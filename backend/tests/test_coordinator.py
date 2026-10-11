"""Tests for the Coordinator engine: run_step retries, fallbacks, metrics, and idempotency."""
import json
import pytest
from unittest.mock import MagicMock, patch

from app import db
from app.coordinator import compute_metrics, execute_run, run_step
from app.errors import BadJSONError, BlockerDetected, RateLimitError, RunContext
from app.models import (
    Claim,
    Dossier,
    DossierFact,
    Edge,
    Listing,
    Preferences,
    Segment,
    TailoredOutput,
    VerificationReport,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    test_db = tmp_path / "coordinator_test.db"
    monkeypatch.setenv("TEST_DB_PATH", str(test_db))
    monkeypatch.setenv("RETRY_SLEEP_SECONDS", "0")
    db.init_db()
    yield test_db


def test_run_step_retry_then_success():
    """run_step retries on retryable errors and returns on success."""
    ctx = RunContext(run_id="run_1", app_id="app_1", mode="A")
    calls = []

    def flaky_func():
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("Rate limit hit")
        return "success_val"

    result = run_step(ctx, "test_step", flaky_func)
    assert result == "success_val"
    assert len(calls) == 2

    # Check retry event logged
    events = db.list_events("run_1")
    assert any(e["type"] == "retry" for e in events)


def test_run_step_retry_exhausted_with_fallback():
    """run_step exhausts retries and calls fallback inside recovery decision."""
    ctx = RunContext(run_id="run_1", app_id="app_1", mode="A")

    def failing_func():
        raise BadJSONError("Broken JSON")

    def fallback_func():
        return "fallback_val"

    result = run_step(ctx, "test_step", failing_func, fallback=fallback_func)
    assert result == "fallback_val"

    # Check recovery decision event logged
    events = db.list_events("run_1")
    assert any(e["type"] == "recovery_decision" for e in events)


def test_run_step_non_retryable_blocker_detected():
    """BlockerDetected stops retries immediately and marks application failed."""
    run_id = db.create_run("A", 1)
    app_id = db.create_application(run_id, "mock_listing", "portal_captcha")
    ctx = RunContext(run_id=run_id, app_id=app_id, mode="A")

    def blocker_func():
        raise BlockerDetected("CAPTCHA wall found")

    result = run_step(ctx, "test_step", blocker_func)
    assert result is None

    app = db.get_application(app_id)
    assert app["status"] == "failed"
    assert "CAPTCHA" in app["failure_reason"]


def test_run_step_idempotency():
    """If step output already exists in db, run_step returns it without executing fn."""
    run_id = db.create_run("A", 1)
    app_id = db.create_application(run_id, "mock_listing", "portal_captcha")
    ctx = RunContext(run_id=run_id, app_id=app_id, mode="A")

    # Store a pre-existing dossier
    dossier = Dossier(
        listing_id="mock_listing",
        facts=[DossierFact(id="D1", topic="about", text="info", source_url="url", snippet="snip", retrieved_at="now")],
    )
    db.update_application(app_id, dossier=dossier.model_dump())

    fn_called = False
    def should_not_run():
        nonlocal fn_called
        fn_called = True
        return "new_dossier"

    cached_res = run_step(ctx, "research", should_not_run)
    assert not fn_called
    assert cached_res.listing_id == "mock_listing"
    assert len(cached_res.facts) == 1


def test_compute_metrics():
    """compute_metrics aggregates claims, unsupported claims, and events accurately."""
    run_id = db.create_run("A", 1)
    app_id = db.create_application(run_id, "mock_listing", "portal_captcha")

    # Setup application verification report
    vr = VerificationReport(
        rounds=1,
        claims=[
            Claim(id="CLM1", text="c1", segment_index=0, section="essay", verdict="supported"),
            Claim(id="CLM2", text="c2", segment_index=1, section="essay", verdict="unsupported"),
        ],
        unsupported_before=1,
        unsupported_final=1,
    )
    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[
            Segment(text="I applied to the University programme.", source_ids=["D1"], status="supported"),
        ],
    )
    db.update_application(app_id, verification=vr.model_dump(), tailored=tailored.model_dump())

    # Add some events
    db.add_event(run_id, app_id, "verifier", "retry", "Retry 1")
    db.add_event(run_id, app_id, "verifier", "recovery_decision", "Recovery")

    metrics = compute_metrics(run_id)
    assert metrics.claims_total == 2
    assert metrics.claims_unsupported == 1
    assert metrics.retries == 1
    assert metrics.recovery_decisions == 1
    assert metrics.personal_refs_total == 1
    assert metrics.personal_refs_sourced == 1
