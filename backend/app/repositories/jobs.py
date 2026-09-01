from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.models import JobPosting, JobSource
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
