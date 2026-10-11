"""Acceptance tests for Milestone 4: State Machine, Autonomy Modes, and Event Auditing."""
import asyncio
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.core.config import settings
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, ApplicationEvent, Scholarship, User
from app.jobs.state_machine import (
    IllegalStateTransitionError,
    KillSwitchActiveError,
    transition_application,
)
from app.main import app
from scripts.import_catalog import import_listings
from pathlib import Path


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


def test_autopilot_mode_lifecycle_and_events():
    """Verifies Autopilot lifecycle flow and append-only event logging."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="auto.pilot@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol_list = (await session.execute(select(Scholarship))).scalars().all()
            schol = schol_list[0]

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="discovered",
                mode_used="autopilot",
            )
            session.add(app_record)
            await session.commit()
            await session.refresh(app_record)

            # 1. discovered -> matched
            await transition_application(app_record, "matched", "matcher", {"fit_score": 85.0}, session)
            assert app_record.status == "matched"

            # 2. matched -> researching
            await transition_application(app_record, "researching", "coordinator", {}, session)
            assert app_record.status == "researching"

            # 3. researching -> drafting
            await transition_application(app_record, "drafting", "drafter", {"facts_used": 3}, session)
            assert app_record.status == "drafting"

            # 4. drafting -> submitting (valid in autopilot)
            await transition_application(app_record, "submitting", "coordinator", {"channel": "portal_form"}, session)
            assert app_record.status == "submitting"

            # 5. submitting -> submitted
            await transition_application(app_record, "submitted", "applier", {"confirmation_code": "CONF-999"}, session)
            assert app_record.status == "submitted"
            assert app_record.submitted_at is not None

            # Verify every transition wrote an application_events row
            events_stmt = select(ApplicationEvent).where(ApplicationEvent.application_id == app_record.id).order_by(ApplicationEvent.created_at.asc())
            events = (await session.execute(events_stmt)).scalars().all()
            assert len(events) == 5
            event_types = [e.event_type for e in events]
            assert event_types == [
                "status_changed_matched",
                "status_changed_researching",
                "status_changed_drafting",
                "status_changed_submitting",
                "status_changed_submitted",
            ]

    asyncio.run(run())


def test_review_mode_lifecycle_and_approval():
    """Verifies Review mode halts at ready_for_review and requires explicit approval."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="review.user@example.com", mode="review", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="drafting",
                mode_used="review",
            )
            session.add(app_record)
            await session.commit()

            # Attempting drafting -> submitting in Review mode MUST fail
            with pytest.raises(IllegalStateTransitionError, match="Review mode violation"):
                await transition_application(app_record, "submitting", "agent", {}, session)

            # drafting -> ready_for_review MUST succeed
            await transition_application(app_record, "ready_for_review", "drafter", {"review_prompt": "Please review draft"}, session)
            assert app_record.status == "ready_for_review"

            # ready_for_review -> approved
            await transition_application(app_record, "approved", "user", {"user_approved": True}, session)
            assert app_record.status == "approved"

            # approved -> submitting
            await transition_application(app_record, "submitting", "applier", {}, session)
            assert app_record.status == "submitting"

    asyncio.run(run())


def test_illegal_transitions_rejected():
    """Verifies illegal transitions are rejected with IllegalStateTransitionError."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="illegal.trans@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="discovered",
                mode_used="autopilot",
            )
            session.add(app_record)
            await session.commit()

            # discovered cannot jump directly to submitted
            with pytest.raises(IllegalStateTransitionError):
                await transition_application(app_record, "submitted", "agent", {}, session)

            # Fast-forward to submitted
            app_record.status = "submitted"
            await session.commit()

            # submitted cannot transition back to drafting (terminal state)
            with pytest.raises(IllegalStateTransitionError):
                await transition_application(app_record, "drafting", "agent", {}, session)

    asyncio.run(run())


def test_needs_human_and_resume():
    """Verifies needs_human blocker and human resume transition."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="human.resume@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="submitting",
                mode_used="autopilot",
            )
            session.add(app_record)
            await session.commit()

            # CAPTCHA detected -> needs_human
            await transition_application(app_record, "needs_human", "applier", {"blocker": "captcha_challenge"}, session)
            assert app_record.status == "needs_human"

            # User solves challenge -> resume to submitting
            await transition_application(app_record, "submitting", "user", {"resumed_by_user": True}, session)
            assert app_record.status == "submitting"

    asyncio.run(run())


def test_kill_switch_active_blocks_submissions():
    """Verifies global kill switch stops submissions immediately."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="kill.switch@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="drafting",
                mode_used="autopilot",
            )
            session.add(app_record)
            await session.commit()

            # Activate kill switch
            settings.KILL_SWITCH_ACTIVE = True
            try:
                with pytest.raises(KillSwitchActiveError, match="Global kill switch is active"):
                    await transition_application(app_record, "submitting", "agent", {}, session)
            finally:
                settings.KILL_SWITCH_ACTIVE = False

    asyncio.run(run())


def test_applications_rest_endpoints():
    """Verifies full REST lifecycle: start -> list -> detail -> approve -> resume -> withdraw -> settings."""
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create key
            key_resp = await client.post("/v1/auth/keys", json={"email": "rest.apps@example.com"})
            api_key = key_resp.json()["api_key"]
            headers = {"X-API-Key": api_key}

            # 2. Get active scholarship
            schol_resp = await client.get("/v1/scholarships", headers=headers)
            schol_id = schol_resp.json()["items"][0]["id"]

            # 3. Start application
            start_resp = await client.post(
                "/v1/applications",
                headers=headers,
                json={"scholarship_id": schol_id, "mode": "review"},
            )
            assert start_resp.status_code == 201
            app_id = start_resp.json()["id"]
            assert start_resp.json()["status"] == "discovered"
            assert len(start_resp.json()["events"]) >= 1

            # 4. List applications
            list_resp = await client.get("/v1/applications", headers=headers)
            assert list_resp.status_code == 200
            assert len(list_resp.json()) == 1

            # 5. Fast-forward application in DB to ready_for_review to test approval endpoint
            async with AsyncSessionLocal() as session:
                app_obj = await session.get(Application, uuid.UUID(app_id))
                app_obj.status = "ready_for_review"
                await session.commit()

            # 6. Approve application via endpoint
            approve_resp = await client.post(f"/v1/applications/{app_id}/approve", headers=headers)
            assert approve_resp.status_code == 200
            assert approve_resp.json()["status"] == "approved"

            # 7. Fast-forward application in DB to needs_human to test resume endpoint
            async with AsyncSessionLocal() as session:
                app_obj = await session.get(Application, uuid.UUID(app_id))
                app_obj.status = "needs_human"
                await session.commit()

            resume_resp = await client.post(f"/v1/applications/{app_id}/resume", headers=headers)
            assert resume_resp.status_code == 200
            assert resume_resp.json()["status"] == "submitting"

            # 8. Withdraw application
            withdraw_resp = await client.post(f"/v1/applications/{app_id}/withdraw", headers=headers)
            assert withdraw_resp.status_code == 200
            assert withdraw_resp.json()["status"] == "withdrawn"

            # 9. Settings endpoints
            settings_get = await client.get("/v1/settings", headers=headers)
            assert settings_get.status_code == 200

            settings_put = await client.put(
                "/v1/settings",
                headers=headers,
                json={"mode": "review", "timezone": "Africa/Lagos", "telegram_chat_id": "123456789"},
            )
            assert settings_put.status_code == 200
            assert settings_put.json()["mode"] == "review"
            assert settings_put.json()["telegram_chat_id"] == "123456789"

    asyncio.run(run())
