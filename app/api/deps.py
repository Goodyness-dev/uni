"""FastAPI dependencies: authentication, request tracking, and error handlers."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import request_id_ctx
from app.core.security import hash_api_key
from app.db.base import get_db_session
from app.db.models import ApiKey, User


class APIError(Exception):
    """Custom application exception with structured error code and status."""
    def __init__(self, code: str, message: str, status_code: int = 400, details: Optional[dict] = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def get_request_id(x_request_id: Optional[str] = Header(None)) -> str:
    """Extracts or generates a unique request ID for the current request."""
    req_id = x_request_id or f"req_{uuid.uuid4().hex[:12]}"
    request_id_ctx.set(req_id)
    return req_id


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> User:
    """Authenticates the incoming request via API Key or Bearer token."""
    req_id = get_request_id(request.headers.get("X-Request-ID"))

    token = x_api_key
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Missing API key in 'X-API-Key' header or bearer token.",
                "request_id": req_id,
            },
        )

    # Hash the token and verify against active api_keys
    hashed = hash_api_key(token)
    stmt = select(ApiKey).where(ApiKey.hashed_key == hashed, ApiKey.revoked_at.is_(None))
    api_key_record = (await db.execute(stmt)).scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_API_KEY",
                "message": "API key is invalid, expired, or has been revoked.",
                "request_id": req_id,
            },
        )

    # Update last_used_at
    api_key_record.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    # Load associated user
    user = await db.get(User, api_key_record.user_id)
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "message": "The user account associated with this key is inactive.",
                "request_id": req_id,
            },
        )

    return user
