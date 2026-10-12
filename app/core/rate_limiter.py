"""Sliding window in-memory rate limiter for API protection and abuse prevention."""
import time
import hashlib
import uuid
from collections import defaultdict
from typing import Callable, Dict, List
from fastapi import HTTPException, Request, status
from app.core.config import settings
from app.jobs.queue import get_redis_client
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

WINDOW_SCRIPT = """
redis.call('zremrangebyscore', KEYS[1], '-inf', ARGV[1])
if redis.call('zcard', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('zadd', KEYS[1], ARGV[3], ARGV[4])
redis.call('expire', KEYS[1], ARGV[5])
return 1
"""


class SlidingWindowRateLimiter:
    """Sliding-window token bucket limiter tracked per client key (IP or API key)."""
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        # Evict timestamps outside the window
        timestamps = self.requests[key]
        self.requests[key] = [t for t in timestamps if t > window_start]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

    def retry_after(self, key: str) -> int:
        now = time.time()
        if not self.requests[key]:
            return 0
        oldest_in_window = self.requests[key][0]
        return max(1, int(oldest_in_window + self.window_seconds - now))


# Global default API limiter: 100 requests per minute
global_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)


def rate_limit_dependency(max_requests: int = 60, window_seconds: int = 60) -> Callable:
    """FastAPI dependency factory enforcing rate limits on endpoint routes."""
    limiter = SlidingWindowRateLimiter(max_requests=max_requests, window_seconds=window_seconds)

    async def dependency(request: Request) -> None:
        # Identify by client API key if present, otherwise by client IP
        client_key = request.headers.get("X-API-Key")
        if not client_key:
            client_key = request.client.host if request.client else "unknown"

        if settings.ENVIRONMENT == "production":
            broker = await get_redis_client()
            if broker is None:
                raise HTTPException(status_code=503, detail="Shared rate limiting is unavailable.")
            # Do not retain raw credentials or trust forwarding headers supplied by clients.
            hashed = hashlib.sha256(client_key.encode()).hexdigest()
            now = time.time()
            address = request.client.host if request.client else "unknown"
            ip_hash = hashlib.sha256(address.encode()).hexdigest()
            allowed = True
            for bucket in {"credential:" + hashed, "address:" + ip_hash}:
                try:
                    accepted = await broker.eval(WINDOW_SCRIPT, 1, "scholarpilot:rate:" + bucket,
                        now - window_seconds, max_requests, now, uuid.uuid4().hex, window_seconds)
                except (RedisConnectionError, RedisTimeoutError):
                    raise HTTPException(status_code=503, detail="Shared rate limiting is temporarily unavailable.")
                allowed = allowed and bool(accepted)
        else:
            allowed = limiter.is_allowed(client_key)
        if not allowed:
            retry_sec = window_seconds if settings.ENVIRONMENT == "production" else limiter.retry_after(client_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down your requests.",
                headers={"Retry-After": str(retry_sec)},
            )

    return dependency
