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
        self.windows = {}

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

    async def getdel(self, key):
        value = await self.get(key)
        await self.delete(key)
        return value

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def lpop(self, key):
        values = self.lists.get(key, [])
        return values.pop(0) if values else None

    async def eval(self, script, count, *args):
        if "zremrangebyscore" in script:
            key, cutoff, maximum, now, nonce, expiry = args
            window = [value for value in self.windows.get(key, []) if value > float(cutoff)]
            self.windows[key] = window
            if len(window) >= int(maximum):
                return 0
            window.append(float(now))
            return 1
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
            if "expire" in script:
                self.expires[key] = time.monotonic() + 90
                return 1
            return await self.delete(key)
        return 0


@pytest.fixture(autouse=True)
def offline_services(monkeypatch):
    """Prevent test runs using real brokers, provider keys, or external HTTP."""
    from app.jobs import queue
    from app.core import runtime
    from app.services import scheduler
    from app.core import rate_limiter, identity
    from app.api.v1 import settings as user_settings, onboarding, applications
    from app.agents import researcher
    from app.core.config import settings
    broker = FakeRedis()

    async def get_broker():
        return broker

    for module in (queue, runtime, scheduler, rate_limiter, identity, user_settings, onboarding, applications):
        monkeypatch.setattr(module, "get_redis_client", get_broker)
    for name in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "PRIMARY_API_KEY", "FALLBACK_API_KEY", "NEATLOGS_API_KEY"):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "LLM_DRAFTING", False)
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SES_FROM", None)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_APP_PASSWORD", None)
    async def public_fixture(url):
        return "<p>Fictional institutional page used only in offline tests.</p>"
    from app.services import public_pages
    async def official_fixture(url, **kwargs):
        return await public_fixture(url)
    monkeypatch.setattr(public_pages, "fetch_public_text", official_fixture)
    monkeypatch.setattr(settings, "LIVE_RESEARCH", True)
    original = httpx.AsyncClient.request

    async def request(client, method, url, **kwargs):
        if isinstance(client._transport, (httpx.ASGITransport, httpx.MockTransport)):
            return await original(client, method, url, **kwargs)
        if method.upper() == "GET":
            return httpx.Response(200, text="<p>Fictional institutional page used only in offline tests.</p>", request=httpx.Request(method, str(url)))
        raise AssertionError("External HTTP is prohibited in tests.")

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    yield broker
