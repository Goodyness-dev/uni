"""Real opt-in notification delivery; provider absence is never success."""
import asyncio
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from typing import Any
import httpx
import boto3
from botocore.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.tracing import trace_block
from app.db.models import Application, ApplicationEvent, Job, Profile, User
from app.jobs.queue import enqueue_job, register_job_handler


def email_configured() -> bool:
    if settings.EMAIL_PROVIDER == "ses":
        return bool(settings.SES_FROM and settings.SES_REGION)
    return bool(settings.SMTP_USER and settings.SMTP_APP_PASSWORD)


def send_ses_email(recipient: str, subject: str, body: str) -> dict[str, Any]:
    if not settings.SES_FROM:
        return {"ok": False, "reason": "ses_not_configured"}
    # Instance-role credentials in AWS; the default profile chain locally.
    # Queue retries own delivery retries, avoiding hidden duplicate SDK sends.
    client = boto3.Session(region_name=settings.SES_REGION).client("sesv2", config=Config(
        connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 1, "mode": "standard"}))
    try:
        response = client.send_email(FromEmailAddress=settings.SES_FROM,
            Destination={"ToAddresses": [recipient]}, Content={"Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}}}})
    except client.exceptions.MessageRejected:
        return {"ok": False, "reason": "ses_message_rejected"}
    except client.exceptions.MailFromDomainNotVerifiedException:
        return {"ok": False, "reason": "ses_sender_not_verified"}
    finally:
        client.close()
    message_id = response.get("MessageId")
    return {"ok": bool(message_id), "reason": "provider_accepted" if message_id else "provider_rejected",
        "message_id": message_id}


def send_email(recipient: str, subject: str, body: str) -> dict[str, Any]:
    if settings.EMAIL_PROVIDER == "ses":
        return send_ses_email(recipient, subject, body)
    if not settings.SMTP_USER or not settings.SMTP_APP_PASSWORD:
        return {"ok": False, "reason": "smtp_not_configured"}
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
        client.starttls(context=ssl.create_default_context())
        client.login(settings.SMTP_USER, settings.SMTP_APP_PASSWORD)
        refused = client.send_message(message)
    return {"ok": not refused, "reason": "provider_accepted" if not refused else "recipient_refused"}


async def deliver(channel: str, recipient: str, body: str) -> dict[str, Any]:
    if not settings.NOTIFICATIONS_ENABLED:
        return {"ok": False, "reason": "notifications_disabled"}
    with trace_block("notification_delivery", "TOOL", channel=channel):
        try:
            if channel == "email":
                return await asyncio.to_thread(send_email, recipient, "ScholarPilot notification", body)
            if channel != "telegram" or not settings.TELEGRAM_BOT_TOKEN:
                return {"ok": False, "reason": "telegram_not_configured"}
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post("https://api.telegram.org/bot" + settings.TELEGRAM_BOT_TOKEN + "/sendMessage",
                    json={"chat_id": recipient, "text": body, "disable_web_page_preview": True})
                response.raise_for_status()
                accepted = response.json().get("ok") is True
                return {"ok": accepted, "reason": "provider_accepted" if accepted else "provider_rejected"}
        except (httpx.HTTPError, smtplib.SMTPException, OSError):
            return {"ok": False, "reason": "provider_delivery_failed"}


async def queue_notifications(application: Application, session: AsyncSession) -> None:
    user = await session.get(User, application.user_id)
    profile = (await session.execute(select(Profile).where(Profile.user_id == application.user_id))).scalar_one_or_none()
    preferences = (profile.personal_details if profile else {}).get("_notifications", {})
    if not user or not settings.NOTIFICATIONS_ENABLED:
        return
    body = "ScholarPilot application update: " + application.status + ". Open your dashboard for details."
    for channel, recipient in (("email", preferences.get("email", user.email)), ("telegram", user.telegram_chat_id)):
        if preferences.get(channel + "_enabled") and recipient:
            existing = (await session.execute(select(Job).where(Job.type == "notification_delivery",
                Job.payload["application_id"].as_string() == str(application.id),
                Job.payload["state"].as_string() == application.status,
                Job.payload["channel"].as_string() == channel))).scalars().first()
            if not existing:
                await enqueue_job("notification_delivery", {"user_id": str(user.id), "application_id": str(application.id),
                    "state": application.status, "channel": channel, "recipient": recipient, "body": body}, session=session)


@register_job_handler("notification_delivery")
async def notification_job(job: Job, payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    user = await session.get(User, uuid.UUID(payload["user_id"]))
    if not user or user.status != "active":
        raise ValueError("Notification owner is inactive.")
    result = await deliver(payload["channel"], payload["recipient"], payload["body"])
    if payload.get("application_id"):
        session.add(ApplicationEvent(application_id=uuid.UUID(payload["application_id"]), actor="notifications",
            event_type="notification_delivery", payload={"channel": payload["channel"], **result}))
        await session.commit()
    if not result["ok"]:
        raise RuntimeError(result["reason"])
    job.payload = {**payload, "delivery_result": result}
    await session.commit()
    return result
