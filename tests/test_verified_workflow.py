"""Offline regression tests; every applicant and identity here is fictional."""
import asyncio
import base64
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.core import identity, llm_gateway
from app.core.config import settings
from app.core.evidence import approved_facts, review_document
from app.core.runtime import assert_submission_lease, submission_lease
from app.core.audit import authorize_privacy_erasure
from app.db.base import Base, engine, AsyncSessionLocal
from app.db.models import Application, ApplicationEvent, Document, Profile, Scholarship, User, Job
from app.agents.generation import draft_verified
from app.main import app
from app.integrations.browser_runner import detect_blockers
from app.jobs.queue import execute_job
from app.core.rate_limiter import rate_limit_dependency
from pypdf import PdfReader
from io import BytesIO
from pydantic import BaseModel


@pytest.fixture(autouse=True)
def database():
    async def schema(create: bool) -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all if create else Base.metadata.drop_all)
    asyncio.run(schema(True))
    yield
    asyncio.run(schema(False))


def test_document_review_rejects_invention_and_invalidates_changed_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def run() -> None:
        async with AsyncSessionLocal() as session:
            user = User(email="fictional.review@example.test")
            session.add(user)
            await session.flush()
            profile = Profile(user_id=user.id, personal_details={})
            path = Path("storage/documents") / str(user.id) / "cv.txt"
            path.parent.mkdir(parents=True)
            path.write_text("I studied engineering at Fictional College.")
            document = Document(user_id=user.id, type="cv", storage_key=str(path))
            session.add_all([profile, document])
            await session.commit()
            fact = {"category": "education", "text": "I studied engineering", "source_excerpt": "I studied engineering at Fictional College."}
            with pytest.raises(ValueError):
                await review_document(document, profile, [{**fact, "text": "I won 12 awards"}], session)
            await review_document(document, profile, [fact], session)
            assert len(await approved_facts(profile, session)) == 1
            path.write_text("A replaced source document.")
            assert await approved_facts(profile, session) == []
    asyncio.run(run())


def test_audit_events_block_updates_and_wrong_owner_deletion():
    async def run() -> None:
        async with AsyncSessionLocal() as session:
            user = User(email="fictional.audit@example.test")
            scholarship = Scholarship(title="Fictional award", provider="Fictional College", country="UK", level="masters", field="Engineering", amount=1, application_url="https://example.test", eligibility_rules={})
            session.add_all([user, scholarship])
            await session.flush()
            application = Application(user_id=user.id, scholarship_id=scholarship.id)
            session.add(application)
            await session.flush()
            session.add(ApplicationEvent(application_id=application.id, actor="test", event_type="original", payload={}))
            await session.commit()
            owner = user.id
            for query in ("UPDATE application_events SET event_type='changed'", "DELETE FROM application_events"):
                with pytest.raises(DBAPIError):
                    await session.execute(text(query))
                await session.rollback()
            await authorize_privacy_erasure(session, uuid4())
            with pytest.raises(DBAPIError):
                await session.execute(text("DELETE FROM application_events"))
            await session.rollback()
            await authorize_privacy_erasure(session, owner)
            await session.execute(text("DELETE FROM application_events"))
            await session.commit()
    asyncio.run(run())


def test_lease_loss_stops_submit_and_does_not_unlock_successor(offline_services):
    async def run() -> None:
        identifier = uuid4()
        key = "scholarpilot:submission:" + str(identifier)
        async with submission_lease(identifier):
            await assert_submission_lease()
            await offline_services.set(key, "successor")
            with pytest.raises(RuntimeError, match="lost"):
                await assert_submission_lease()
        assert await offline_services.get(key) == "successor"
    asyncio.run(run())


def test_signed_identity_token_verification_and_replay(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    encode = lambda data: base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    now = time.time()
    claims = {"iss": "https://identity.example.test", "aud": "scholarpilot", "sub": "fictional-user", "email": "fictional.identity@example.test", "email_verified": True, "iat": now, "exp": now + 600}
    pieces = [encode(json.dumps({"alg": "RS256", "kid": "fixture"}).encode()), encode(json.dumps(claims).encode())]
    token = ".".join(pieces) + "." + encode(private.sign(".".join(pieces).encode(), padding.PKCS1v15(), hashes.SHA256()))
    key = {"kid": "fixture", "kty": "RSA", "n": encode(numbers.n.to_bytes(256, "big")), "e": encode(numbers.e.to_bytes(3, "big"))}
    async def get_keys(client, url, **kwargs):
        return httpx.Response(200, json={"keys": [key]}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", get_keys)
    monkeypatch.setattr(settings, "OIDC_ISSUER", claims["iss"])
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", claims["aud"])
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", claims["iss"] + "/keys")
    async def run() -> None:
        with pytest.raises(ValueError):
            await identity.verify_identity(token, "someone.else@example.test")
        assert len(await identity.verify_identity(token, claims["email"])) == 64
        with pytest.raises(ValueError, match="already exchanged"):
            await identity.verify_identity(token, claims["email"])
    asyncio.run(run())


@pytest.mark.parametrize("field,value", [("aud", "wrong"), ("email_verified", False), ("exp", 1), ("iat", 1), ("sub", "")])
def test_identity_claims_reject_invalid_values(field, value, monkeypatch):
    now = time.time()
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://example.test")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "fixture")
    claims = {"iss": settings.OIDC_ISSUER, "aud": "fixture", "email_verified": True, "email": "fictional@example.test", "sub": "fixture", "exp": now + 600, "iat": now, field: value}
    with pytest.raises(ValueError):
        identity.validate_claims(claims, "fictional@example.test")


def test_challenger_rejects_title_upgrade_and_revision_preserves_source(monkeypatch):
    outputs = [
        {"segments": [{"id": "a", "text": "I was president.", "section": "essay", "source_ids": ["F1"]}]},
        {"decisions": [{"id": "a", "supported": True, "reason": "Overbroad judgment"}]},
        {"decisions": [{"id": "a", "supported": False, "reason": "Source says assistant coordinator"}]},
        {"segments": [{"id": "a", "text": "I was assistant coordinator.", "section": "essay", "source_ids": ["F1"]}]},
        {"decisions": [{"id": "a", "supported": True, "reason": "Exact source"}]},
        {"decisions": [{"id": "a", "supported": True, "reason": "Exact source"}]},
    ]
    async def call(system, prompt, schema, **kwargs):
        result = outputs.pop(0)
        return llm_gateway.LLMResponse(content=json.dumps(result), parsed=schema.model_validate(result), model_used="fixture", input_tokens=1, output_tokens=1, cost_usd=0, latency_seconds=0, fallback_used=False)
    monkeypatch.setattr(llm_gateway, "call_llm", call)
    segments, report, usage = asyncio.run(draft_verified([{"id": "F1", "text": "I was assistant coordinator.", "kind": "profile"}], "Original experience", 100, "fictional"))
    assert [segment.text for segment in segments] == ["I was assistant coordinator."]
    assert report["unsupported_before"] == 1
    assert report["unsupported_final"] == 0
    assert report["rounds"] == 2
    assert len(usage) == 6


def test_upload_review_export_and_scope_boundaries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            key = (await client.post("/v1/auth/keys", json={"email": "fictional.upload@example.test"})).json()["api_key"]
            headers = {"X-API-Key": key}
            await client.put("/v1/profile", headers=headers, json={"personal_details": {"_identity_subject": "forged", "_verified_facts": [{"text": "invented"}]}})
            profile = (await client.get("/v1/profile", headers=headers)).json()
            assert "_verified_facts" not in profile["personal_details"]
            content = "I studied engineering at Fictional College."
            response = await client.post("/v1/documents/upload", headers=headers, json={"type": "cv", "filename": "cv.txt", "content_base64": base64.b64encode(content.encode()).decode()})
            assert response.status_code == 201
            document = response.json()
            assert document["verified"] is False
            reviewed = await client.post(f"/v1/documents/{document['id']}/verify", headers=headers, json={"confirmed": True, "facts": [{"text": content, "source_excerpt": content, "category": "education"}]})
            assert reviewed.json()["verified"] is True
            exported = (await client.get("/v1/account/export?include_files=true", headers=headers)).json()
            assert base64.b64decode(exported["documents"][0]["content_base64"]).decode() == content
            read_key = (await client.post("/v1/auth/keys", json={"email": "fictional.readonly@example.test", "scopes": ["read"]})).json()["api_key"]
            assert (await client.put("/v1/profile", headers={"X-API-Key": read_key}, json={})).status_code == 403
            assert (await client.get("/v1/profile", headers={"X-API-Key": read_key})).status_code == 200
            assert (await client.delete("/v1/account", headers=headers)).status_code == 200
            assert not Path(document["storage_key"]).exists()
    asyncio.run(run())


def test_batch_builds_owned_packages_and_erasure_removes_them(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def run() -> None:
        async with AsyncSessionLocal() as session:
            for index in range(2):
                session.add(Scholarship(title=f"Fictional award {index}", provider="Fictional College", country="UK", level="masters", field="Engineering", amount=1, status="active", application_url="https://example.test", eligibility_rules={"fields": ["Engineering"], "ai_policy": "unknown"}))
            await session.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            key = (await client.post("/v1/auth/keys", json={"email": "fictional.batch@example.test"})).json()["api_key"]
            headers = {"X-API-Key": key}
            await client.put("/v1/profile", headers=headers, json={"personal_details": {"target_level": "masters"}, "target_countries": ["UK"], "target_fields_of_study": ["Engineering"], "achievements": [{"description": "I studied engineering at Fictional College."}]})
            started = await client.post("/v1/runs", headers=headers, json={"top_n": 1})
            assert started.status_code == 202
            run_id = started.json()["run_id"]
            batch = (await client.get(f"/v1/runs/{run_id}", headers=headers)).json()
            assert len(batch["application_ids"]) == 2
            await execute_job(UUID(run_id))
            application_id = batch["application_ids"][0]
            detail = (await client.get(f"/v1/applications/{application_id}", headers=headers)).json()
            assert detail["status"] == "needs_human"
            assert detail["package"]
            cv = await client.get(detail["package"]["cv_pdf_url"], headers=headers)
            assert "Fictional College" in PdfReader(BytesIO(cv.content)).pages[0].extract_text()
            files = list(Path("storage/packages").rglob("*.*"))
            assert len(files) == 3
            other = (await client.post("/v1/auth/keys", json={"email": "fictional.other@example.test"})).json()["api_key"]
            assert (await client.get(detail["package"]["cv_pdf_url"], headers={"X-API-Key": other})).status_code == 404
            assert (await client.delete("/v1/account", headers=headers)).status_code == 200
            assert all(not file.exists() for file in files)
    asyncio.run(run())


def test_production_rate_limit_is_shared_and_rotating_headers_cannot_bypass(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    first, second = rate_limit_dependency(2, 60), rate_limit_dependency(2, 60)
    async def run() -> None:
        from fastapi import HTTPException, Request
        def request(key: str) -> Request:
            return Request({"type": "http", "headers": [(b"x-api-key", key.encode())], "client": ("192.0.2.5", 123)})
        await first(request("one"))
        await second(request("two"))
        with pytest.raises(HTTPException) as captured:
            await first(request("three"))
        assert captured.value.status_code == 429
    asyncio.run(run())


def test_public_dns_rejects_private_and_mixed_addresses(monkeypatch):
    from app.core import public_fetch
    monkeypatch.setattr(public_fetch.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="mixed DNS"):
        asyncio.run(public_fetch.resolve_public("fictional.example.test", 443))


def test_confirmed_handoff_reconciles_without_another_submission(monkeypatch):
    from app.api.v1 import applications
    async def confirmation(url: str) -> str:
        assert url == "http://localhost:8000/portal/draft/fictional"
        return "DEMO1234"
    monkeypatch.setattr(applications, "read_confirmation", confirmation)
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            key = (await client.post("/v1/auth/keys", json={"email": "fictional.handoff@example.test"})).json()["api_key"]
            headers = {"X-API-Key": key}
            profile = (await client.get("/v1/profile", headers=headers)).json()
            async with AsyncSessionLocal() as session:
                scholarship = Scholarship(title="Fictional demo", provider="Fictional College", country="UK", level="masters", field="Engineering", amount=1, application_url="http://localhost:8000/portal/apply/fictional", eligibility_rules={})
                session.add(scholarship)
                await session.flush()
                application = Application(user_id=UUID(profile["user_id"]), scholarship_id=scholarship.id, status="needs_human", mode_used="review")
                session.add(application)
                await session.flush()
                session.add(ApplicationEvent(application_id=application.id, actor="test", event_type="handoff", payload={"portal_url": "http://localhost:8000/portal/draft/fictional", "acceptance_unknown": True}))
                await session.commit()
                identifier = application.id
            response = await client.post(f"/v1/applications/{identifier}/resume", headers=headers)
            assert response.status_code == 200
            assert response.json()["status"] == "submitted"
            assert response.json()["confirmation_ref"] == "DEMO1234"
            async with AsyncSessionLocal() as session:
                assert (await session.execute(select(Job).where(Job.type == "submit_application"))).scalars().all() == []
    asyncio.run(run())


def test_gateway_counts_billed_invalid_output_and_rejects_missing_usage(monkeypatch):
    class Result(BaseModel):
        value: int
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fictional-offline-key")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(llm_gateway, "circuit_breaker", llm_gateway.ProviderCircuitBreaker())
    results = ["not valid JSON", '{"value": 7}']
    async def post(client, url, **kwargs):
        return httpx.Response(200, json={"choices": [{"message": {"content": results.pop(0)}}], "usage": {"prompt_tokens": 20, "completion_tokens": 10}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    result = asyncio.run(llm_gateway.call_llm("fictional", "fictional", Result, user_id="fictional"))
    assert result.parsed.value == 7
    assert result.input_tokens == 40 and result.output_tokens == 20
    async def absent(client, url, **kwargs):
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"value": 7}'}}]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", absent)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)
    with pytest.raises(RuntimeError, match="All model providers failed"):
        asyncio.run(llm_gateway.call_llm("fictional", "fictional", Result, user_id="fictional"))


def test_production_readiness_requires_applied_migration(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
            assert response.status_code == 503
            assert response.json()["checks"]["schema"] is False
    asyncio.run(run())


def test_portal_script_error_strings_are_not_a_captcha():
    script = "<script>const error = 'Please solve the challenge.';</script>"
    assert detect_blockers("<form><button>Submit</button></form>" + script) is None
    assert detect_blockers('<div id="captcha_challenge">Human security check</div>' + script)[0] == "captcha"
    assert detect_blockers('<input type="password">' + script)[0] == "login_wall"
