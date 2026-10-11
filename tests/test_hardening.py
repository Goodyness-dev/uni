"""Acceptance tests for Milestone 7: Hardening, Rate Limiting, Cost Caps, Redaction, Export, and Deletion."""
import asyncio
import json
import uuid
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.core.llm_gateway import LLMSpendLimitExceeded, spend_tracker
from app.core.logging import redact_pii_value
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import ApiKey, Application, Document, Draft, Profile, Scholarship, User
from app.main import app
from scripts.import_catalog import import_listings


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes and tears down in-memory test database and seeds catalog."""
    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        catalog_path = Path(__file__).resolve().parent.parent / "backend" / "data" / "listings.json"
        if catalog_path.exists():
            await import_listings(catalog_path)

    async def teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(init())
    yield
    asyncio.run(teardown())


def test_rate_limiter_sliding_window():
    """Verifies that sliding-window limiter allows requests up to max_requests and blocks excesses."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
    client_key = "test_ip_192.168.1.1"

    assert limiter.is_allowed(client_key) is True
    assert limiter.is_allowed(client_key) is True
    assert limiter.is_allowed(client_key) is True

    # 4th request must be rejected
    assert limiter.is_allowed(client_key) is False
    assert limiter.retry_after(client_key) > 0


def test_llm_gateway_cost_caps():
    """Verifies that exceeding user or global spending caps throws LLMSpendLimitExceeded."""
    user_id = str(uuid.uuid4())

    # Record spend that approaches user daily limit ($1.00)
    spend_tracker.check_and_record(user_id, 0.95)

    # Next call that exceeds cap raises LLMSpendLimitExceeded
    with pytest.raises(LLMSpendLimitExceeded):
        spend_tracker.check_and_record(user_id, 0.10)


def test_pii_redaction_audit():
    """Audits log redactor against emails, phone numbers, and sensitive identification numbers."""
    raw_log = "Applicant Ngozi (email: ngozi.student@lagos.edu.ng, phone: +2348031234567, NIN: 98765432101) applied."
    scrubbed = redact_pii_value(raw_log)

    assert "ngozi.student@lagos.edu.ng" not in scrubbed
    assert "+2348031234567" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed


def test_account_export_and_gdpr_deletion():
    """Full Milestone 7 acceptance: export personal data archive and permanently purge under NDPR/GDPR."""
    async def run():
        async with AsyncSessionLocal() as session:
            # 1. Seed user, API key, profile, document, application, draft
            user = User(email="tobi.ade@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            from app.core.security import hash_api_key
            plain_key = "sp_live_hardening_test_key_123"
            api_key = ApiKey(user_id=user.id, hashed_key=hash_api_key(plain_key), scopes=["*"])
            session.add(api_key)

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Tobi", "last_name": "Adeyemi", "citizenship": "Nigeria"},
                grades={"gpa": 4.9},
            )
            session.add(profile)

            doc = Document(user_id=user.id, type="transcript", storage_key="vault/transcripts/tobi.pdf")
            session.add(doc)

            schol = (await session.execute(select(Scholarship))).scalars().first()
            application = Application(user_id=user.id, scholarship_id=schol.id, status="drafting")
            session.add(application)
            await session.commit()

            draft = Draft(
                application_id=application.id,
                kind="statement",
                content="Personal statement draft for scholar funding.",
                version=1,
            )
            session.add(draft)
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-API-Key": plain_key}

            # 2. Test Account Export
            export_resp = await client.get("/v1/account/export", headers=headers)
            assert export_resp.status_code == 200
            data = export_resp.json()

            assert data["user"]["email"] == "tobi.ade@example.com"
            assert data["profile"]["personal_details"]["first_name"] == "Tobi"
            assert len(data["documents"]) == 1
            assert len(data["applications"]) == 1
            assert len(data["drafts"]) == 1

            # 3. Test Account Deletion (Right to be Forgotten)
            del_resp = await client.delete("/v1/account", headers=headers)
            assert del_resp.status_code == 200
            assert del_resp.json()["success"] is True

        # 4. Verify DB state is thoroughly purged
        async with AsyncSessionLocal() as session:
            # Profile must be deleted
            prof_after = (await session.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
            assert prof_after is None

            # Documents must be deleted
            docs_after = (await session.execute(select(Document).where(Document.user_id == user.id))).scalars().all()
            assert len(docs_after) == 0

            # Drafts must be deleted
            drafts_after = (await session.execute(select(Draft).where(Draft.application_id == application.id))).scalars().all()
            assert len(drafts_after) == 0

            # User email anonymized and marked deleted
            user_after = await session.get(User, user.id)
            assert user_after.status == "deleted"
            assert "tobi.ade@example.com" not in user_after.email
            assert user_after.email.startswith("purged-")

    asyncio.run(run())
