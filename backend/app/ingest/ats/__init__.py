"""Route A — per-vendor public job-board API clients (ADR-0012).

Ship: Greenhouse, Lever, Ashby. Each adapter is
``async def fetch(board_id, *, fetcher) -> list[FetchedJob]`` and normalises the
vendor's shape onto the common schema. Unknown/failing vendors fall back to
route C.
"""

from __future__ import annotations

from app.ingest.ats.base import AtsAdapter, AtsError
from app.ingest.ats.registry import ADAPTERS, get_adapter

__all__ = ["ADAPTERS", "AtsAdapter", "AtsError", "get_adapter"]
