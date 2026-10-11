"""Acceptance tests for Milestone 5: Submitter Agent, Playwright Runner, Screenshots, and CAPTCHA Handoff."""
import asyncio
import os
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select
from app.agents.submitter import run_submitter
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, ApplicationEvent, Draft, Profile, Scholarship, User
from app.integrations.browser_runner import detect_blockers
from app.jobs.state_machine import IllegalStateTransitionError, transition_application
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


def test_blocker_detection_signatures():
    """Verifies that all human-intervention blockers (CAPTCHA, login wall, 2FA, fee) are detected."""
    # 1. CAPTCHA / bot challenges
    c1 = detect_blockers("<div>Please complete the hCaptcha before submitting</div>")
    assert c1 is not None and c1[0] == "captcha"

    c2 = detect_blockers("<iframe src='https://challenges.cloudflare.com/turnstile/v0/api.js'></iframe>")
    assert c2 is not None and c2[0] == "captcha"

    c3 = detect_blockers("<p>Security Check: verify you are human to proceed</p>")
    assert c3 is not None and c3[0] == "captcha"

    # 2. Login wall
    l1 = detect_blockers("<div class='auth'>Sign in to continue your scholarship application</div>")
    assert l1 is not None and l1[0] == "login_wall"

    # 3. Two-factor authentication
    m1 = detect_blockers("<form>Enter the 6-digit code sent to your phone</form>")
    assert m1 is not None and m1[0] == "2fa_verification"

    # 4. Unexpected application fee
    p1 = detect_blockers("<div>An application fee required of $50 must be paid prior to submission</div>")
    assert p1 is not None and p1[0] == "fee_payment"

    # 5. Clean form has no blockers
    clean = detect_blockers("<form><input name='first_name'/><button type='submit'>Submit</button></form>")
    assert clean is None


def test_mocked_portal_submits_once_and_is_idempotent():
    """Milestone 5 acceptance: A mocked portal run submits once and strictly prevents duplicate submission."""
    async def run():
        async with AsyncSessionLocal() as session:
            # Setup user, profile, scholarship, and application
            user = User(email="test.student@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Chidi", "last_name": "Okonkwo", "citizenship": "Nigeria", "phone": "+2348012345678"},
                grades={"gpa": 4.85},
            )
            session.add(profile)

            schol = (await session.execute(select(Scholarship))).scalars().first()
            application = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="drafting",
                mode_used="autopilot",
            )
            session.add(application)
            await session.commit()

            draft = Draft(
                application_id=application.id,
                kind="statement",
                content="My application essay grounded in research facts.",
                version=1,
                source_facts=["University of Lagos degree"],
            )
            session.add(draft)
            await session.commit()

            # First submission run
            result1 = await run_submitter(
                application_id=application.id,
                session=session,
                mock_mode=True,
            )

            assert result1.status == "submitted"
            assert result1.confirmation_ref is not None
            assert result1.confirmation_ref.startswith("CONF-2026-")
            assert len(result1.screenshot_paths) > 0
            for ss_path in result1.screenshot_paths:
                assert os.path.exists(ss_path)

            # Check DB state
            app_after = await session.get(Application, application.id)
            assert app_after.status == "submitted"
            assert app_after.confirmation_ref == result1.confirmation_ref
            assert app_after.submitted_at is not None

            # Verify audit trail in application_events
            events = (
                await session.execute(
                    select(ApplicationEvent)
                    .where(ApplicationEvent.application_id == application.id)
                    .order_by(ApplicationEvent.created_at.asc())
                )
            ).scalars().all()
            event_types = [e.payload.get("to_status") for e in events]
            assert "submitting" in event_types
            assert "submitted" in event_types

            # SECOND RUN: Idempotency Check
            result2 = await run_submitter(
                application_id=application.id,
                session=session,
                mock_mode=True,
            )

            assert result2.status == "already_submitted"
            assert result2.confirmation_ref == result1.confirmation_ref

            # Ensure event count did NOT grow with redundant submission
            events_count_after = (
                await session.execute(
                    select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)
                )
            ).scalars().all()
            assert len(events_count_after) == len(events)

    asyncio.run(run())


def test_captcha_run_stops_cleanly_and_resumes():
    """Milestone 5 acceptance: CAPTCHA stops cleanly at needs_human, captures screenshot, and resumes after approval."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="captcha.user@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()
            application = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="approved",
                mode_used="review",
            )
            session.add(application)
            await session.commit()

            # 1. Trigger submission with CAPTCHA blocker encountered
            res_blocked = await run_submitter(
                application_id=application.id,
                session=session,
                mock_mode=True,
                simulated_blocker="captcha",
            )

            assert res_blocked.status == "needs_human"
            assert res_blocked.blocker_type == "captcha"
            assert len(res_blocked.screenshot_paths) > 0
            for ss_path in res_blocked.screenshot_paths:
                assert os.path.exists(ss_path)

            app_blocked = await session.get(Application, application.id)
            assert app_blocked.status == "needs_human"
            assert app_blocked.confirmation_ref is None

            # 2. Student solves CAPTCHA and resumes application
            app_resumed = await transition_application(
                application=app_blocked,
                new_status="submitting",
                actor="user",
                payload={"action": "captcha_solved_by_student"},
                session=session,
            )
            assert app_resumed.status == "submitting"

            # 3. Submitter runs without blocker and finishes successfully
            res_success = await run_submitter(
                application_id=application.id,
                session=session,
                mock_mode=True,
                simulated_blocker=None,
            )

            assert res_success.status == "submitted"
            assert res_success.confirmation_ref is not None
            assert res_success.confirmation_ref.startswith("CONF-2026-")

            app_final = await session.get(Application, application.id)
            assert app_final.status == "submitted"
            assert app_final.confirmation_ref == res_success.confirmation_ref

    asyncio.run(run())


def test_review_mode_enforces_student_approval_before_submitting():
    """Verifies that an application in ready_for_review cannot be submitted without student approval."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="review.user@example.com", mode="review", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship))).scalars().first()
            application = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="ready_for_review",
                mode_used="review",
            )
            session.add(application)
            await session.commit()

            # Attempting to submit in ready_for_review must raise IllegalStateTransitionError
            with pytest.raises(IllegalStateTransitionError):
                await run_submitter(
                    application_id=application.id,
                    session=session,
                    mock_mode=True,
                )

            # Once student approves, submission succeeds
            application = await transition_application(
                application=application,
                new_status="approved",
                actor="user",
                payload={"action": "student_approved_draft"},
                session=session,
            )
            assert application.status == "approved"

            res = await run_submitter(
                application_id=application.id,
                session=session,
                mock_mode=True,
            )
            assert res.status == "submitted"

    asyncio.run(run())
