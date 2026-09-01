"""enqueue_due_sources picks active sources that are past their interval."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.scheduler import enqueue_due_sources
from app.models import JobSource, User
from app.models.enums import JobSourceStatus
from tests.fakes import RecordingQueue


async def _user(db: AsyncSession) -> User:
    user = User(email="sched@example.com", email_verified_at=datetime.now(UTC))
    db.add(user)
    await db.flush()
    return user


async def test_enqueues_only_due_active_sources(db: AsyncSession) -> None:
    user = await _user(db)
    now = datetime.now(UTC)
    db.add_all(
        [
            JobSource(user_id=user.id, url="https://a.example", fetch_interval_hours=24),  # never
            JobSource(
                user_id=user.id,
                url="https://b.example",
                fetch_interval_hours=1,
                last_fetched_at=now - timedelta(hours=3),  # due
            ),
            JobSource(
                user_id=user.id,
                url="https://c.example",
                fetch_interval_hours=24,
                last_fetched_at=now - timedelta(hours=1),  # not due
            ),
            JobSource(
                user_id=user.id,
                url="https://d.example",
                fetch_interval_hours=1,
                last_fetched_at=now - timedelta(hours=5),
                status=JobSourceStatus.PAUSED,  # inactive
            ),
        ]
    )
    await db.flush()

    queue = RecordingQueue()
    count = await enqueue_due_sources(db, queue)

    assert count == 2
    assert {m.task for m in queue.messages} == {"job_source.fetch"}
