"""Job ingestion — fetching career URLs safely and politely (Phase 06).

This package is the *fetch foundation* (part 1): an SSRF-safe HTTP client
(:mod:`app.ingest.http`), a cached ``robots.txt`` gate (:mod:`app.ingest.robots`),
a per-host rate limiter (:mod:`app.ingest.ratelimit`), the :class:`PoliteFetcher`
that combines them, and the scheduler that enqueues due sources
(:mod:`app.ingest.scheduler`). Route A/B/C classification and structuring land in
part 2.
"""

from app.ingest.errors import (
    BlockedHostError,
    FetchError,
    FetchTimeoutError,
    FetchTooLargeError,
    RobotsDisallowedError,
)
from app.ingest.fetcher import PoliteFetcher, get_fetcher
from app.ingest.http import FetchResult, safe_get

__all__ = [
    "BlockedHostError",
    "FetchError",
    "FetchResult",
    "FetchTimeoutError",
    "FetchTooLargeError",
    "PoliteFetcher",
    "RobotsDisallowedError",
    "get_fetcher",
    "safe_get",
]
