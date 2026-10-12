"""Telegram bot notification integration for ScholarPilot."""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from app.core.logging import logger


def format_blocker_alert(
    scholarship_title: str,
    blocker_type: str,
    blocker_message: str,
    portal_url: Optional[str] = None,
) -> str:
    """Formats human handoff notification when an automated portal blocker is encountered."""
    url_line = f"\n🔗 *Portal*: {portal_url}" if portal_url else ""
    return (
        f"🚨 *ScholarPilot Action Required: Human Verification*\n\n"
        f"Scholarship: *{scholarship_title}*\n"
        f"Blocker Type: `{blocker_type}`\n"
        f"Details: {blocker_message}{url_line}\n\n"
        f"👉 Please open the portal or review the dashboard screenshot to resolve the challenge, "
        f"then click *Resume* to complete your submission."
    )


def format_submission_alert(
    scholarship_title: str,
    confirmation_ref: str,
    submitted_at: datetime,
) -> str:
    """Formats student notification upon successful portal submission."""
    ts_str = submitted_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"🎉 *Scholarship Application Successfully Submitted!*\n\n"
        f"Scholarship: *{scholarship_title}*\n"
        f"Confirmation Code: `{confirmation_ref}`\n"
        f"Submitted At: {ts_str}\n\n"
        f"Your application record and evidence screenshots have been preserved in your audit timeline."
    )


def format_deadline_alert(
    scholarship_title: str,
    days_remaining: int,
    deadline_str: str,
    application_status: str,
) -> str:
    """Formats proactive deadline urgency reminder (7d, 3d, 1d)."""
    urgency_emoji = "⚠️" if days_remaining > 1 else "🔥"
    return (
        f"{urgency_emoji} *Urgent Deadline Warning: {days_remaining} Day{'s' if days_remaining != 1 else ''} Left!*\n\n"
        f"Scholarship: *{scholarship_title}*\n"
        f"Deadline: *{deadline_str}*\n"
        f"Current Status: `{application_status}`\n\n"
        f"Action: Review your tailored materials and submit prior to cutoff."
    )


def format_daily_digest(
    new_matches_count: int,
    pending_reviews_count: int,
    upcoming_deadlines: List[Dict[str, Any]],
) -> str:
    """Formats daily student summary digest."""
    deadlines_text = ""
    if upcoming_deadlines:
        deadlines_text = "\n*Upcoming Deadlines:*\n" + "\n".join(
            f"• *{d['title']}* ({d['days_remaining']}d remaining)" for d in upcoming_deadlines[:5]
        )
    else:
        deadlines_text = "\n*Upcoming Deadlines:* No critical deadlines in the next 7 days."

    return (
        f"☀️ *ScholarPilot Daily Briefing*\n\n"
        f"• New Matching Opportunities: *{new_matches_count}*\n"
        f"• Applications Awaiting Review: *{pending_reviews_count}*{deadlines_text}\n\n"
        f"Have a productive day! Check your dashboard for details."
    )


async def send_telegram_message(
    chat_id: str,
    text: str,
    bot_token: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Sends Markdown formatted message via Telegram Bot API or mock dispatcher."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token or token.lower() in ("mock", "test", "none"):
        logger.info(f"Telegram notification dispatched [MOCK to chat {chat_id}]: {text[:60]}...")
        return {"ok": False, "mock": False, "error": "telegram_not_configured"}

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        own_client = True

    try:
        resp = await client.post(api_url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to deliver Telegram notification to {chat_id}: {e}")
        return {"ok": False, "error": str(e), "chat_id": chat_id}
    finally:
        if own_client:
            await client.aclose()
