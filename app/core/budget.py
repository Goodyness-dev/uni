"""Atomic, durable per-day model budget reservations in Redis."""
from datetime import datetime, timezone
from app.core.config import settings
from app.jobs.queue import get_redis_client

RESERVE = """
local amount = tonumber(ARGV[1])
if tonumber(redis.call('get', KEYS[1]) or '0') + amount > tonumber(ARGV[2]) then return 0 end
if tonumber(redis.call('get', KEYS[2]) or '0') + amount > tonumber(ARGV[3]) then return 0 end
redis.call('incrby', KEYS[1], amount)
redis.call('incrby', KEYS[2], amount)
redis.call('expire', KEYS[1], 172800)
redis.call('expire', KEYS[2], 172800)
return 1
"""


async def reserve_budget(user_id: str, estimated_usd: float) -> tuple[str, str, int]:
    """Reserve a conservative token bound before each paid provider attempt."""
    if not user_id:
        raise ValueError("Paid production calls require an owner for accounting.")
    client = await get_redis_client()
    if client is None:
        raise RuntimeError("Production model calls require a shared budget ledger.")
    day = datetime.now(timezone.utc).date().isoformat()
    keys = (f"scholarpilot:spend:{day}:global", f"scholarpilot:spend:{day}:user:{user_id}")
    amount = int(estimated_usd * 1_000_000 + 1)
    result = await client.eval(RESERVE, 2, *keys, amount,
        int(settings.GLOBAL_DAILY_SPEND_CAP_USD * 1_000_000),
        int(settings.USER_DAILY_SPEND_CAP_USD * 1_000_000))
    if not result:
        raise RuntimeError("Daily model budget is exhausted.")
    return keys[0], keys[1], amount


async def settle_budget(reservation: tuple[str, str, int], actual_usd: float) -> None:
    """Retain billed usage, including invalid model output; release unused bound."""
    client = await get_redis_client()
    if client is None:
        # Retaining a reservation is safer than forgetting uncertain charges.
        raise RuntimeError("Budget settlement could not access the ledger.")
    actual = int(actual_usd * 1_000_000 + 1)
    if actual > reservation[2]:
        raise RuntimeError("Provider usage exceeded the reserved token bound; stop further calls.")
    script = "redis.call('incrby', KEYS[1], ARGV[1]); redis.call('incrby', KEYS[2], ARGV[1]); return 1"
    await client.eval(script, 2, reservation[0], reservation[1], actual - reservation[2])
