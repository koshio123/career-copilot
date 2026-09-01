"""Dispatch due job sources onto the fetch queue.

In dev/prod an EventBridge Scheduler → Lambda calls :func:`enqueue_due_sources`
on a fixed cadence (Phase 10); locally ``scripts/schedule_fetches.py`` does.
A source is *due* when it is active and either never fetched or last fetched
more than ``fetch_interval_hours`` ago.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobSource
from app.models.enums import JobSourceStatus
from app.queue.base import Queue, TaskMessage
from app.services.jobs import FETCH_TASK

log = structlog.get_logger(__name__)


def _is_due(source: JobSource, now: datetime) -> bool:
    if source.last_fetched_at is None:
        return True
    return source.last_fetched_at <= now - timedelta(hours=source.fetch_interval_hours)


async def enqueue_due_sources(session: AsyncSession, queue: Queue) -> int:
    now = datetime.now(UTC)
    result = await session.execute(
        select(JobSource).where(JobSource.status == JobSourceStatus.ACTIVE)
    )
    due = [s for s in result.scalars().all() if _is_due(s, now)]
    for source in due:
        await queue.enqueue(TaskMessage(task=FETCH_TASK, payload={"source_id": str(source.id)}))
    log.info("scheduler.enqueued", count=len(due))
    return len(due)
