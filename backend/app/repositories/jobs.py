from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, Job, JobPosting, JobSource, LlmUsage
from app.models.enums import JobPostingStatus, JobSourceStatus
from app.repositories.base import UserScopedRepository


class JobSourceRepository(UserScopedRepository):
    async def list(self) -> Sequence[JobSource]:
        result = await self.session.execute(
            self._scoped(JobSource).order_by(JobSource.created_at.desc())
        )
        return result.scalars().all()

    async def get(self, source_id: uuid.UUID) -> JobSource | None:
        result = await self.session.execute(
            self._scoped(JobSource).where(JobSource.id == source_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> JobSource | None:
        result = await self.session.execute(self._scoped(JobSource).where(JobSource.url == url))
        return result.scalar_one_or_none()

    async def create(self, *, url: str, label: str | None, fetch_interval_hours: int) -> JobSource:
        source = JobSource(
            user_id=self.user_id,
            url=url,
            label=label,
            fetch_interval_hours=fetch_interval_hours,
            status=JobSourceStatus.ACTIVE,
        )
        self.session.add(source)
        await self.session.flush()
        return source

    async def delete(self, source: JobSource) -> None:
        await self.session.delete(source)
        await self.session.flush()


class JobPostingRepository(UserScopedRepository):
    async def list(self) -> Sequence[JobPosting]:
        result = await self.session.execute(
            self._scoped(JobPosting).order_by(
                JobPosting.match_score.desc().nullslast(),
                JobPosting.created_at.desc(),
            )
        )
        return result.scalars().all()

    async def get(self, posting_id: uuid.UUID) -> JobPosting | None:
        result = await self.session.execute(
            self._scoped(JobPosting).where(JobPosting.id == posting_id)
        )
        return result.scalar_one_or_none()

    async def get_by_dedup_key(self, key: str) -> JobPosting | None:
        result = await self.session.execute(
            self._scoped(JobPosting).where(JobPosting.dedup_key == key)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        dedup_key: str,
        company_name: str,
        company_name_normalized: str,
        canonical_title: str,
        location_normalized: str | None,
        structured: dict[str, object],
        status: JobPostingStatus = JobPostingStatus.NEW,
    ) -> JobPosting:
        posting = JobPosting(
            user_id=self.user_id,
            dedup_key=dedup_key,
            company_name=company_name,
            company_name_normalized=company_name_normalized,
            canonical_title=canonical_title,
            location_normalized=location_normalized,
            structured=structured,
            status=status,
        )
        self.session.add(posting)
        await self.session.flush()
        return posting


class JobIngestRepository:
    """Worker-side reads/writes for the ingestion pipeline. Scoped to one source's owner."""

    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def find_job(
        self, *, source_id: uuid.UUID, external_id: str | None, url: str
    ) -> Job | None:
        clause = Job.url == url
        if external_id is not None:
            clause = or_(clause, Job.external_id == external_id)
        result = await self.session.execute(
            select(Job).where(and_(Job.job_source_id == source_id, clause))
        )
        return result.scalars().first()

    async def known_hashes(self, source_id: uuid.UUID) -> dict[str, str]:
        """{external_id-or-url: raw_text_hash} for every job currently held for this source."""
        result = await self.session.execute(
            select(Job.external_id, Job.url, Job.raw_text_hash).where(
                Job.job_source_id == source_id
            )
        )
        return {(ext or url): digest for ext, url, digest in result.all()}

    async def get_posting(self, dedup_key: str) -> JobPosting | None:
        result = await self.session.execute(
            select(JobPosting).where(
                JobPosting.user_id == self.user_id, JobPosting.dedup_key == dedup_key
            )
        )
        return result.scalar_one_or_none()

    def add(self, obj: Job | JobPosting | LlmUsage) -> None:
        self.session.add(obj)

    async def delete_job(self, job: Job) -> None:
        await self.session.delete(job)

    async def jobs_for_source(self, source_id: uuid.UUID) -> Sequence[Job]:
        result = await self.session.execute(select(Job).where(Job.job_source_id == source_id))
        return result.scalars().all()

    async def prune_orphan_postings(self) -> int:
        """Delete this user's non-manual postings that have no jobs and no application."""
        job_count = (
            select(func.count(Job.id)).where(Job.job_posting_id == JobPosting.id).scalar_subquery()
        )
        app_count = (
            select(func.count(Application.id))
            .where(Application.job_posting_id == JobPosting.id)
            .scalar_subquery()
        )
        result = await self.session.execute(
            select(JobPosting).where(
                JobPosting.user_id == self.user_id,
                job_count == 0,
                app_count == 0,
                JobPosting.structured["source_type"].astext != "manual",
            )
        )
        orphans = result.scalars().all()
        for posting in orphans:
            await self.session.delete(posting)
        return len(orphans)
