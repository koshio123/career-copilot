"""JobSourceService / JobPostingService exercised directly (no HTTP layer)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models import User
from app.models.enums import JobPostingStatus, JobSourceStatus
from app.schemas.job import JobPostingManualIn, JobPostingUpdateIn
from app.schemas.job_source import JobSourceCreateIn
from app.services.jobs import JobPostingService, JobSourceService
from tests.fakes import RecordingQueue


async def _user(db: AsyncSession) -> User:
    user = User(email="svc@example.com", email_verified_at=datetime.now(UTC))
    db.add(user)
    await db.flush()
    return user


async def test_source_lifecycle(db: AsyncSession) -> None:
    user = await _user(db)
    queue = RecordingQueue()
    svc = JobSourceService(db, user_id=user.id, queue=queue)

    source = await svc.register(JobSourceCreateIn(url="https://acme.example/careers"))
    assert len(queue.messages) == 1

    with pytest.raises(ValidationError):
        await svc.register(JobSourceCreateIn(url="https://acme.example/careers"))

    await svc.set_status(source.id, JobSourceStatus.PAUSED)
    with pytest.raises(ValidationError):
        await svc.trigger_fetch(source.id)

    await svc.set_status(source.id, JobSourceStatus.ACTIVE)
    await svc.trigger_fetch(source.id)
    assert len(queue.messages) == 2

    await svc.remove(source.id)
    with pytest.raises(NotFoundError):
        await svc.get(source.id)


async def test_posting_service(db: AsyncSession) -> None:
    user = await _user(db)
    svc = JobPostingService(db, user_id=user.id)

    posting = await svc.create_manual(
        JobPostingManualIn(company_name="Acme", title="Backend Engineer", location="Tokyo")
    )
    assert posting.status is JobPostingStatus.NEW

    updated = await svc.update(
        posting.id, JobPostingUpdateIn(status=JobPostingStatus.INTERESTED, bookmarked=True)
    )
    assert updated.status is JobPostingStatus.INTERESTED
    assert updated.bookmarked is True

    await svc.remove(posting.id)
    with pytest.raises(NotFoundError):
        await svc.get(posting.id)
