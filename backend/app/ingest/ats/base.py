from __future__ import annotations

import json
from typing import Any, Protocol

from app.ingest.errors import FetchError
from app.ingest.fetcher import PoliteFetcher
from app.jobs.schema import FetchedJob


class AtsError(FetchError):
    """The ATS API was unreachable or returned something we can't parse."""


class AtsAdapter(Protocol):
    vendor: str

    async def fetch(self, board_id: str, *, fetcher: PoliteFetcher) -> list[FetchedJob]: ...


async def get_json(url: str, *, fetcher: PoliteFetcher) -> Any:
    """GET an ATS endpoint (route A: no robots gate, ADR-0013) and parse JSON."""
    try:
        result = await fetcher.fetch(url, respect_robots=False)
    except FetchError as exc:
        raise AtsError(str(exc)) from exc
    if result.status_code >= 400:
        raise AtsError(f"{url} returned HTTP {result.status_code}")
    try:
        return json.loads(result.content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AtsError(f"{url} did not return JSON: {exc}") from exc
