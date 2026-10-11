"""User settings management endpoints."""
from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db_session
from app.db.models import User

router = APIRouter(prefix="/settings", tags=["Settings"])


class UserSettingsPayload(BaseModel):
    mode: Optional[Literal["autopilot", "review"]] = None
    timezone: Optional[str] = Field(None, max_length=64)
    telegram_chat_id: Optional[str] = Field(None, max_length=64)


class UserSettingsResponse(BaseModel):
    user_id: str
    email: str
    mode: str
    timezone: str
    telegram_chat_id: Optional[str] = None


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    user: Annotated[User, Depends(get_current_user)],
) -> UserSettingsResponse:
    """Retrieves autonomy mode and notification settings for authenticated user."""
    return UserSettingsResponse(
        user_id=str(user.id),
        email=user.email,
        mode=user.mode,
        timezone=user.timezone,
        telegram_chat_id=user.telegram_chat_id,
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    payload: UserSettingsPayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserSettingsResponse:
    """Updates autonomy mode (autopilot vs review) and preferences."""
    if payload.mode is not None:
        user.mode = payload.mode
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.telegram_chat_id is not None:
        user.telegram_chat_id = payload.telegram_chat_id

    await db.commit()
    await db.refresh(user)

    return UserSettingsResponse(
        user_id=str(user.id),
        email=user.email,
        mode=user.mode,
        timezone=user.timezone,
        telegram_chat_id=user.telegram_chat_id,
    )
