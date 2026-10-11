"""Acceptance tests for Milestone 6: Autonomy Scheduler, Deadline Alerts (7d/3d/1d), Webhooks, and Telegram."""
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import pytest
from sqlalchemy import select
from app.core.security import verify_webhook_signature
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, Profile, Scholarship, User, Webhook
from app.integrations.telegram import (
    format_blocker_alert,
    format_daily_digest,
    format_deadline_alert,
    format_submission_alert,
    send_telegram_message,
)
from app.integrations.webhooks import dispatch_user_webhooks
from app.services.scheduler import run_daily_scheduler_cycle, scan_upcoming_deadlines
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


def test_telegram_message_formatting():
    """Verifies that Telegram alerts format clear markdown with required details."""
    # 1. Blocker Alert
    b_msg = format_blocker_alert(
        scholarship_title="Chevening Scholarship 2027",
        blocker_type="captcha",
        blocker_message="Cloudflare Turnstile challenge detected",
        portal_url="https://chevening.org/apply",
    )
    assert "Chevening Scholarship 2027" in b_msg
    assert "captcha" in b_msg
    assert "https://chevening.org/apply" in b_msg
    assert "Action Required" in b_msg

    # 2. Submission Alert
    s_msg = format_submission_alert(
        scholarship_title="Gates Cambridge Scholarship",
        confirmation_ref="CONF-2026-GC-9921",
        submitted_at=datetime(2026, 10, 11, 14, 30, tzinfo=timezone.utc),
    )
    assert "Gates Cambridge Scholarship" in s_msg
    assert "CONF-2026-GC-9921" in s_msg
    assert "2026-10-11 14:30:00 UTC" in s_msg

    # 3. Deadline Alert
    d_msg = format_deadline_alert(
        scholarship_title="Rhodes Scholarship",
        days_remaining=3,
        deadline_str="2026-10-14",
        application_status="ready_for_review",
    )
    assert "3 Days Left" in d_msg
    assert "Rhodes Scholarship" in d_msg
    assert "ready_for_review" in d_msg

    # 4. Daily Digest
    digest = format_daily_digest(
        new_matches_count=5,
        pending_reviews_count=2,
        upcoming_deadlines=[{"title": "Commonwealth Shared", "days_remaining": 1}],
    )
    assert "New Matching Opportunities: *5*" in digest
    assert "Applications Awaiting Review: *2*" in digest
    assert "Commonwealth Shared" in digest
    assert "1d remaining" in digest


def test_deadline_monitoring_buckets():
    """Verifies that scholarships approaching deadlines (7d, 3d, 1d) are accurately classified."""
    async def run():
        async with AsyncSessionLocal() as session:
            now = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)

            # Insert test scholarships with known relative deadlines
            s_1d = Scholarship(
                title="1-Day Urgent Scholarship",
                provider="Org A",
                country="United Kingdom",
                level="masters",
                field="Engineering",
                amount=10000.0,
                deadline=now + timedelta(hours=18),  # 0.75 days
                application_url="https://example.com/apply1",
                eligibility_rules={},
            )
            s_3d = Scholarship(
                title="3-Day Impending Scholarship",
                provider="Org B",
                country="United States",
                level="masters",
                field="Engineering",
                amount=20000.0,
                deadline=now + timedelta(days=2, hours=12),  # 2.5 days
                application_url="https://example.com/apply2",
                eligibility_rules={},
            )
            s_7d = Scholarship(
                title="7-Day Warning Scholarship",
                provider="Org C",
                country="Canada",
                level="masters",
                field="Engineering",
                amount=15000.0,
                deadline=now + timedelta(days=6),  # 6.0 days
                application_url="https://example.com/apply3",
                eligibility_rules={},
            )
            s_far = Scholarship(
                title="Far Future Scholarship",
                provider="Org D",
                country="Germany",
                level="masters",
                field="Engineering",
                amount=5000.0,
                deadline=now + timedelta(days=30),  # Not in 7d bucket
                application_url="https://example.com/apply4",
                eligibility_rules={},
            )
            session.add_all([s_1d, s_3d, s_7d, s_far])
            await session.commit()

            alerts = await scan_upcoming_deadlines(session, reference_time=now)
            buckets = {a["title"]: a["bucket"] for a in alerts}

            assert buckets.get("1-Day Urgent Scholarship") == "1d"
            assert buckets.get("3-Day Impending Scholarship") == "3d"
            assert buckets.get("7-Day Warning Scholarship") == "7d"
            assert "Far Future Scholarship" not in buckets

    asyncio.run(run())


def test_hmac_signed_webhook_dispatch():
    """Verifies that webhook payloads are delivered with valid HMAC-SHA256 signatures."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="webhook.student@example.com", status="active")
            session.add(user)
            await session.commit()

            secret = "whsec_test_secret_key_12345"
            webhook = Webhook(
                user_id=user.id,
                url="https://mock.webhook.site/receiver",
                secret=secret,
                events_subscribed=["scholarship.deadline_warning"],
            )
            session.add(webhook)
            await session.commit()

            # Mock httpx client to intercept and verify outgoing webhook payload
            received_requests = []

            async def mock_handler(request: httpx.Request):
                received_requests.append(request)
                return httpx.Response(200, json={"received": True})

            transport = httpx.MockTransport(mock_handler)
            async with httpx.AsyncClient(transport=transport) as mock_client:
                results = await dispatch_user_webhooks(
                    user_id=user.id,
                    event_type="scholarship.deadline_warning",
                    payload={"scholarship_title": "Test Chevening", "days_remaining": 3},
                    session=session,
                    client=mock_client,
                )

            assert len(results) == 1
            assert results[0]["success"] is True

            # Verify intercepted request
            assert len(received_requests) == 1
            req = received_requests[0]
            sig = req.headers.get("X-ScholarPilot-Signature")
            assert sig is not None

            # Verify that our verification function confirms the signature
            is_valid = verify_webhook_signature(req.content, secret, sig)
            assert is_valid is True

            # Verify event header and body
            assert req.headers.get("X-ScholarPilot-Event") == "scholarship.deadline_warning"
            body = json.loads(req.content.decode("utf-8"))
            assert body["event_type"] == "scholarship.deadline_warning"
            assert body["data"]["scholarship_title"] == "Test Chevening"

    asyncio.run(run())


def test_daily_scheduler_cycle_end_to_end():
    """Full Milestone 6 acceptance: daily cycle runs matching, scans deadlines, and dispatches alerts."""
    async def run():
        async with AsyncSessionLocal() as session:
            # Create active user with complete profile
            user = User(email="autonomous.student@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Amina", "citizenship": "Nigeria"},
                target_countries=["United Kingdom", "Canada"],
                target_fields_of_study=["Computer Science", "Artificial Intelligence"],
                education_history=[{"degree": "B.Sc.", "field": "Computer Science"}],
                grades={"gpa": 4.8},
                completeness_score=1.0,
            )
            session.add(profile)

            # Add an upcoming urgent deadline scholarship
            now = datetime.now(timezone.utc)
            schol = (await session.execute(select(Scholarship))).scalars().first()
            schol.deadline = now + timedelta(days=2)  # within 3d window
            session.add(schol)
            await session.commit()

            # Execute scheduler cycle
            cycle_result = await run_daily_scheduler_cycle(session, reference_time=now)

            assert "matching" in cycle_result
            assert cycle_result["matching"]["users_processed"] >= 1
            assert cycle_result["deadline_alerts_count"] >= 1

    asyncio.run(run())
