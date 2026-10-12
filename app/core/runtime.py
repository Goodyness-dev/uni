"""Shared submission leases and emergency stop checks."""
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import asyncio
from contextvars import ContextVar
from typing import Any

from app.core.config import settings
from app.jobs.queue import get_redis_client

_lease: ContextVar[tuple[Any, str, str] | None] = ContextVar("submission_lease", default=None)


async def assert_submission_lease() -> None:
    """Verify this task still owns its renewable lease immediately before Submit."""
    lease = _lease.get()
    if lease is None:
        raise RuntimeError("A submission lease is required before clicking Submit.")
    client, key, token = lease
    application_id = key.rsplit(":", 1)[-1]
    if await client.get("scholarpilot:application_cancelled:" + application_id):
        raise RuntimeError("Application cancelled; the browser must stop before Submit.")
    if await client.get(key) != token:
        raise RuntimeError("Submission lease was lost; the browser must stop.")


async def submissions_stopped(user_id: str | None = None, autonomous: bool = False) -> bool:
    """Read the configured flag and the shared Redis runtime stop key."""
    if settings.KILL_SWITCH_ACTIVE:
        return True
    client = await get_redis_client()
    if client is None:
        return settings.ENVIRONMENT == "production"
    if user_id and await client.get("scholarpilot:user_deleted:" + user_id):
        return True
    if autonomous and user_id and await client.get("scholarpilot:autopilot_paused:" + user_id):
        return True
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
    if not await client.set(key, token, nx=True, ex=90):
        raise RuntimeError("Another worker already holds this application's submission lease.")
    marker = _lease.set((client, key, token))
    stopping = asyncio.Event()

    async def renew() -> None:
        while not stopping.is_set():
            try:
                await asyncio.wait_for(stopping.wait(), timeout=20)
            except asyncio.TimeoutError:
                renewed = await client.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], 90) else return 0 end",
                    1, key, token,
                )
                if not renewed:
                    return
    renewal = asyncio.create_task(renew())
    try:
        yield
    finally:
        _lease.reset(marker)
        stopping.set()
        try:
            await renewal
        finally:
            await client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                1, key, token,
            )
