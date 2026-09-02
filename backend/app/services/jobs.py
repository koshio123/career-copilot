from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.jobs.normalize import dedup_key, normalize_company, normalize_text
from app.models import JobPosting, JobSource
from app.models.enums import JobSourceStatus
from app.queue.base import Queue, TaskMessage
from app.repositories.jobs import JobPostingRepository, JobSourceRepository
from app.schemas.job import JobPostingManualIn, JobPostingUpdateIn
from app.schemas.job_source import JobSourceCreateIn

FETCH_TASK = "job_source.fetch"


class JobSourceService:
    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID, queue: Queue) -> None:
        self._session = session
        self._repo = JobSourceRepository(session, user_id=user_id)
        self._queue = queue

    async def register(self, data: JobSourceCreateIn) -> JobSource:
        if await self._repo.get_by_url(data.url) is not None:
            raise ValidationError("You've already registered that URL.")
        source = await self._repo.create(
            url=data.url,
            label=data.label,
            fetch_interval_hours=data.fetch_interval_hours,
        )
        await self._enqueue_fetch(source.id)
        return source

    async def list(self) -> Sequence[JobSource]:
        return await self._repo.list()

    async def get(self, source_id: uuid.UUID) -> JobSource:
        source = await self._repo.get(source_id)
        if source is None:
            raise NotFoundError("Job source not found.")
        return source

    async def remove(self, source_id: uuid.UUID) -> None:
        await self._repo.delete(await self.get(source_id))

    async def set_status(self, source_id: uuid.UUID, status: JobSourceStatus) -> JobSource:
        source = await self.get(source_id)
        source.status = status
        await self._session.flush()
        return source

    async def trigger_fetch(self, source_id: uuid.UUID) -> JobSource:
        source = await self.get(source_id)
        if source.status != JobSourceStatus.ACTIVE:
            raise ValidationError("Resume the source before fetching it.")
        await self._enqueue_fetch(source.id)
        return source

    async def _enqueue_fetch(self, source_id: uuid.UUID) -> None:
        await self._queue.enqueue(
            TaskMessage(task=FETCH_TASK, payload={"source_id": str(source_id)})
        )


class JobPostingService:
    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID) -> None:
        self._session = session
        self._repo = JobPostingRepository(session, user_id=user_id)

    async def create_manual(self, data: JobPostingManualIn) -> JobPosting:
        key = dedup_key(company=data.company_name, title=data.title, location=data.location)
        if await self._repo.get_by_dedup_key(key) is not None:
            raise ValidationError("A job like that is already in your list.")
        structured = data.to_structured().model_dump()
        structured["source_type"] = "manual"
        return await self._repo.create(
            dedup_key=key,
            company_name=data.company_name.strip(),
            company_name_normalized=normalize_company(data.company_name),
            canonical_title=data.title.strip(),
            location_normalized=normalize_text(data.location) if data.location else None,
            structured=structured,
        )

    async def list(self) -> Sequence[JobPosting]:
        return await self._repo.list()

    async def get(self, posting_id: uuid.UUID) -> JobPosting:
        posting = await self._repo.get(posting_id)
        if posting is None:
            raise NotFoundError("Job not found.")
        return posting

    async def update(self, posting_id: uuid.UUID, data: JobPostingUpdateIn) -> JobPosting:
        posting = await self.get(posting_id)
        if data.status is not None:
            posting.status = data.status
        if data.bookmarked is not None:
            posting.bookmarked = data.bookmarked
        await self._session.flush()
        return posting

    async def remove(self, posting_id: uuid.UUID) -> None:
        await self._session.delete(await self.get(posting_id))
        await self._session.flush()
