"""Fictional regression cases and real-world boundary/recovery invariants, all offline."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.agents.verifier import deterministic_check
from app.agents.planner import adaptive_actions
from app.db.base import Base, engine, AsyncSessionLocal
from app.db.models import Job, ApplicationEvent
from app.services import public_pages, notifications
from app.services.discovery import deadline_observation, observe_pages
from app.core.config import settings
from backend.app.tracing import metadata_mask
from app.jobs.queue import get_redis_client as actual_broker_client

CASES = json.loads((Path(__file__).parent / "fixtures/factuality_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_fictional_source_regressions(case):
    assert deterministic_check(case["claim"], case["sources"]) is case["supported"]


def test_official_page_blockers_do_not_become_evidence():
    assert public_pages.parse_page('<form><input type="password">Sign in</form>', "https://example.test")["blocker"] == "login"
    page = public_pages.parse_page("<p>Verify you are human</p>", "https://example.test")
    assert page["blocker"] == "captcha" and page["text"] == ""


def test_deadline_is_not_guessed_from_missing_year_or_conflicts():
    assert deadline_observation("The closing date is 20 October.")["deadline"] is None
    assert deadline_observation("Deadline: 20 October 2099. Deadline: 21 October 2099.")["ambiguous"]
    assert deadline_observation("The closing date is 16:00 BST on Tuesday 20 October.", 2026)["deadline"].startswith("2026-10-20")
    assert deadline_observation("The closing date is 16:00 BST on Tuesday 20 October.", 2026)["deadline"] == "2026-10-20T15:00:00+00:00"


def test_closed_and_unknown_ai_policy_are_not_overridden_by_catalog():
    result = observe_pages([{"url": "https://example.test", "text": "Applications are closed. Artificial intelligence generation is strictly prohibited."}])
    assert result["state"] == "closed" and result["ai_policy"] == "restricted"


def test_adaptive_actions_bound_repeated_research_and_require_evidence():
    assert adaptive_actions(None, None, False, [], 0) == ["request_evidence", "skip_opportunity"]
    events = [ApplicationEvent(event_type="agent_decision", payload={"action": "retry_research"}) for _ in range(2)]
    assert "retry_research" not in adaptive_actions([], [], False, events, 3)
    assert "finish" not in adaptive_actions([], [], False, events, 3)


def test_snapshot_survives_new_database_session(monkeypatch):
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        return "<title>Fictional College</title><p>Fictional scholarship requirements.</p>"
    monkeypatch.setattr(public_pages, "fetch_public_text", fetch)
    async def run():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with AsyncSessionLocal() as session:
                first = await public_pages.get_page("https://example.test/scholarship", {"example.test"}, session)
            async with AsyncSessionLocal() as session:
                second = await public_pages.get_page("https://example.test/scholarship", {"example.test"}, session)
            assert second["from_cache"] and first["sha256"] == second["sha256"]
            assert len(calls) == 1
        finally:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
    asyncio.run(run())


def test_no_notification_provider_is_not_a_delivery(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_APP_PASSWORD", None)
    assert not asyncio.run(notifications.deliver("telegram", "fictional-chat", "Fictional test"))["ok"]
    assert not asyncio.run(notifications.deliver("email", "fictional@example.test", "Fictional test"))["ok"]


def test_mask_preserves_usage_without_applicant_prompt():
    masked = metadata_mask({"name": "model", "attributes": {"input.value": "private applicant text",
        "output.value": "private draft", "llm.token_count.total": 42, "llm.model_name": "fictional-test-model"},
        "events": [{"private": "applicant content"}]})
    assert masked["attributes"] == {"llm.token_count.total": 42, "llm.model_name": "fictional-test-model"}
    assert not masked["events"]


def test_mask_preserves_installed_sdk_token_attribute_names():
    payload = {"attributes": {"neatlogs.llm.token_count.prompt": 13, "neatlogs.llm.token_count.completion": 7,
        "neatlogs.llm.token_count.total": 20, "neatlogs.llm.model": "fictional-model",
        "neatlogs.llm.input": "private input", "neatlogs.llm.output": "private output"}}
    attributes = metadata_mask(payload)["attributes"]
    assert attributes["neatlogs.llm.token_count.total"] == 20
    assert attributes["neatlogs.llm.model"] == "fictional-model"
    assert "neatlogs.llm.input" not in attributes and "neatlogs.llm.output" not in attributes


def test_empty_claim_is_rejected():
    assert not deterministic_check("", ["A fictional source fact."])


def test_ses_delivery_uses_role_chain_and_records_actual_message(monkeypatch):
    calls = []
    class FakeClient:
        def send_email(self, **kwargs):
            calls.append(kwargs)
            return {"MessageId": "fictional-provider-message"}
        def close(self):
            calls.append("closed")
    class FakeSession:
        def __init__(self, **kwargs):
            assert kwargs == {"region_name": "eu-north-1"}
        def client(self, name, **kwargs):
            assert name == "sesv2"
            assert kwargs["config"].retries["total_max_attempts"] == 1
            return FakeClient()
    monkeypatch.setattr(notifications.boto3, "Session", FakeSession)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "ses")
    monkeypatch.setattr(settings, "SES_FROM", "fictional-sender@example.test")
    result = notifications.send_email("fictional-recipient@example.test", "Fictional test", "Fictional content")
    assert result["ok"] and result["message_id"] == "fictional-provider-message"
    assert calls[0]["Destination"] == {"ToAddresses": ["fictional-recipient@example.test"]}
    assert calls[-1] == "closed"


def test_cancel_marker_blocks_existing_submission_lease(monkeypatch):
    import uuid
    from app.core import runtime
    from conftest import FakeRedis
    broker = FakeRedis()
    async def redis_client():
        return broker
    monkeypatch.setattr(runtime, "get_redis_client", redis_client)
    async def run():
        application_id = uuid.uuid4()
        async with runtime.submission_lease(application_id):
            await runtime.assert_submission_lease()
            await broker.set("scholarpilot:application_cancelled:" + str(application_id), "1")
            with pytest.raises(RuntimeError, match="cancelled"):
                await runtime.assert_submission_lease()
    asyncio.run(run())


def test_release_archive_excludes_private_and_generated_files(tmp_path):
    import tarfile
    from scripts.deploy_aws import bundle
    destination = tmp_path / "release.tgz"
    manifest = bundle(destination)
    assert "backend/data/synthetic/cv.txt" in manifest
    assert "app/services/notifications.py" in manifest
    with tarfile.open(destination) as archive:
        for name in archive.getnames():
            assert "node_modules/" not in name and "storage/" not in name
            assert not any(part.startswith(".env") for part in name.split("/"))


def test_oidc_pkce_nonce_and_one_time_state(monkeypatch, offline_services):
    import base64
    from urllib.parse import urlsplit, parse_qs
    from app.api.v1 import onboarding
    monkeypatch.setattr(settings, "OIDC_AUTHORIZATION_URL", "https://identity.example.test/authorize")
    monkeypatch.setattr(settings, "OIDC_TOKEN_URL", "https://identity.example.test/token")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "fictional-client")
    payload = base64.urlsafe_b64encode(json.dumps({"nonce": "wrong-nonce", "email": "fictional@example.test"}).encode()).decode().rstrip("=")
    token = "fictional-header." + payload + ".fictional-signature"
    original_client = httpx.AsyncClient
    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"id_token": token})), **kwargs)
    monkeypatch.setattr(onboarding.httpx, "AsyncClient", client)
    async def run():
        result = await onboarding.authorize()
        query = parse_qs(urlsplit(result["url"]).query)
        assert query["code_challenge_method"] == ["S256"]
        saved = json.loads(await offline_services.get("scholarpilot:oidc:" + result["state"]))
        assert saved["verifier"] not in result["url"]
        with pytest.raises(HTTPException) as rejected:
            await onboarding.callback(onboarding.Callback(state=result["state"], code="fictional-code"), None)
        assert rejected.value.status_code == 401
        assert await offline_services.get("scholarpilot:oidc:" + result["state"]) is None
        with pytest.raises(HTTPException, match="already used"):
            await onboarding.callback(onboarding.Callback(state=result["state"], code="fictional-code"), None)
    asyncio.run(run())


def test_official_redirect_cannot_fetch_private_destination(monkeypatch):
    from app.core import public_fetch
    calls = []
    async def resolve(host, port):
        return "8.8.8.8"
    def response(request):
        calls.append(str(request.url))
        return httpx.Response(307, headers={"location": "http://127.0.0.1/private"})
    original_client = httpx.AsyncClient
    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(public_fetch, "resolve_public", resolve)
    monkeypatch.setattr(public_fetch.httpx, "AsyncClient", client)
    with pytest.raises(ValueError, match="HTTPS"):
        asyncio.run(public_fetch.fetch_public_text("https://official.example.test/page", {"official.example.test"}, 2))
    assert len(calls) == 1


def test_generated_sources_must_still_match_reviewed_documents(monkeypatch):
    from app.core import evidence
    async def reviewed(profile, session):
        return [{"id": "fictional-fact", "text": "A changed fictional fact."}]
    monkeypatch.setattr(evidence, "approved_facts", reviewed)
    with pytest.raises(ValueError, match="evidence changed"):
        asyncio.run(evidence.assert_current_sources(object(), [{"id": "fictional-fact", "text": "An old fictional fact.", "kind": "profile"}], None))


def test_stale_redis_connection_is_replaced_without_replaying_writes(monkeypatch):
    from app.jobs import queue
    from redis.exceptions import ConnectionError
    calls = []
    class Stale:
        async def ping(self):
            raise ConnectionError("Fictional stale connection.")
        async def aclose(self):
            calls.append("old_closed")
    class Healthy:
        async def ping(self):
            calls.append("fresh_ping")
    healthy = Healthy()
    monkeypatch.setattr(queue, "_redis_client", Stale())
    monkeypatch.setattr(queue.aioredis, "from_url", lambda *args, **kwargs: healthy)
    assert asyncio.run(actual_broker_client()) is healthy
    assert calls == ["old_closed", "fresh_ping"]
