"""``PoliteFetcher`` — robots gate + rate limit + SSRF-safe GET, in that order.

Worker code fetches career pages exclusively through this. It owns one
``httpx.AsyncClient`` for connection reuse across a run.
"""

from __future__ import annotations

from types import TracebackType
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import settings
from app.ingest.errors import RobotsDisallowedError
from app.ingest.http import FetchResult, safe_get
from app.ingest.ratelimit import HostRateLimiter, get_rate_limiter
from app.ingest.robots import RobotsCache, RobotsDecision, get_robots_cache

log = structlog.get_logger(__name__)


class PoliteFetcher:
    def __init__(
        self,
        *,
        robots: RobotsCache | None = None,
        limiter: HostRateLimiter | None = None,
    ) -> None:
        self._robots = robots or get_robots_cache()
        self._limiter = limiter or get_rate_limiter()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.fetch_timeout_seconds),
            follow_redirects=False,
        )

    async def __aenter__(self) -> PoliteFetcher:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check_robots(self, url: str) -> RobotsDecision:
        return await self._robots.check(url, client=self._client)

    async def fetch(
        self,
        url: str,
        *,
        respect_robots: bool = True,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        host = urlparse(url).netloc
        crawl_delay: float | None = None
        if respect_robots:
            decision = await self.check_robots(url)
            if not decision.allowed:
                raise RobotsDisallowedError(f"robots.txt disallows {url}")
            crawl_delay = decision.crawl_delay
        await self._limiter.acquire(host, min_interval=crawl_delay)
        return await safe_get(url, client=self._client, headers=headers)


def get_fetcher() -> PoliteFetcher:
    """A fresh fetcher (and HTTP client) for one unit of work."""
    return PoliteFetcher()
