"""Offline tests for bounded agent decisions; all applicant data is fictional."""
import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.agents import planner
from app.agents.planner import AgentDecision, allowed_actions
from app.core.config import settings
from app.db.base import Base, engine, AsyncSessionLocal
from app.db.models import Application, ApplicationEvent, Scholarship, User, Draft, Job
from types import SimpleNamespace
from backend.app import llm
from app.agents.verifier import deterministic_check


@pytest.mark.parametrize("backup_overload", [False, True])
def test_overloaded_model_switches_once_without_bypassing_budget(monkeypatch: pytest.MonkeyPatch, backup_overload: bool) -> None:
    import httpx
    from app.core import llm_gateway
    calls: list[str] = []
    reservations: list[str] = []
    monkeypatch.setattr(settings, "AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fictional-test-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setattr(settings, "AGENT_FALLBACK_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 3)
    monkeypatch.setattr(llm_gateway, "circuit_breaker", llm_gateway.ProviderCircuitBreaker())
    monkeypatch.setattr(llm_gateway, "current_application_id", lambda: None)

    async def reserve(owner: str, amount: float) -> tuple[str, str, int]:
        reservations.append(owner)
        return ("global", "owner", 100000)

    async def settle(reservation: tuple[str, str, int], amount: float) -> None:
        return None

    async def complete(key: str, url: str, model: str, messages: list[dict[str, str]], temperature: float, capture: bool, timeout: float) -> dict:
        calls.append(model)
        if model == "gemini-3.5-flash-lite" or (backup_overload and calls.count(model) == 1):
            response = httpx.Response(503, request=httpx.Request("POST", "https://example.test"))
            raise httpx.HTTPStatusError("Synthetic overload", request=response.request, response=response)
        return {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 2}}

    monkeypatch.setattr(llm_gateway, "reserve_budget", reserve)
    monkeypatch.setattr(llm_gateway, "settle_budget", settle)
    monkeypatch.setattr(llm_gateway, "provider_completion", complete)
    async def sleep(seconds: float) -> None:
        assert seconds >= 2
    monkeypatch.setattr(llm_gateway.asyncio, "sleep", sleep)
    result = asyncio.run(llm_gateway.call_llm("Test", "Fictional fixture", user_id="fictional-owner"))
    assert calls == ["gemini-3.5-flash-lite", "gemini-2.5-flash-lite"] + (["gemini-2.5-flash-lite"] if backup_overload else [])
    assert reservations == ["fictional-owner"] * len(calls)
    assert result.fallback_used and result.model_used == "gemini-2.5-flash-lite"


def test_budget_failure_does_not_try_another_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import llm_gateway
    monkeypatch.setattr(settings, "AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fictional-test-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setattr(llm_gateway, "circuit_breaker", llm_gateway.ProviderCircuitBreaker())
    monkeypatch.setattr(llm_gateway, "current_application_id", lambda: None)

    async def reserve(owner: str, amount: float) -> tuple[str, str, int]:
        raise RuntimeError("Daily model budget is exhausted.")

    async def complete(*args: object, **kwargs: object) -> dict:
        pytest.fail("Provider must not run after budget denial")

    monkeypatch.setattr(llm_gateway, "reserve_budget", reserve)
    monkeypatch.setattr(llm_gateway, "provider_completion", complete)
    with pytest.raises(RuntimeError, match="budget is exhausted"):
        asyncio.run(llm_gateway.call_llm("Test", "Fictional fixture", user_id="fictional-owner"))


def test_tool_whitelist_requires_evidence_and_draft_before_finish():
    assert set(allowed_actions(False, False, False)) == {"research", "select_evidence"}
    assert allowed_actions(True, False, False) == ["select_evidence"]
    assert allowed_actions(False, True, False) == ["research"]
    assert allowed_actions(True, True, False) == ["draft_and_verify"]
    assert allowed_actions(True, True, True) == ["finish"]


@pytest.fixture
def agent_database():
    async def schema(create: bool) -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all if create else Base.metadata.drop_all)
    asyncio.run(schema(True))
    yield
    asyncio.run(schema(False))


async def fictional_application(session):
    user = User(email="fictional.agent@example.test")
    scholarship = Scholarship(title="Fictional award", provider="Fictional College", country="UK", level="masters",
        field="Engineering", amount=1, application_url="http://localhost:8000/portal/apply/fictional",
        eligibility_rules={"ai_policy": "allowed"})
    session.add_all([user, scholarship])
    await session.flush()
    application = Application(user_id=user.id, scholarship_id=scholarship.id, status="researching", mode_used="review")
    session.add(application)
    await session.commit()
    return application, scholarship


def test_no_supported_essay_requests_evidence_without_submission(agent_database: None) -> None:
    async def run() -> None:
        async with AsyncSessionLocal() as session:
            application, _ = await fictional_application(session)
            result = await planner.request_writing_evidence(application, session)
            assert result["status"] == "needs_human"
            events = (await session.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == application.id))).scalars().all()
            assert any(event.event_type == "recovery_decision" and event.payload["chosen"] == "request_evidence" for event in events)
            assert any(event.payload.get("blocker_type") == "missing_evidence" for event in events)
            jobs = (await session.execute(select(Job).where(Job.type == "submit_application"))).scalars().all()
            assert not jobs
    asyncio.run(run())


def test_agent_rejects_premature_finish_and_records_rejection(agent_database, monkeypatch):
    async def choose(*args):
        return AgentDecision(action="finish", reason="Invalid premature finish from a test double.")
    monkeypatch.setattr(planner, "invoke", choose)
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            with pytest.raises(ValueError, match="whitelist"):
                await planner.run_application_agent(application, scholarship, session)
            event = (await session.execute(select(ApplicationEvent))).scalars().one()
            assert event.payload["accepted"] is False
            assert application.status == "researching"
    asyncio.run(run())


def test_agent_limit_survives_retry(agent_database, monkeypatch):
    async def forbidden(*args):
        raise AssertionError("Exhausted agent must not call a provider.")
    monkeypatch.setattr(planner, "invoke", forbidden)
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            session.add_all([ApplicationEvent(application_id=application.id, actor="coordinator",
                event_type="agent_decision", payload={"iteration": i}) for i in range(settings.AGENT_MAX_DECISIONS)])
            await session.commit()
            with pytest.raises(RuntimeError, match="decision limit"):
                await planner.run_application_agent(application, scholarship, session)
    asyncio.run(run())


def test_agent_kill_switch_blocks_before_provider(agent_database, monkeypatch):
    monkeypatch.setattr(settings, "KILL_SWITCH_ACTIVE", True)
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            with pytest.raises(RuntimeError, match="Kill switch"):
                await planner.run_application_agent(application, scholarship, session)
    asyncio.run(run())


def test_agent_refuses_unknown_ai_policy(agent_database):
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            scholarship.eligibility_rules = {"ai_policy": "unknown"}
            with pytest.raises(ValueError, match="policy"):
                await planner.run_application_agent(application, scholarship, session)
    asyncio.run(run())


def test_sdk_normalizes_provider_thinking_tokens_before_tracing(monkeypatch):
    class Response:
        usage = SimpleNamespace(prompt_tokens=8, completion_tokens=4, total_tokens=154)

        def model_dump(self):
            return {"usage": vars(self.usage)}

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def create(self, **kwargs):
            return Response()

        async def close(self):
            return None

    monkeypatch.setattr(llm.openai, "AsyncOpenAI", Client)
    result = asyncio.run(llm.provider_completion("fictional-test-key", "https://example.test", "gemini-3-test",
        [{"role": "user", "content": "fictional test"}], 0, False, 10))
    assert result["usage"] == {"prompt_tokens": 8, "completion_tokens": 146, "total_tokens": 154}


def test_source_association_cannot_become_causation():
    source = "Eight of my students later entered a state science fair."
    assert not deterministic_check("My teaching resulted in eight students entering a state science fair.", [source])
    assert not deterministic_check("Volunteered as a teacher, resulting in eight students entering a state science fair.", [source])
    assert deterministic_check(source, [source])


def test_aspiration_cannot_become_completed_work():
    source = "I want to design low cost energy monitoring systems in Nigeria."
    assert not deterministic_check("My work focuses on low cost energy monitoring systems in Nigeria.", [source])
    assert not deterministic_check("I design low cost energy monitoring systems in Nigeria.", [source])
    assert deterministic_check(source, [source])


def test_literal_possessive_and_decimal_evidence_is_not_rejected():
    source = "I want a Master's in AI for energy systems."
    assert deterministic_check(source, [source])
    assert deterministic_check("I was on the Dean's list for 2 sessions.", ["I was on the Dean's list for 2 sessions."])


@pytest.mark.parametrize("mode,portal,queued", [
    ("autopilot", "http://localhost:8000/portal/apply/fictional", True),
    ("review", "http://localhost:8000/portal/apply/fictional", False),
    ("autopilot", "https://fictional.example.test/apply", False),
])
def test_agent_finish_respects_autonomy_and_portal(agent_database, mode, portal, queued):
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            application.status = "drafting"
            application.mode_used = mode
            user = await session.get(User, application.user_id)
            user.mode = mode
            scholarship.application_url = portal
            session.add(Draft(application_id=application.id, kind="essay", version=1,
                content="Fictional source-aligned fixture.", source_facts=["fixture-source"]))
            session.add(ApplicationEvent(application_id=application.id, actor="verifier", event_type="verification_report",
                payload={"report": {"unsupported_final": 0}}))
            await session.commit()
            result = await planner.finish_application(application, scholarship, session)
            jobs = (await session.execute(select(Job).where(Job.type == "submit_application"))).scalars().all()
            assert bool(result.get("submission_job_id")) == queued
            assert len(jobs) == int(queued)
            expected = "needs_human" if portal.startswith("https://") else "drafting" if queued else "ready_for_review"
            assert application.status == expected
            if queued:
                await planner.finish_application(application, scholarship, session)
                assert len((await session.execute(select(Job))).scalars().all()) == 1
    asyncio.run(run())


def test_agent_finish_refuses_unchecked_draft(agent_database):
    async def run():
        async with AsyncSessionLocal() as session:
            application, scholarship = await fictional_application(session)
            application.status = "drafting"
            application.mode_used = "autopilot"
            with pytest.raises(ValueError, match="source-checked"):
                await planner.finish_application(application, scholarship, session)
            assert not (await session.execute(select(Job))).scalars().all()
    asyncio.run(run())


def test_owner_autopilot_pause_only_blocks_automatic_submissions(monkeypatch):
    from app.core import runtime
    from conftest import FakeRedis
    broker = FakeRedis()
    async def client():
        return broker
    monkeypatch.setattr(runtime, "get_redis_client", client)
    async def run():
        await broker.set("scholarpilot:autopilot_paused:fictional-owner", "1")
        assert await runtime.submissions_stopped("fictional-owner", autonomous=True)
        assert not await runtime.submissions_stopped("fictional-other", autonomous=True)
        assert not await runtime.submissions_stopped("fictional-owner", autonomous=False)
    asyncio.run(run())
