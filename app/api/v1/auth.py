"""Authentication & API Key management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_request_id
from app.core.security import generate_api_key
from app.db.base import get_db_session
from app.db.models import ApiKey, User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class CreateKeyRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid email address")
    scopes: Optional[List[str]] = ["read", "write"]


class CreateKeyResponse(BaseModel):
    id: str
    api_key: str
    scopes: List[str]
    created_at: str
    note: str = "Store your API key securely. It cannot be displayed again."


class RevokeKeyResponse(BaseModel):
    id: str
    status: str
    revoked_at: str


@router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    req: CreateKeyRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> CreateKeyResponse:
    """Creates a new API key for a student or developer account."""
    req_id = get_request_id(x_request_id)

    # Find or create user by email
    stmt = select(User).where(User.email == req.email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        user = User(email=req.email, mode="autopilot", status="active")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    plain_key, hashed_key = generate_api_key()
    api_key_record = ApiKey(
        user_id=user.id,
        hashed_key=hashed_key,
        scopes=req.scopes or ["read", "write"],
    )
    db.add(api_key_record)
    await db.commit()
    await db.refresh(api_key_record)

    return CreateKeyResponse(
        id=str(api_key_record.id),
        api_key=plain_key,
        scopes=api_key_record.scopes,
        created_at=api_key_record.created_at.isoformat(),
    )


@router.delete("/keys/{key_id}", response_model=RevokeKeyResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> RevokeKeyResponse:
    """Revokes an API key owned by the authenticated user."""
    req_id = get_request_id(x_request_id)

    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    key_record = (await db.execute(stmt)).scalar_one_or_none()

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "KEY_NOT_FOUND", "message": "API key not found.", "request_id": req_id},
        )

    now = datetime.now(timezone.utc)
    key_record.revoked_at = now
    await db.commit()

    return RevokeKeyResponse(
        id=str(key_record.id),
        status="revoked",
        revoked_at=now.isoformat(),
    )
