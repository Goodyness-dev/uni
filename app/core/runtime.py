"""Shared submission leases and emergency stop checks."""
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from app.core.config import settings
from app.jobs.queue import get_redis_client


async def submissions_stopped() -> bool:
    """Read the configured flag and the shared Redis runtime stop key."""
    if settings.KILL_SWITCH_ACTIVE:
        return True
    client = await get_redis_client()
    if client is None:
        return settings.ENVIRONMENT == "production"
    return await client.get("scholarpilot:kill_switch") in ("1", "true", "on", b"1")


def is_demo_portal(url: str) -> bool:
    """Only the local demo portal can receive browser submissions."""
    parsed = urlsplit(url)
    return (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.port in {None, 8000} and parsed.path.startswith("/portal/")
        and parsed.username is None and parsed.password is None
    )


@asynccontextmanager
async def submission_lease(application_id: UUID) -> AsyncIterator[None]:
    """Fail closed without a broker; token release cannot unlock another worker."""
    client = await get_redis_client()
    if client is None:
        raise RuntimeError("Submission requires Redis for an exclusive application lease.")
    key = f"scholarpilot:submission:{application_id}"
    token = uuid4().hex
    if not await client.set(key, token, nx=True, ex=300):
        raise RuntimeError("Another worker already holds this application's submission lease.")
    try:
        yield
    finally:
        await client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1, key, token,
        )
