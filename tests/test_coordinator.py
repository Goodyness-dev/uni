"""Acceptance tests for Phase 4: Lifecycle Coordination, Human Handoff & Browser Automation."""
import asyncio
import os
import uuid
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents.submitter import run_submitter
from app.core.config import settings
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, ApplicationEvent, Draft, Job, Profile, Scholarship, User
from app.integrations.browser_runner import BrowserSubmissionResult, submit_portal
from app.jobs.coordinator import run_coordinator_pipeline
from app.jobs.queue import execute_job
from app.jobs.state_machine import KillSwitchActiveError
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


def test_coordinator_autopilot_pipeline_end_to_end():
    """Verifies that the coordinator connects discovered -> matched -> researching -> drafting -> submitter."""
    async def run():
        async with AsyncSessionLocal() as session:
            # 1. Create user and rich profile
            user = User(email="autopilot.coord@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Ifeoma", "last_name": "Eze", "citizenship": "Nigeria", "phone": "+2348011223344"},
                education_history=[{"institution": "University of Nigeria", "degree": "B.Sc. Electronic Engineering", "year": 2024}],
                grades={"gpa": 4.9, "gpa_scale": 5.0},
                achievements=[{"title": "Best Graduating Engineering Student", "year": 2024}],
                financial_need_info={"statement": "Underprivileged background requiring full financial scholarship."},
                target_countries=["UK", "Canada"],
                target_fields_of_study=["engineering", "computer science"],
            )
            session.add(profile)

            schol = (await session.execute(select(Scholarship).where(Scholarship.eligibility_rules["is_mock"].as_boolean() == True))).scalars().first()

            schol.application_url = "http://localhost:8000/portal/apply/fictional"
            schol.eligibility_rules = {**schol.eligibility_rules, "ai_policy": "allowed"}
            # 2. Start Application in discovered state
            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="discovered",
                mode_used="autopilot",
            )
            session.add(app_record)
            await session.commit()
            await session.refresh(app_record)

            # 3. Run coordinator pipeline
            coord_res = await run_coordinator_pipeline(app_record.id, session)

            assert coord_res["status"] == "drafting"
            assert coord_res["mode"] == "autopilot"
            assert "submission_job_id" in coord_res

            # 4. Verify drafted essay exists with verified source facts
            draft = (
                await session.execute(
                    select(Draft).where(Draft.application_id == app_record.id)
                )
            ).scalars().first()
            assert draft is not None
            assert len(draft.content) > 50
            assert len(draft.source_facts) > 0

            # 5. Execute enqueued submission job (using mock mode for sandbox)
            sub_job_id = uuid.UUID(coord_res["submission_job_id"])
            exec_res = await execute_job(sub_job_id, {"application_id": str(app_record.id), "mock_mode": True})
            assert exec_res["status"] == "submitted"
            assert exec_res["confirmation_ref"] is not None

            # Verify final database status
            await session.refresh(app_record)
            assert app_record.status == "submitted"
            assert app_record.submitted_at is not None

            # Verify complete audit event progression
            events = (
                await session.execute(
                    select(ApplicationEvent)
                    .where(ApplicationEvent.application_id == app_record.id)
                    .order_by(ApplicationEvent.created_at.asc())
                )
            ).scalars().all()
            event_types = [e.event_type for e in events]
            assert "status_changed_matched" in event_types
            assert "status_changed_researching" in event_types
            assert "status_changed_drafting" in event_types
            assert "status_changed_submitting" in event_types
            assert "status_changed_submitted" in event_types

    asyncio.run(run())


def test_coordinator_review_mode_pauses_at_ready_for_review():
    """Verifies that Review mode halts at ready_for_review and does NOT enqueue submission."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="review.coord@example.com", mode="review", status="active")
            session.add(user)
            await session.commit()

            profile = Profile(
                user_id=user.id,
                personal_details={"first_name": "Tari", "last_name": "Alagoa", "citizenship": "Nigeria"},
                education_history=[{"institution": "Rivers State University", "degree": "B.Sc. Mechanical Engineering"}],
                grades={"gpa": 4.6, "gpa_scale": 5.0},
                target_fields_of_study=["engineering"],
            )
            session.add(profile)

            schol = (await session.execute(select(Scholarship).where(Scholarship.eligibility_rules["is_mock"].as_boolean() == True))).scalars().first()

            app_record = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="discovered",
                mode_used="review",
            )
            session.add(app_record)
            await session.commit()

            # Run coordinator pipeline
            coord_res = await run_coordinator_pipeline(app_record.id, session)

            assert coord_res["status"] == "ready_for_review"
            assert coord_res["mode"] == "review"
            assert "submission_job_id" not in coord_res

            # Ensure application row is saved in ready_for_review
            await session.refresh(app_record)
            assert app_record.status == "ready_for_review"

            # Verify draft exists for user review
            draft = (
                await session.execute(
                    select(Draft).where(Draft.application_id == app_record.id)
                )
            ).scalars().first()
            assert draft is not None

    asyncio.run(run())


def test_rest_approve_enqueues_and_unreconciled_resume_stops():
    """Verifies that calling /approve and /resume enqueues submit_application jobs into the queue."""
    async def run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            key_resp = await client.post("/v1/auth/keys", json={"email": "coord.api@example.com"})
            api_key = key_resp.json()["api_key"]
            headers = {"X-API-Key": api_key}

            schol_resp = await client.get("/v1/scholarships", headers=headers)
            schol_id = schol_resp.json()["items"][0]["id"]

            # 1. Start application (which enqueues coordinator_pipeline)
            start_resp = await client.post(
                "/v1/applications",
                headers=headers,
                json={"scholarship_id": schol_id, "mode": "review"},
            )
            assert start_resp.status_code == 201
            app_id = start_resp.json()["id"]

            # 2. Fast-forward to ready_for_review
            async with AsyncSessionLocal() as session:
                app_obj = await session.get(Application, uuid.UUID(app_id))
                scholarship = await session.get(Scholarship, app_obj.scholarship_id)
                scholarship.application_url = "http://localhost:8000/portal/apply/fictional"
                scholarship.eligibility_rules = {**scholarship.eligibility_rules, "ai_policy": "allowed"}
                session.add(Draft(application_id=app_obj.id, kind="essay", content="Clearly fictional source evidence for review.", version=1))
                app_obj.status = "ready_for_review"
                await session.commit()

            # 3. Call approve endpoint
            appr_resp = await client.post(f"/v1/applications/{app_id}/approve", headers=headers)
            assert appr_resp.status_code == 200
            assert appr_resp.json()["status"] == "approved"

            # Check that a submit_application job was enqueued
            async with AsyncSessionLocal() as session:
                job_stmt = select(Job).where(Job.type == "submit_application").order_by(Job.created_at.desc())
                job = (await session.execute(job_stmt)).scalars().first()
                assert job is not None
                assert job.payload["application_id"] == app_id

                # Fast forward to needs_human to test resume
                app_obj = await session.get(Application, uuid.UUID(app_id))
                app_obj.status = "needs_human"
                await session.commit()

            # 4. Call resume endpoint
            resume_resp = await client.post(f"/v1/applications/{app_id}/resume", headers=headers)
            assert resume_resp.status_code == 409

            # Check that another submit_application job was enqueued
            async with AsyncSessionLocal() as session:
                jobs = (
                    await session.execute(
                        select(Job).where(Job.type == "submit_application").order_by(Job.created_at.desc())
                    )
                ).scalars().all()
                assert len(jobs) == 1

    asyncio.run(run())


def test_kill_switch_cancellation_guards():
    """Verifies that active kill switch halts submit_portal and run_submitter immediately."""
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="kill.coord@example.com", mode="autopilot", status="active")
            session.add(user)
            await session.commit()

            schol = (await session.execute(select(Scholarship).where(Scholarship.eligibility_rules["is_mock"].as_boolean() == True))).scalars().first()
            application = Application(
                user_id=user.id,
                scholarship_id=schol.id,
                status="drafting",
                mode_used="autopilot",
            )
            session.add(application)
            await session.commit()

            # Activate kill switch
            settings.KILL_SWITCH_ACTIVE = True
            try:
                # 1. submit_portal returns kill_switch blocker
                portal_res = await submit_portal(
                    portal_url="https://demo.portal/apply",
                    applicant_data={"first_name": "Test"},
                    draft_content="Essay",
                    mock_mode=False,
                )
                assert portal_res.success is False
                assert portal_res.is_blocked is True
                assert portal_res.blocker_type == "kill_switch"

                # 2. run_submitter raises KillSwitchActiveError
                with pytest.raises(KillSwitchActiveError):
                    await run_submitter(application.id, session=session, mock_mode=True)
            finally:
                settings.KILL_SWITCH_ACTIVE = False

    asyncio.run(run())
