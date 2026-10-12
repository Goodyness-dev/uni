"""Global pytest configuration and fixtures for ScholarPilot tests."""
import os
import pytest
import asyncio
import time
import httpx
from sqlalchemy import event

# Ensure tests default to in-memory sqlite if DATABASE_URL is not explicitly pointing to test postgres
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


class FakeRedis:
    """Isolated broker double supporting leases and daily deduplication."""
    def __init__(self):
        self.values = {}
        self.expires = {}
        self.lists = {}

    async def get(self, key):
        if self.expires.get(key, float("inf")) <= time.monotonic():
            self.values.pop(key, None)
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and await self.get(key) is not None:
            return False
        self.values[key] = value
        if ex:
            self.expires[key] = time.monotonic() + ex
        return True

    async def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def lpop(self, key):
        values = self.lists.get(key, [])
        return values.pop(0) if values else None

    async def eval(self, script, count, *args):
        if count == 2:
            first, second, amount = args[:3]
            amount = int(amount)
            global_total = int(self.values.get(first, 0))
            user_total = int(self.values.get(second, 0))
            if len(args) == 5 and (global_total + amount > int(args[3]) or user_total + amount > int(args[4])):
                return 0
            self.values[first] = global_total + amount
            self.values[second] = user_total + amount
            return 1
        key, token = args
        if await self.get(key) == token:
            return await self.delete(key)
        return 0


@pytest.fixture(autouse=True)
def offline_services(monkeypatch):
    """Prevent test runs using real brokers, provider keys, or external HTTP."""
    from app.jobs import queue
    from app.core import runtime
    from app.services import scheduler
    from app.agents import researcher
    from app.core.config import settings
    broker = FakeRedis()

    async def get_broker():
        return broker

    for module in (queue, runtime, scheduler):
        monkeypatch.setattr(module, "get_redis_client", get_broker)
    for name in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "PRIMARY_API_KEY", "FALLBACK_API_KEY", "NEATLOGS_API_KEY"):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    researcher._RESEARCH_CACHE.clear()
    original = httpx.AsyncClient.request

    async def request(client, method, url, **kwargs):
        if isinstance(client._transport, (httpx.ASGITransport, httpx.MockTransport)):
            return await original(client, method, url, **kwargs)
        if method.upper() == "GET":
            return httpx.Response(200, text="<p>Fictional institutional page used only in offline tests.</p>", request=httpx.Request(method, str(url)))
        raise AssertionError("External HTTP is prohibited in tests.")

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    yield broker
