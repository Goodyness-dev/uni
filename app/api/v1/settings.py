"""User settings management endpoints."""
from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db_session
from app.db.models import User, Profile
from sqlalchemy import select
from app.jobs.queue import enqueue_job
from app.core.config import settings
from app.jobs.queue import get_redis_client
from app.services.notifications import email_configured

router = APIRouter(prefix="/settings", tags=["Settings"])


class UserSettingsPayload(BaseModel):
    mode: Optional[Literal["autopilot", "review"]] = None
    timezone: Optional[str] = Field(None, max_length=64)
    telegram_chat_id: Optional[str] = Field(None, max_length=64)
    notification_email: Optional[str] = Field(None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    email_notifications: Optional[bool] = None
    telegram_notifications: Optional[bool] = None


class UserSettingsResponse(BaseModel):
    user_id: str
    email: str
    mode: str
    timezone: str
    telegram_chat_id: Optional[str] = None
    notification_email: Optional[str] = None
    email_notifications: bool = False
    telegram_notifications: bool = False
    email_ready: bool = False
    telegram_ready: bool = False


@router.get("", response_model=UserSettingsResponse)
async def get_settings(user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> UserSettingsResponse:
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
    preferences = (profile.personal_details if profile else {}).get("_notifications", {})
    return UserSettingsResponse(user_id=str(user.id), email=user.email, mode=user.mode,
        timezone=user.timezone, telegram_chat_id=user.telegram_chat_id,
        notification_email=preferences.get("email", user.email), email_notifications=bool(preferences.get("email_enabled")),
        telegram_notifications=bool(preferences.get("telegram_enabled")),
        email_ready=bool(settings.NOTIFICATIONS_ENABLED and email_configured()),
        telegram_ready=bool(settings.NOTIFICATIONS_ENABLED and settings.TELEGRAM_BOT_TOKEN))


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    payload: UserSettingsPayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserSettingsResponse:
    """Updates autonomy mode (autopilot vs review) and preferences."""
    if payload.mode is not None:
        broker = await get_redis_client()
        if broker is None:
            raise HTTPException(status_code=503, detail="Autopilot controls require the shared worker broker.")
        pause_key = "scholarpilot:autopilot_paused:" + str(user.id)
        if payload.mode == "review":
            await broker.set(pause_key, "1")
        else:
            await broker.delete(pause_key)
        user.mode = payload.mode
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.telegram_chat_id is not None:
        user.telegram_chat_id = payload.telegram_chat_id

    if any(value is not None for value in (payload.notification_email, payload.email_notifications, payload.telegram_notifications)):
        profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
        if profile is None:
            profile = Profile(user_id=user.id, personal_details={})
            db.add(profile)
        preferences = dict(profile.personal_details.get("_notifications", {}))
        for key, value in (("email", payload.notification_email), ("email_enabled", payload.email_notifications), ("telegram_enabled", payload.telegram_notifications)):
            if value is not None:
                preferences[key] = value
        profile.personal_details = {**profile.personal_details, "_notifications": preferences}

    await db.commit()
    await db.refresh(user)

    return await get_settings(user, db)


class NotificationTest(BaseModel):
    channel: Literal["email", "telegram"]


@router.post("/test-notification", status_code=202)
async def test_notification(payload: NotificationTest, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
    current = await get_settings(user, db)
    enabled = current.email_notifications if payload.channel == "email" else current.telegram_notifications
    ready = current.email_ready if payload.channel == "email" else current.telegram_ready
    recipient = current.notification_email if payload.channel == "email" else user.telegram_chat_id
    if not enabled or not ready or not recipient:
        raise HTTPException(status_code=409, detail="Save and enable a configured notification destination first.")
    job = await enqueue_job("notification_delivery", {"user_id": str(user.id), "channel": payload.channel,
        "recipient": recipient, "body": "ScholarPilot connection test. Notification delivery is configured; no applicant documents are included."}, session=db)
    return {"job_id": str(job.id), "status": "queued"}
