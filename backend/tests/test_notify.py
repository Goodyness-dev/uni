"""Unit tests for notification templates, telegram/email dispatchers, and poller."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.config import settings
from app import db, notify
from app.errors import RunContext, SmtpError


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3000")
    db.init_db()


def test_template_wordings():
    # 1. matches_found
    t1 = notify.tpl_matches_found(3, "Merit Award", 85, 2)
    assert t1 == "ScholarPilot: found 3 scholarships you qualify for. Top match: Merit Award (fit 85). Researching the top 2 now."

    # 2. researched
    t2 = notify.tpl_researched("Merit Award", 5)
    assert t2 == "Researched {name}: {k} sourced facts about the programme. Looking for your strongest evidence.".format(name="Merit Award", k=5)

    # 3. edges_used
    edges = [
        {"fact_id": "C1", "short_fact": "3.8 GPA", "reason": "Academic excellence"},
        {"fact_id": "P2", "short_fact": "President", "reason": "Leadership"},
    ]
    t3 = notify.tpl_edges_used(edges)
    assert "Used C1 (3.8 GPA) because Academic excellence." in t3
    assert "Used P2 (President) because Leadership." in t3

    # 4. verified
    t4 = notify.tpl_verified("Merit Award", 10, 2, 1)
    assert t4 == "Verified Merit Award: 10 claims supported, 2 removed, 1 overturned by self challenge."

    # 5. submitted
    t5 = notify.tpl_submitted("Merit Award", "DEMO1234")
    assert t5 == "Submitted Merit Award. Confirmation: DEMO1234."

    # 6. prepared
    t6 = notify.tpl_prepared("Merit Award", "app_1")
    assert t6 == "Merit Award needs manual submission. Your package is ready: http://localhost:3000/applications/app_1"

    # 7. handoff
    t7 = notify.tpl_handoff("Merit Award", "app_1")
    assert t7 == "Merit Award needs you for a quick CAPTCHA. Open http://localhost:3000/handoff/app_1, solve it, then tap Done."

    # 8. failed
    t8 = notify.tpl_failed("Merit Award", "apply", "Timeout")
    assert t8 == "Merit Award failed at apply: Timeout."

    # 9. gap
    t9 = notify.tpl_gap("Merit Award", "Do you have robotics experience?")
    assert t9 == "Optional question for Merit Award: Do you have robotics experience? Answer it in the app to add it to your profile."

    # 10. restricted_briefing
    t10 = notify.tpl_restricted_briefing("Grant", "2026/11/01", 20, "Strong coding skills", "app_2", "https://grant.com")
    assert "Grant: briefing ready." in t10
    assert "Deadline 2026/11/01 (20 days left)." in t10


def test_send_telegram_success_and_failure(monkeypatch):
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal")

    # Fake successful HTTP response
    fake_resp = MagicMock()
    fake_resp.status_code = 200

    with patch("httpx.post", return_value=fake_resp) as mock_post:
        res = notify.send_telegram("Test Success", run_id=run_id, app_id=app_id)
        assert res is True
        mock_post.assert_called_once()
        assert "sendMessage" in mock_post.call_args[0][0]

    # Check notification row in DB is marked sent = 1
    notifs = db.list_notifications(app_id)
    assert len(notifs) >= 1
    assert notifs[-1]["sent"] is True

    # Fake failed HTTP response (e.g. 500)
    fake_fail_resp = MagicMock()
    fake_fail_resp.status_code = 500
    fake_fail_resp.text = "Internal Server Error"

    with patch("httpx.post", return_value=fake_fail_resp):
        res2 = notify.send_telegram("Test Fail", run_id=run_id, app_id=app_id)
        assert res2 is False

    # Check notification row in DB leaves sent = 0 and did not raise
    unsent = db.list_unsent_notifications()
    assert any(u["text"] == "Test Fail" and u["application_id"] == app_id for u in unsent)


def test_retry_unsent():
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal")

    # Add unsent notification manually
    notif_id = db.add_notification(run_id, app_id, "telegram", "Retry Me", sent=False)
    unsent_before = [u for u in db.list_unsent_notifications() if u["id"] == notif_id]
    assert len(unsent_before) == 1

    fake_resp = MagicMock()
    fake_resp.status_code = 200

    with patch("httpx.post", return_value=fake_resp):
        success_count = notify.retry_unsent()
        assert success_count >= 1

    unsent_after = [u for u in db.list_unsent_notifications() if u["id"] == notif_id]
    assert len(unsent_after) == 0


def test_send_email_and_failure_injection(monkeypatch):
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_email_award", "email")

    # Happy path without real SMTP credentials (offline/mock)
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    notify.send_email("recipient@demo.com", "Test Subject", "Body text", run_id=run_id, app_id=app_id)

    # Injected failure flag smtp_fail
    db.set_flag("smtp_fail", True, count=1)
    with pytest.raises(SmtpError, match="simulated failure"):
        notify.send_email("recipient@demo.com", "Test Subject", "Body text", run_id=run_id, app_id=app_id)


def test_on_status_change_handoff():
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_captcha_award", "portal_captcha")

    fake_resp = MagicMock()
    fake_resp.status_code = 200

    with patch("httpx.post", return_value=fake_resp) as mock_post:
        notify.on_status_change(app_id, "awaiting_user")
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert "quick CAPTCHA" in payload["text"]
        assert "reply_markup" in payload
        buttons = payload["reply_markup"]["inline_keyboard"][0]
        assert buttons[0]["text"] == "Done"
        assert buttons[0]["callback_data"] == f"done:{app_id}"
        assert buttons[1]["text"] == "Open"


def test_poll_telegram_once():
    run_id = db.create_run("B", 2)
    app_id = db.create_application(run_id, "mock_captcha_award", "portal_captcha")
    conn = db.get_connection()
    with conn:
        conn.execute("UPDATE applications SET status = 'awaiting_user' WHERE id = ?", (app_id,))
    conn.close()

    fake_get_resp = MagicMock()
    fake_get_resp.status_code = 200
    fake_get_resp.json.return_value = {
        "result": [
            {
                "update_id": 105,
                "callback_query": {
                    "id": "cq_999",
                    "data": f"done:{app_id}",
                },
            }
        ]
    }

    fake_post_resp = MagicMock()
    fake_post_resp.status_code = 200

    with patch("httpx.get", return_value=fake_get_resp):
        with patch("httpx.post", return_value=fake_post_resp) as mock_post:
            notify.poll_telegram_once()
            assert db.get_last_update_id() == 105

            # Application status should be transitioned to submitting
            updated_app = db.get_application(app_id)
            assert updated_app["status"] == "submitting"
            assert mock_post.called
