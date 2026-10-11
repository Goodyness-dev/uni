"""Unit tests for the Applier agent, blocker detection, and handoff resume."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.agents import applier, scout
from app import db
from app.errors import RunContext
from app.models import Listing


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_check_blockers_html_fixtures():
    # 1. captcha_challenge element
    html_captcha = '<html><body><div id="captcha_challenge">Solve this</div></body></html>'
    mock_resp1 = MagicMock(text=html_captcha, url=MagicMock(path="/apply"), history=[])
    with patch("httpx.get", return_value=mock_resp1):
        blockers1 = applier.check_blockers("http://localhost:8000/portal/apply/mock_captcha")
        assert "captcha_challenge" in blockers1

    # 2. recaptcha iframe
    html_iframe = '<html><body><iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe></body></html>'
    mock_resp2 = MagicMock(text=html_iframe, url=MagicMock(path="/apply"), history=[])
    with patch("httpx.get", return_value=mock_resp2):
        blockers2 = applier.check_blockers("http://localhost:8000/portal/apply/mock_captcha")
        assert "captcha_iframe" in blockers2

    # 3. password input
    html_pwd = '<html><body><form><input type="password" name="pass" /></form></body></html>'
    mock_resp3 = MagicMock(text=html_pwd, url=MagicMock(path="/apply"), history=[])
    with patch("httpx.get", return_value=mock_resp3):
        blockers3 = applier.check_blockers("http://localhost:8000/portal/apply/mock_login")
        assert "password_input" in blockers3

    # 4. clean page (no blockers)
    html_clean = '<html><body><form><input type="text" name="name" /></form></body></html>'
    mock_resp4 = MagicMock(text=html_clean, url=MagicMock(path="/apply"), history=[])
    with patch("httpx.get", return_value=mock_resp4):
        blockers4 = applier.check_blockers("http://localhost:8000/portal/apply/clean")
        assert len(blockers4) == 0


def test_apply_package_only_and_notes_only():
    run_id = db.create_run("B", 2)
    # real_one is package_only
    app_id = db.create_application(run_id, "real_one", "package_only")
    ctx = RunContext(run_id=run_id, app_id=app_id)

    outcome = applier.apply(app_id, ctx)
    assert outcome == "prepared"


def test_apply_email_path(monkeypatch):
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_email_award", "email")
    ctx = RunContext(run_id=run_id, app_id=app_id)

    with patch("app.notify.send_email", return_value=None) as mock_send_email:
        outcome = applier.apply(app_id, ctx)
        assert outcome == "submitted"
        assert mock_send_email.called

    app_data = db.get_application(app_id)
    sub = app_data.get("submission") or {}
    assert sub.get("confirmed") is True
    assert sub.get("confirmation_code", "").startswith("EMAIL")


def test_apply_portal_with_captcha_blocker():
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_captcha_award", "portal_captcha")
    ctx = RunContext(run_id=run_id, app_id=app_id)

    # Fake draft response
    draft_mock_resp = MagicMock()
    draft_mock_resp.json.return_value = {"draft_id": "draft_cap_123", "draft_url": "http://localhost:8000/portal/draft/draft_cap_123"}

    # Fake submissions endpoint (not submitted yet)
    sub_mock_resp = MagicMock()
    sub_mock_resp.json.return_value = {"submitted": False}

    # Fake blocker scan returning captcha_challenge
    html_cap = '<html><body><div id="captcha_challenge">What is 7 plus 5?</div></body></html>'
    blocker_mock_resp = MagicMock(text=html_cap, url=MagicMock(path="/apply"), history=[])

    def fake_get(url, *args, **kwargs):
        if "submissions" in url:
            return sub_mock_resp
        return blocker_mock_resp

    with patch("httpx.post", return_value=draft_mock_resp):
        with patch("httpx.get", side_effect=fake_get):
            outcome = applier.apply(app_id, ctx)
            assert outcome == "awaiting_user"

    app_data = db.get_application(app_id)
    handoff = app_data.get("handoff") or {}
    assert handoff.get("reason") == "captcha"
    assert handoff.get("draft_id") == "draft_cap_123"

    # Check recovery_decision event was logged
    events = db.list_application_events(app_id)
    assert any(e["type"] == "recovery_decision" and e["data"].get("chosen") == "handoff" for e in events)


def test_resume_after_handoff_true_and_false():
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_captcha_award", "portal_captcha")

    # Put application in awaiting_user with handoff json
    conn = db.get_connection()
    with conn:
        conn.execute(
            "UPDATE applications SET status = 'awaiting_user', handoff_json = ? WHERE id = ?",
            (json.dumps({"draft_id": "draft_res_999", "reason": "captcha"}), app_id),
        )
    conn.close()

    # 1. False branch: submission not confirmed on portal yet
    not_confirmed_resp = MagicMock()
    not_confirmed_resp.json.return_value = {"submitted": False}

    with patch("httpx.get", return_value=not_confirmed_resp):
        res_false = applier.resume_after_handoff(app_id)
        assert res_false is False
        # Remains in awaiting_user
        app_after_false = db.get_application(app_id)
        assert app_after_false["status"] == "awaiting_user"

    # 2. True branch: submission confirmed with code
    confirmed_resp = MagicMock()
    confirmed_resp.json.return_value = {"submitted": True, "confirmation_code": "DEMO9999"}

    with patch("httpx.get", return_value=confirmed_resp):
        res_true = applier.resume_after_handoff(app_id)
        assert res_true is True
        app_after_true = db.get_application(app_id)
        assert app_after_true["status"] == "submitted"
        assert (app_after_true.get("submission") or {}).get("confirmation_code") == "DEMO9999"
