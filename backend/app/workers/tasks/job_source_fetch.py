"""job_source.fetch — part 1: robots gate + SSRF-safe reachability check.

Route A/B/C classification, adapters, diffing, and structuring are Phase 06
part 2; this handler proves the fetch foundation end to end and records the
result on the ``job_source`` so the UI can show it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from app.db.session import get_sessionmaker
from app.ingest.errors import FetchError
from app.ingest.fetcher import get_fetcher
from app.models import JobSource
from app.models.enums import JobSourceStatus, RobotsState
from app.workers.registry import task

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@task("job_source.fetch")
async def job_source_fetch(payload: dict[str, Any]) -> None:
    source_id = UUID(payload["source_id"])
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        source = await session.get(JobSource, source_id)
        if source is None:
            log.warning("job_source.fetch.gone", source_id=str(source_id))
            return
        url, status = source.url, source.status

    if status != JobSourceStatus.ACTIVE:
        log.info("job_source.fetch.skip_inactive", source_id=str(source_id))
        return

    robots_state = RobotsState.UNKNOWN
    error: str | None = None
    ok = False
    async with get_fetcher() as fetcher:
        decision = await fetcher.check_robots(url)
        if not decision.allowed:
            robots_state = RobotsState.DISALLOWED
            error = "robots.txt disallows this URL — add the job pages manually."
        else:
            robots_state = decision.state
            try:
                result = await fetcher.fetch(url)
                if result.status_code >= 400:
                    error = f"The page returned HTTP {result.status_code}."
                else:
                    ok = True
            except FetchError as exc:
                error = f"Couldn't fetch the page: {exc}"

    async with sessionmaker() as session, session.begin():
        source = await session.get(JobSource, source_id)
        if source is None:
            return
        now = _utcnow()
        source.robots_state = robots_state
        source.robots_checked_at = now
        source.last_fetched_at = now
        source.last_error = error
        if ok:
            source.last_success_at = now
            source.consecutive_failures = 0
        else:
            source.consecutive_failures += 1
            if source.consecutive_failures >= 5:
                source.status = JobSourceStatus.ERROR
    log.info("job_source.fetch.done", source_id=str(source_id), ok=ok, robots=robots_state)
