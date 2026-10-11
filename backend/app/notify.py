import httpx
from typing import Any

from app.config import settings
from app import db


def tpl_matches_found(n: int, name: str, score: int, top_n: int) -> str:
    return f"ScholarPilot: found {n} scholarships you qualify for. Top match: {name} (fit {score}). Researching the top {top_n} now."


def tpl_researched(name: str, k: int) -> str:
    return f"Researched {name}: {k} sourced facts about the programme. Looking for your strongest evidence."


def tpl_edges_used(edges: list[dict[str, Any]]) -> str:
    lines = []
    for e in edges[:3]:
        fact_id = e.get("fact_id", "")
        short_fact = e.get("short_fact", "")
        reason = e.get("reason", "")
        lines.append(f"Used {fact_id} ({short_fact}) because {reason}.")
    return "\n".join(lines)


def tpl_verified(name: str, supported: int, removed: int, overturned: int) -> str:
    return f"Verified {name}: {supported} claims supported, {removed} removed, {overturned} overturned by self challenge."


def tpl_submitted(name: str, code: str) -> str:
    return f"Submitted {name}. Confirmation: {code}."


def tpl_prepared(name: str, app_id: str) -> str:
    frontend_url = settings.frontend_base_url.rstrip("/")
    return f"{name} needs manual submission. Your package is ready: {frontend_url}/applications/{app_id}"


def tpl_handoff(name: str, app_id: str) -> str:
    frontend_url = settings.frontend_base_url.rstrip("/")
    return f"{name} needs you for a quick CAPTCHA. Open {frontend_url}/handoff/{app_id}, solve it, then tap Done."


def tpl_failed(name: str, step: str, reason: str) -> str:
    return f"{name} failed at {step}: {reason}."


def tpl_gap(name: str, question: str) -> str:
    return f"Optional question for {name}: {question} Answer it in the app to add it to your profile."


def tpl_restricted_briefing(name: str, deadline: str, days: int, edge_notes: str, app_id: str, source_url: str) -> str:
    frontend_url = settings.frontend_base_url.rstrip("/")
    return (
        f"{name}: briefing ready. Deadline {deadline} ({days} days left).\n"
        f"Rule: AI written essays are not allowed or not confirmed, so I did not write yours. "
        f"I prepared your CV draft, form answers, an essay outline with your own evidence, and a checklist.\n"
        f"Your strongest points: {edge_notes}\n"
        f"Open your pack: {frontend_url}/applications/{app_id}\n"
        f"Official page: {source_url}"
    )


def send_message_telegram(text: str) -> bool:
    """Sends a text message via Telegram Bot API if configured."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        resp = httpx.post(url, json={"chat_id": settings.telegram_chat_id, "text": text}, timeout=10.0)
        return resp.status_code == 200
    except Exception:
        return False


def send_event(app_id: str | None, kind: str, text: str, run_id: str | None = None) -> None:
    """Queues a notification and attempts sending if telegram is configured."""
    sent = send_message_telegram(text)
    db.add_notification(run_id=run_id, application_id=app_id, channel="telegram", text=text, sent=sent)
    if run_id:
        db.add_event(
            run_id=run_id,
            application_id=app_id,
            agent="notifier",
            type_="notification_sent" if sent else "notification_queued",
            message=text[:100],
            data={"kind": kind, "sent": sent},
        )


def retry_unsent() -> int:
    """Retries sending unsent notifications from the database."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return 0
    unsent = db.list_unsent_notifications()
    success_count = 0
    for notif in unsent:
        if send_message_telegram(notif["text"]):
            db.mark_notification_sent(notif["id"])
            success_count += 1
    return success_count


def on_status_change(app_id: str, new_status: str) -> None:
    """Optional hook invoked on application status change."""
    pass
