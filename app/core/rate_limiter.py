"""Sliding window in-memory rate limiter for API protection and abuse prevention."""
import time
from collections import defaultdict
from typing import Callable, Dict, List
from fastapi import HTTPException, Request, status


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

    async def dependency(request: Request):
        # Identify by client API key if present, otherwise by client IP
        client_key = request.headers.get("X-API-Key")
        if not client_key:
            client_key = request.client.host if request.client else "unknown"

        if not limiter.is_allowed(client_key):
            retry_sec = limiter.retry_after(client_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down your requests.",
                headers={"Retry-After": str(retry_sec)},
            )

    return dependency
