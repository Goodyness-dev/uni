"""Notification and Telegram polling daemon for ScholarPilot."""
import email
from email.message import EmailMessage
from pathlib import Path
import smtplib
import threading
import time
from typing import Any

import httpx

from app.config import settings
from app import db
from app.errors import RunContext, SmtpError
from app.tracing import tool_span, trace_block


# --- Message Templates ---
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


# --- Telegram Dispatcher ---
def send_telegram(
    text: str,
    ctx: RunContext | None = None,
    reply_markup: dict[str, Any] | None = None,
    run_id: str | None = None,
    app_id: str | None = None,
) -> bool:
    """Sends a Telegram message within a TOOL span.

    Always inserts a notifications row first with sent=0, then marks sent=1 on success.
    Never raises exceptions.
    """
    effective_run_id = (ctx.run_id if ctx else None) or run_id
    effective_app_id = (ctx.application_id or ctx.app_id if ctx else None) or app_id

    # Always write notification row first (sent = False)
    notif_id = db.add_notification(
        run_id=effective_run_id,
        application_id=effective_app_id,
        channel="telegram",
        text=text,
        sent=False,
    )

    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        if effective_run_id:
            db.add_event(
                run_id=effective_run_id,
                application_id=effective_app_id,
                agent="notifier",
                type_="notification_queued",
                message=text[:100],
                data={"channel": "telegram", "sent": False, "reason": "not_configured"},
            )
        return False

    with trace_block("send_telegram", "TOOL", tool_name="send_telegram", app_id=effective_app_id):
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": settings.telegram_chat_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            if resp.status_code == 200:
                db.mark_notification_sent(notif_id)
                if effective_run_id:
                    db.add_event(
                        run_id=effective_run_id,
                        application_id=effective_app_id,
                        agent="notifier",
                        type_="notification_sent",
                        message=text[:100],
                        data={"channel": "telegram", "sent": True},
                    )
                return True
            else:
                if effective_run_id:
                    db.add_event(
                        run_id=effective_run_id,
                        application_id=effective_app_id,
                        agent="notifier",
                        type_="notification_failed",
                        message=f"HTTP {resp.status_code}: {resp.text[:100]}",
                        data={"status_code": resp.status_code},
                    )
                return False
        except Exception as e:
            if effective_run_id:
                db.add_event(
                    run_id=effective_run_id,
                    application_id=effective_app_id,
                    agent="notifier",
                    type_="notification_failed",
                    message=f"Network exception: {str(e)}",
                    data={"error": str(e)},
                )
            return False


# Convenience wrapper
def send_message_telegram(text: str) -> bool:
    return send_telegram(text)


def send_event(app_id: str | None, kind: str, text: str, run_id: str | None = None) -> None:
    """Queues and attempts sending a typed event notification."""
    send_telegram(text, run_id=run_id, app_id=app_id)


# --- Email Dispatcher ---
def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    ctx: RunContext | None = None,
    run_id: str | None = None,
    app_id: str | None = None,
) -> None:
    """Sends an email via SMTP with STARTTLS inside a TOOL span. Raises SmtpError on failure."""
    effective_run_id = (ctx.run_id if ctx else None) or run_id
    effective_app_id = (ctx.application_id or ctx.app_id if ctx else None) or app_id

    # Check failure injection flag
    if db.consume_flag("smtp_fail"):
        if effective_run_id:
            db.add_event(
                run_id=effective_run_id,
                application_id=effective_app_id,
                agent="notifier",
                type_="failure_injected",
                message="Injected failure: smtp_fail",
                data={"flag": "smtp_fail"},
            )
        raise SmtpError("simulated failure")

    with trace_block("send_email", "TOOL", tool_name="send_email", recipient=to):
        msg = EmailMessage()
        msg["From"] = settings.smtp_user or "scholarpilot@demo.local"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        if attachments:
            for att_path_str in attachments:
                att_path = Path(att_path_str)
                if att_path.is_file():
                    content = att_path.read_bytes()
                    maintype = "application"
                    subtype = "pdf" if att_path.suffix == ".pdf" else "octet-stream"
                    msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=att_path.name)

        if not settings.smtp_configured:
            # If SMTP credentials not provided (e.g. test or offline demo)
            db.add_notification(
                run_id=effective_run_id,
                application_id=effective_app_id,
                channel="email",
                text=f"Subject: {subject}\n\n{body}",
                sent=True,
            )
            return

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10.0) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_app_password)
                server.send_message(msg)

            db.add_notification(
                run_id=effective_run_id,
                application_id=effective_app_id,
                channel="email",
                text=f"Subject: {subject}\n\n{body}",
                sent=True,
            )
        except Exception as e:
            db.add_notification(
                run_id=effective_run_id,
                application_id=effective_app_id,
                channel="email",
                text=f"Subject: {subject}\n\n{body}",
                sent=False,
            )
            raise SmtpError(f"SMTP error: {str(e)}") from e


# --- Status Change Hook ---
def on_status_change(app_id: str, new_status: str, ctx: RunContext | None = None) -> None:
    """Dispatches Telegram notifications automatically when application status updates."""
    app = db.get_application(app_id)
    if not app:
        return

    run_id = app.get("run_id")
    listing_id = app.get("listing_id", "")

    # Resolve listing name
    from app.agents import scout
    listing = scout.get_listing(listing_id)
    listing_name = listing.name if listing else listing_id

    if new_status == "awaiting_user":
        # Handoff message with inline keyboard Done & Open buttons
        text = tpl_handoff(listing_name, app_id)
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Done", "callback_data": f"done:{app_id}"},
                    {"text": "Open", "url": f"{settings.frontend_base_url.rstrip('/')}/handoff/{app_id}"},
                ]
            ]
        }
        send_telegram(text, ctx=ctx, reply_markup=reply_markup, run_id=run_id, app_id=app_id)

    elif new_status == "submitted":
        submission = app.get("submission") or {}
        code = submission.get("confirmation_code") or "PENDING"
        text = tpl_submitted(listing_name, code)
        send_telegram(text, ctx=ctx, run_id=run_id, app_id=app_id)

    elif new_status == "prepared":
        text = tpl_prepared(listing_name, app_id)
        send_telegram(text, ctx=ctx, run_id=run_id, app_id=app_id)

    elif new_status == "failed":
        reason = app.get("failure_reason") or "Application failed"
        text = tpl_failed(listing_name, "apply", reason)
        send_telegram(text, ctx=ctx, run_id=run_id, app_id=app_id)


# --- Unsent Notifications Retry ---
def retry_unsent() -> int:
    """Retries sending unsent notifications from the database."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return 0
    unsent = db.list_unsent_notifications()
    success_count = 0
    for notif in unsent:
        # Use direct post without re-inserting row
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": settings.telegram_chat_id, "text": notif["text"]}
        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            if resp.status_code == 200:
                db.mark_notification_sent(notif["id"])
                success_count += 1
        except Exception:
            pass
    return success_count


# --- Telegram Poller Daemon ---
_poller_thread: threading.Thread | None = None
_poller_stop_event = threading.Event()


def poll_telegram_once() -> None:
    """Executes a single polling iteration for Telegram updates."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return

    last_id = db.get_last_update_id()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    params = {"offset": last_id + 1, "timeout": 0}

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code != 200:
            return
        data = resp.json()
        updates = data.get("result", [])
    except Exception:
        return

    for upd in updates:
        upd_id = upd.get("update_id", 0)
        cq = upd.get("callback_query")
        if cq:
            cq_id = cq.get("id")
            cq_data = cq.get("data", "")
            if cq_data.startswith("done:"):
                app_id = cq_data.split("done:", 1)[1]
                with trace_block("telegram_callback", "TOOL", callback_data=cq_data, app_id=app_id):
                    # Resume application submission
                    try:
                        from app.agents import applier
                        if hasattr(applier, "resume_after_handoff"):
                            applier.resume_after_handoff(app_id)
                        else:
                            db.set_status(app_id, "submitting", "User confirmed CAPTCHA completion via Telegram Done button", agent="coordinator")
                    except Exception:
                        db.set_status(app_id, "submitting", "User confirmed CAPTCHA completion via Telegram Done button", agent="coordinator")

                    # Answer callback query
                    ans_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery"
                    try:
                        httpx.post(ans_url, json={"callback_query_id": cq_id, "text": "Resuming submission!"}, timeout=5.0)
                    except Exception:
                        pass

        if upd_id > last_id:
            last_id = upd_id
            db.set_last_update_id(last_id)


def start_poller(poll_interval: float = 3.0, stop_event: threading.Event | None = None) -> threading.Thread | None:
    """Starts the background Telegram polling daemon thread."""
    global _poller_thread, _poller_stop_event
    if stop_event:
        _poller_stop_event = stop_event

    if not settings.telegram_configured:
        return None

    def _loop() -> None:
        while not _poller_stop_event.is_set():
            try:
                poll_telegram_once()
            except Exception:
                pass
            time.sleep(poll_interval)

    _poller_thread = threading.Thread(target=_loop, daemon=True, name="TelegramPoller")
    _poller_thread.start()
    return _poller_thread
