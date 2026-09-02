"""Per-host politeness delay (ADR-0013).

An in-process limiter: before each request to a host, wait until at least
``min_interval`` seconds have passed since the last one. One worker process =
one limiter; that is enough for the scheduled, low-volume fetching we do.
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import settings


class HostRateLimiter:
    def __init__(self, *, min_interval: float | None = None) -> None:
        self._default = (
            min_interval if min_interval is not None else settings.fetch_min_host_interval_seconds
        )
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, host: str) -> asyncio.Lock:
        lock = self._locks.get(host)
        if lock is None:
            lock = self._locks[host] = asyncio.Lock()
        return lock

    async def acquire(self, host: str, *, min_interval: float | None = None) -> None:
        interval = max(self._default, min_interval or 0.0)
        async with self._lock(host):
            last = self._last.get(host)
            now = time.monotonic()
            if last is not None:
                wait = interval - (now - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last[host] = time.monotonic()


_limiter: HostRateLimiter | None = None


def get_rate_limiter() -> HostRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = HostRateLimiter()
    return _limiter
