"""HostRateLimiter enforces a minimum per-host interval."""

from __future__ import annotations

import time

from app.ingest.ratelimit import HostRateLimiter


async def test_second_request_to_same_host_waits() -> None:
    limiter = HostRateLimiter(min_interval=0.15)
    start = time.monotonic()
    await limiter.acquire("a.example")
    await limiter.acquire("a.example")
    assert time.monotonic() - start >= 0.15


async def test_different_hosts_do_not_block_each_other() -> None:
    limiter = HostRateLimiter(min_interval=0.5)
    start = time.monotonic()
    await limiter.acquire("a.example")
    await limiter.acquire("b.example")
    assert time.monotonic() - start < 0.3


async def test_crawl_delay_overrides_default() -> None:
    limiter = HostRateLimiter(min_interval=0.01)
    start = time.monotonic()
    await limiter.acquire("a.example", min_interval=0.2)
    await limiter.acquire("a.example", min_interval=0.2)
    assert time.monotonic() - start >= 0.2
