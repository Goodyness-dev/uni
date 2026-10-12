"""Regression tests for production repairs using clearly fictional fixtures."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import httpx
from sqlalchemy import select, text
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.runtime import is_demo_portal, submission_lease, submissions_stopped
from app.core.budget import reserve_budget, settle_budget
from app.core.storage import managed_document_path, remove_managed_file
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Application, ApplicationEvent, Draft, Job, Profile, Scholarship, User
from app.jobs import queue
from app.jobs.coordinator import run_coordinator_pipeline
from app.agents.verifier import run_verifier
from app.agents.submitter import run_submitter
from app.main import app
from app.services.scheduler import schedule_daily_cycles


@pytest.fixture(autouse=True)
def isolated_database():
    async def setup():
        async with engine.begin() as connection:
            await connection.execute(text("PRAGMA foreign_keys=ON"))
            await connection.run_sync(Base.metadata.create_all)
    async def teardown():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    asyncio.run(setup())
    yield
    asyncio.run(teardown())


def test_external_document_paths_are_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    owner, other = uuid4(), uuid4()
    file = Path("storage/documents") / str(owner) / "cv.txt"
    file.parent.mkdir(parents=True)
    file.write_text("Fictional applicant document")
    assert managed_document_path(owner, str(file)) == file.resolve()
    with pytest.raises(ValueError):
        managed_document_path(other, str(file))
    outside = tmp_path / "important.txt"
    outside.write_text("Must survive deletion")
    assert not remove_managed_file(outside, file.parent)
    assert outside.exists()
    with pytest.raises(ValueError):
        managed_document_path(owner, str(outside))


def test_public_portals_cannot_receive_submissions():
    assert is_demo_portal("http://localhost:8000/portal/apply/fictional")
    for url in ("https://real.example/portal/apply", "http://localhost.evil/portal/apply",
                "http://localhost:8000/private", "http://user@localhost:8000/portal/apply"):
        assert not is_demo_portal(url)


def test_topical_overlap_does_not_prove_experience():
    source = ["I studied engineering."]
    clean, report = run_verifier("I have decades of engineering experience. I studied engineering.", source)
    assert clean == "I studied engineering."
    assert len(report.removed_claims) == 1
    _, empty = run_verifier("I patented engineering systems.", source)
    assert empty.passed is False


def test_concurrent_submission_lease_excludes_second_worker():
    async def run():
        application_id = uuid4()
        async with submission_lease(application_id):
            with pytest.raises(RuntimeError):
                async with submission_lease(application_id):
                    pytest.fail("Two workers acquired the same lease")
        async with submission_lease(application_id):
            pass
    asyncio.run(run())


def test_job_claims_are_unique_and_respect_scheduled_time():
    async def run():
        job = await queue.enqueue_job("unused", {"fictional": True})
        delayed = await queue.enqueue_job("unused", {}, datetime.now(timezone.utc) + timedelta(hours=1))
        first, second = await asyncio.gather(queue.fetch_next_pending_job("one"), queue.fetch_next_pending_job("two"))
        claimed = [entry.id for entry in (first, second) if entry]
        assert claimed == [job.id]
        assert delayed.id not in claimed
    asyncio.run(run())


def test_internal_jobs_retry_then_dead_letter(monkeypatch):
    async def fail(job, payload, session):
        raise ValueError("Fictional failure")
    monkeypatch.setitem(queue._JOB_HANDLERS, "fictional_failure", fail)
    async def run():
        job = await queue.enqueue_job("fictional_failure", {})
        for attempt in range(1, 4):
            with pytest.raises(ValueError):
                await queue.execute_job(job.id)
            async with AsyncSessionLocal() as session:
                stored = await session.get(Job, job.id)
                assert stored.attempts == attempt
                assert stored.status == ("dead_letter" if attempt == 3 else "pending")
                if attempt < 3:
                    assert stored.scheduled_for is not None
    asyncio.run(run())


def test_daily_cycles_are_deduplicated_by_local_date():
    async def run():
        async with AsyncSessionLocal() as session:
            session.add(User(email="fictional.scheduler@example.com", timezone="Africa/Lagos"))
            await session.commit()
            now = datetime(2026, 10, 12, 22, 30, tzinfo=timezone.utc)
            assert await schedule_daily_cycles(session, now) == 1
            assert await schedule_daily_cycles(session, now) == 0
            assert await schedule_daily_cycles(session, now + timedelta(hours=2)) == 1
    asyncio.run(run())


def test_ineligible_application_never_drafts_or_submits():
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="fictional.ineligible@example.com")
            scholarship = Scholarship(title="Fictional award", provider="Fictional school", country="UK",
                level="masters", field="engineering", application_url="http://localhost:8000/portal/apply/test",
                eligibility_rules={"eligible_nationalities": ["Canada"]})
            session.add_all([user, scholarship])
            await session.commit()
            session.add(Profile(user_id=user.id, personal_details={"nationalities": ["Nigeria"]}))
            application = Application(user_id=user.id, scholarship_id=scholarship.id)
            session.add(application)
            await session.commit()
            result = await run_coordinator_pipeline(application.id, session)
            assert result["status"] == "withdrawn"
            assert (await session.execute(select(Draft))).scalars().all() == []
            assert (await session.execute(select(Job))).scalars().all() == []
    asyncio.run(run())


def test_existing_email_cannot_issue_new_identity_key():
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/v1/auth/keys", json={"email": "fictional.identity@example.com"})).status_code == 201
            assert (await client.post("/v1/auth/keys", json={"email": "fictional.identity@example.com"})).status_code == 409
    asyncio.run(run())


def test_missing_draft_cannot_submit():
    async def run():
        async with AsyncSessionLocal() as session:
            user = User(email="fictional.empty@example.com")
            scholarship = Scholarship(title="Fictional award", provider="Fictional school", country="UK", level="masters",
                field="engineering", application_url="http://localhost:8000/portal/apply/test")
            session.add_all([user, scholarship])
            await session.commit()
            application = Application(user_id=user.id, scholarship_id=scholarship.id, status="approved")
            session.add(application)
            await session.commit()
            with pytest.raises(ValueError, match="draft"):
                await run_submitter(application.id, session, mock_mode=True)
            assert application.confirmation_ref is None
    asyncio.run(run())


def test_budget_reservations_share_caps_and_settle(monkeypatch, offline_services):
    from app.core import budget
    async def broker():
        return offline_services
    monkeypatch.setattr(budget, "get_redis_client", broker)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.01)
    monkeypatch.setattr(settings, "GLOBAL_DAILY_SPEND_CAP_USD", 0.01)
    async def run():
        reservation = await reserve_budget("fictional_owner", 0.008)
        with pytest.raises(RuntimeError, match="budget"):
            await reserve_budget("fictional_other", 0.008)
        await settle_budget(reservation, 0.001)
        await reserve_budget("fictional_other", 0.008)
    asyncio.run(run())


def test_shared_kill_switch_blocks_another_process(offline_services):
    async def run():
        assert await submissions_stopped() is False
        await offline_services.set("scholarpilot:kill_switch", "1")
        assert await submissions_stopped() is True
        await offline_services.delete("scholarpilot:kill_switch")
        await offline_services.set("scholarpilot:user_deleted:fictional_owner", "1")
        assert await submissions_stopped("fictional_owner") is True
        assert await submissions_stopped("fictional_other") is False
    asyncio.run(run())


def test_erasure_preserves_external_files_and_handles_audit_foreign_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "must_survive.txt"
    outside.write_text("Not owned by the applicant")
    async def run():
        from app.api.v1.account import delete_student_account
        from app.db.models import Document
        async with AsyncSessionLocal() as session:
            user = User(email="fictional.erase@example.com")
            scholarship = Scholarship(title="Fictional award", provider="Fictional school", country="UK", level="masters",
                field="engineering", application_url="http://localhost:8000/portal/apply/test")
            session.add_all([user, scholarship])
            await session.commit()
            application = Application(user_id=user.id, scholarship_id=scholarship.id, status="approved")
            session.add(application)
            await session.commit()
            session.add(ApplicationEvent(application_id=application.id, actor="test", event_type="fictional_event", payload={}))
            session.add(Document(user_id=user.id, type="cv", storage_key=str(outside)))
            await session.commit()
            await delete_student_account(user, session)
            assert outside.exists()
            assert (await session.execute(select(ApplicationEvent))).scalars().all() == []
            assert (await session.execute(select(Application))).scalars().all() == []
    asyncio.run(run())


def test_demo_confirmation_is_read_back_not_invented(monkeypatch):
    from app.integrations import demo_portal
    original_client = httpx.AsyncClient
    portal_state = {"submitted": False, "confirmation_code": None}
    def handle(request):
        if request.method == "POST":
            return httpx.Response(201, json={"draft_url": "http://localhost:8000/portal/draft/fictional123"})
        return httpx.Response(200, json=portal_state)
    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(demo_portal.httpx, "AsyncClient", client)
    async def run():
        draft_url = await demo_portal.prepare_draft("http://localhost:8000/portal/apply/fictional", "fictional_app", {"essay": "Original fictional fixture"})
        assert await demo_portal.read_confirmation(draft_url) is None
        portal_state.update(submitted=True, confirmation_code="confirmation required")
        assert await demo_portal.read_confirmation(draft_url) is None
        portal_state["confirmation_code"] = "DEMO1234"
        assert await demo_portal.read_confirmation(draft_url) == "DEMO1234"
    asyncio.run(run())
