"""``robots.txt`` gate (ADR-0013).

Every HTML fetch on routes B/C — and the initial classification fetch — passes
through :meth:`RobotsCache.check`. ATS public APIs (route A) are exempt (they
exist to distribute postings) but still get the polite User-Agent and rate limit.

The result is cached per host for ``settings.robots_cache_ttl_seconds``. A 404
means "no rules published" → allowed; a fetch error means "unknown" → allowed
but with the conservative default delay.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
import structlog
from protego import Protego

from app.core.config import settings
from app.ingest.errors import FetchError
from app.ingest.http import safe_get
from app.models.enums import RobotsState

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RobotsDecision:
    allowed: bool
    state: RobotsState
    crawl_delay: float | None


@dataclass(slots=True)
class _Entry:
    parser: Protego | None  # None = "unknown", treat as allowed
    state: RobotsState
    fetched_at: float


class RobotsCache:
    def __init__(self, *, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.robots_cache_ttl_seconds
        self._by_host: dict[str, _Entry] = {}

    async def check(self, url: str, *, client: httpx.AsyncClient | None = None) -> RobotsDecision:
        parsed = urlparse(url)
        host = parsed.netloc
        entry = self._by_host.get(host)
        if entry is None or (time.monotonic() - entry.fetched_at) > self._ttl:
            entry = await self._load(parsed.scheme or "https", host, client)
            self._by_host[host] = entry

        path = urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))
        ua = settings.fetch_user_agent
        if entry.parser is None:
            return RobotsDecision(allowed=True, state=entry.state, crawl_delay=None)
        return RobotsDecision(
            allowed=entry.parser.can_fetch(path, ua),
            state=entry.state,
            crawl_delay=entry.parser.crawl_delay(ua),
        )

    async def _load(self, scheme: str, host: str, client: httpx.AsyncClient | None) -> _Entry:
        robots_url = f"{scheme}://{host}/robots.txt"
        try:
            result = await safe_get(robots_url, client=client)
        except FetchError as exc:
            log.info("robots.fetch_failed", host=host, error=str(exc))
            return _Entry(parser=None, state=RobotsState.UNKNOWN, fetched_at=time.monotonic())

        if result.status_code == 404:
            return _Entry(parser=None, state=RobotsState.ALLOWED, fetched_at=time.monotonic())
        if result.status_code >= 400:
            return _Entry(parser=None, state=RobotsState.UNKNOWN, fetched_at=time.monotonic())
        return _Entry(
            parser=Protego.parse(result.text),
            state=RobotsState.ALLOWED,
            fetched_at=time.monotonic(),
        )


_cache: RobotsCache | None = None


def get_robots_cache() -> RobotsCache:
    global _cache
    if _cache is None:
        _cache = RobotsCache()
    return _cache
