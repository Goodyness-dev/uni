"""Fictional regression cases and real-world boundary/recovery invariants, all offline."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from app.agents.verifier import deterministic_check
from app.agents.planner import adaptive_actions
from app.db.base import Base, engine, AsyncSessionLocal
from app.db.models import Job, ApplicationEvent
from app.services import public_pages, notifications
from app.services.discovery import deadline_observation, observe_pages
from app.core.config import settings
from backend.app.tracing import metadata_mask

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
