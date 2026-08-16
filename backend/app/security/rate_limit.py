"""Rate limiter interface and in-memory sliding window implementation.

Designed behind an abstract interface so it can be swapped for Redis / Azure Cache
without modifying endpoint call sites.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ── Abstract Interface ─────────────────────────────────────────────────────────

class RateLimiter(ABC):
    """Interface that all rate limiters (in-memory, Redis, Azure Cache) must implement."""

    @abstractmethod
    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """Check if a request under `key` is allowed.

        Returns:
            (allowed: bool, remaining_requests: int, reset_seconds: int)
        """
        ...


# ── In-Memory Sliding Window Implementation ────────────────────────────────────

class InMemorySlidingWindowRateLimiter(RateLimiter):
    """In-memory rate limiter using sliding-window timestamp tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> list of timestamp floats
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Filter timestamps within the current window
            current_window = [
                ts for ts in self._timestamps[key] if ts > window_start
            ]
            count = len(current_window)

            if count >= max_requests:
                oldest = current_window[0] if current_window else now
                reset_seconds = max(1, int(oldest + window_seconds - now))
                self._timestamps[key] = current_window
                return False, 0, reset_seconds

            current_window.append(now)
            self._timestamps[key] = current_window
            remaining = max_requests - len(current_window)
            return True, remaining, window_seconds


# ── Factory ────────────────────────────────────────────────────────────────────

_rate_limiter_instance: RateLimiter | None = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Return configured RateLimiter singleton."""
    global _rate_limiter_instance  # noqa: PLW0603
    if _rate_limiter_instance is None:
        with _rate_limiter_lock:
            if _rate_limiter_instance is None:
                _rate_limiter_instance = InMemorySlidingWindowRateLimiter()
    return _rate_limiter_instance


async def check_rate_limit_or_raise(
    request: Request,
    scope: str,
    max_requests: int,
    window_seconds: int = 60,
    user_id: str | None = None,
) -> None:
    """Helper to enforce rate limits per IP or authenticated user ID."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    limiter = get_rate_limiter()
    identifier = user_id or (request.client.host if request.client else "127.0.0.1")
    key = f"{scope}:{identifier}"

    allowed, remaining, reset_seconds = await limiter.is_allowed(
        key=key, max_requests=max_requests, window_seconds=window_seconds
    )

    if not allowed:
        logger.warning("Rate limit exceeded for key=%s (reset in %ds)", key, reset_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Too many requests. Please retry in {reset_seconds} seconds.",
                "retry_after": reset_seconds,
            },
            headers={"Retry-After": str(reset_seconds)},
        )
