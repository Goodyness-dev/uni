"""Authentication & API Key management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional, Literal
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_request_id
from app.core.security import generate_api_key
from app.core.config import settings
from app.db.base import get_db_session
from app.db.models import ApiKey, User, Profile
from app.core.identity import verify_identity
from cryptography.exceptions import InvalidSignature

router = APIRouter(prefix="/auth", tags=["Authentication"])


class CreateKeyRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid email address")
    scopes: List[Literal["read", "write"]] = Field(default_factory=lambda: ["read", "write"], min_length=1)


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
    authorization: Optional[str] = Header(None),
) -> CreateKeyResponse:
    """Creates a new API key for a student or developer account."""
    req_id = get_request_id(x_request_id)

    subject = None
    if settings.ENVIRONMENT == "production" or authorization:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="A verified identity token is required.")
        try:
            subject = await verify_identity(authorization[7:], req.email)
        except (ValueError, KeyError, TypeError, InvalidSignature):
            raise HTTPException(status_code=401, detail="Identity token validation failed.")
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Identity provider is unavailable.")

    # Find or create user by email
    canonical_email = req.email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == canonical_email).with_for_update()
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None and subject is None:
        raise HTTPException(status_code=409, detail="An existing identity cannot be recovered by email alone.")
    if user is not None and user.status != "active":
        raise HTTPException(status_code=403, detail="The identity is inactive.")
    if not user:
        user = User(email=canonical_email, mode="autopilot", status="active")
        db.add(user)
        await db.flush()

    if subject:
        profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one_or_none()
        if profile is None:
            profile = Profile(user_id=user.id, personal_details={"_identity_subject": subject})
            db.add(profile)
        elif profile.personal_details.get("_identity_subject") not in (None, subject):
            raise HTTPException(status_code=403, detail="Identity subject does not match this account.")
        else:
            profile.personal_details = {**profile.personal_details, "_identity_subject": subject}

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
