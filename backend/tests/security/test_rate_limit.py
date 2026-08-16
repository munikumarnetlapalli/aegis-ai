"""Security tests for rate limiting interface and sliding-window limiter."""
from __future__ import annotations

import pytest

from app.security.rate_limit import InMemorySlidingWindowRateLimiter, RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    limiter = InMemorySlidingWindowRateLimiter()
    assert isinstance(limiter, RateLimiter)

    key = "test_ip_1"
    for i in range(3):
        allowed, remaining, _ = await limiter.is_allowed(key, max_requests=3, window_seconds=60)
        assert allowed is True
        assert remaining == 2 - i


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    limiter = InMemorySlidingWindowRateLimiter()
    key = "test_ip_2"

    # Consume all 2 allowed requests
    await limiter.is_allowed(key, max_requests=2, window_seconds=60)
    await limiter.is_allowed(key, max_requests=2, window_seconds=60)

    # 3rd request must be blocked
    allowed, remaining, reset_secs = await limiter.is_allowed(key, max_requests=2, window_seconds=60)
    assert allowed is False
    assert remaining == 0
    assert reset_secs > 0


@pytest.mark.asyncio
async def test_rate_limiter_keys_isolated():
    limiter = InMemorySlidingWindowRateLimiter()
    key_a = "ip_alpha"
    key_b = "ip_beta"

    # Fill key_a
    await limiter.is_allowed(key_a, max_requests=1, window_seconds=60)
    blocked_a, _, _ = await limiter.is_allowed(key_a, max_requests=1, window_seconds=60)
    assert blocked_a is False

    # key_b should still be allowed
    allowed_b, _, _ = await limiter.is_allowed(key_b, max_requests=1, window_seconds=60)
    assert allowed_b is True
