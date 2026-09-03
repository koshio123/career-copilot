"""job_source.fetch — the full ingestion pipeline for one source (Phase 06).

Loads state → resolves (fetch, classify routes A/B, filter, LLM match-score,
all outside a transaction) → persists survivors in one short transaction →
records the outcome on the source. Route C (crawl + Playwright) is part 2b.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.ingest.fetcher import get_fetcher
from app.llm import get_llm_client
from app.models import JobPreference, JobSource
from app.models.enums import JobSourceStatus, SourceType
from app.repositories.jobs import JobIngestRepository
from app.services.ingest import JobIngestPipeline, PersistResult, persist
from app.workers.registry import task

log = structlog.get_logger(__name__)

_MAX_FAILURES = 5


def _utcnow() -> datetime:
    return datetime.now(UTC)


@task("job_source.fetch")
async def job_source_fetch(payload: dict[str, Any]) -> None:
    source_id = UUID(payload["source_id"])
    sm = get_sessionmaker()

    async with sm() as session:
        source = await session.get(JobSource, source_id)
        if source is None:
            log.warning("job_source.fetch.gone", source_id=str(source_id))
            return
        if source.status != JobSourceStatus.ACTIVE:
            log.info("job_source.fetch.skip_inactive", source_id=str(source_id))
            return
        url, user_id = source.url, source.user_id
        prefs = (
            await session.execute(select(JobPreference).where(JobPreference.user_id == user_id))
        ).scalar_one_or_none()
        known = await JobIngestRepository(session, user_id=user_id).known_hashes(source_id)

    llm = get_llm_client()
    async with get_fetcher() as fetcher:
        pipeline = JobIngestPipeline(fetcher=fetcher, llm=llm)
        resolved = await pipeline.resolve(source_url=url, known_hashes=known, prefs=prefs)

    # Persist whatever scored cleanly, even if the run later hit an error
    # (e.g. LLM credits ran out mid-board) — don't waste the calls already made.
    persisted = PersistResult()
    if resolved.ok or resolved.keep:
        async with sm() as session, session.begin():
            repo = JobIngestRepository(session, user_id=user_id)
            persisted = await persist(repo, source_id=source_id, resolved=resolved, llm=llm)

    async with sm() as session, session.begin():
        source = await session.get(JobSource, source_id)
        if source is None:
            return
        now = _utcnow()
        source.robots_state = resolved.robots_state
        source.robots_checked_at = now
        source.last_fetched_at = now
        source.last_error = resolved.error
        if resolved.route in ("ats", "json_ld"):
            source.source_type = SourceType(resolved.route)
            source.ats_vendor = resolved.ats_vendor
        if resolved.ok:
            source.last_success_at = now
            source.consecutive_failures = 0
        else:
            source.consecutive_failures += 1
            if source.consecutive_failures >= _MAX_FAILURES:
                source.status = JobSourceStatus.ERROR

    log.info(
        "job_source.fetch.done",
        source_id=str(source_id),
        route=resolved.route,
        fetched=resolved.fetched,
        saved=persisted.saved,
        filtered=resolved.filtered,
        below_threshold=resolved.below_threshold,
        scoring_failed=resolved.scoring_failed,
        pruned=persisted.pruned,
    )
    # ServiceUnavailableError (LLM outage) propagates → queue retry → DLQ.
