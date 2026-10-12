"""OIDC authorization code + PKCE using the existing verified key exchange."""
import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode
from typing import Annotated
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.base import get_db_session
from app.jobs.queue import get_redis_client
from app.api.v1.auth import CreateKeyRequest, create_api_key

router = APIRouter(prefix="/auth", tags=["Verified onboarding"])


@router.get("/authorize")
async def authorize() -> dict[str, str]:
    if not settings.OIDC_AUTHORIZATION_URL or not settings.OIDC_AUDIENCE or not settings.OIDC_TOKEN_URL:
        raise HTTPException(status_code=503, detail="Verified sign-in is not configured by the operator.")
    broker = await get_redis_client()
    if broker is None:
        raise HTTPException(status_code=503, detail="Sign-in requires the shared session broker.")
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    await broker.set("scholarpilot:oidc:" + state, json.dumps({"verifier": verifier, "nonce": nonce}), ex=300)
    query = {"response_type": "code", "client_id": settings.OIDC_AUDIENCE,
        "redirect_uri": settings.OIDC_REDIRECT_URI, "scope": "openid email", "state": state,
        "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
    return {"url": settings.OIDC_AUTHORIZATION_URL + "?" + urlencode(query), "state": state}


class Callback(BaseModel):
    state: str = Field(min_length=20, max_length=150, pattern=r"^[A-Za-z0-9_-]+$")
    code: str = Field(min_length=1, max_length=5000)


@router.post("/callback")
async def callback(value: Callback, db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
    broker = await get_redis_client()
    if broker is None or not settings.OIDC_TOKEN_URL:
        raise HTTPException(status_code=503, detail="Verified sign-in is unavailable.")
    saved = await broker.getdel("scholarpilot:oidc:" + value.state)
    if not saved:
        raise HTTPException(status_code=401, detail="Sign-in session expired or already used.")
    session = json.loads(saved)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(settings.OIDC_TOKEN_URL, data={"grant_type": "authorization_code",
                "client_id": settings.OIDC_AUDIENCE, "code": value.code,
                "redirect_uri": settings.OIDC_REDIRECT_URI, "code_verifier": session["verifier"]})
            response.raise_for_status()
        token = response.json()["id_token"]
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims.get("nonce") != session["nonce"]:
            raise ValueError("Nonce mismatch.")
        key = await create_api_key(CreateKeyRequest(email=claims["email"]), db,
            x_request_id=None, authorization="Bearer " + token)
        return {"api_key": key.api_key}
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Identity-provider sign-in could not be completed.")
