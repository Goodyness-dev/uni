"""Idempotent draft creation and authoritative confirmation on our demo portal."""
from typing import Any
from urllib.parse import urlsplit
import re
import httpx
from app.core.runtime import is_demo_portal


async def prepare_draft(portal_url: str, application_id: str, fields: dict[str, str]) -> str:
    if not is_demo_portal(portal_url):
        raise ValueError("Only our local demo portal can receive an application draft.")
    parsed = urlsplit(portal_url)
    if not parsed.path.startswith("/portal/apply/"):
        raise ValueError("Application URL must identify a demo portal listing.")
    listing_id = parsed.path.removeprefix("/portal/apply/")
    base = parsed.scheme + "://" + parsed.netloc
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.post(base + "/portal/api/draft", json={
            "listing_id": listing_id, "idempotency_key": application_id, "fields": fields,
        })
        response.raise_for_status()
        draft_url = response.json()["draft_url"]
        if not is_demo_portal(draft_url) or urlsplit(draft_url).netloc != parsed.netloc:
            raise ValueError("Portal returned a draft outside its permitted origin.")
        return draft_url


async def read_confirmation(draft_url: str) -> str | None:
    if not is_demo_portal(draft_url):
        raise ValueError("Confirmation must come from our local portal.")
    parsed = urlsplit(draft_url)
    if not parsed.path.startswith("/portal/draft/"):
        return None
    draft_id = parsed.path.removeprefix("/portal/draft/")
    base = parsed.scheme + "://" + parsed.netloc
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.get(base + "/portal/api/submissions/" + draft_id)
        response.raise_for_status()
        result = response.json()
        code = result.get("confirmation_code")
        return code if result.get("submitted") is True and isinstance(code, str) and re.fullmatch(r"DEMO\d{4}", code) else None
