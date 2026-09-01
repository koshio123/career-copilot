from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import Resume, ResumeVersion
from app.models.enums import ResumeVersionSource, ResumeVersionStatus
from app.repositories.base import UserScopedRepository


class ResumeRepository(UserScopedRepository):
    async def list(self) -> Sequence[Resume]:
        result = await self.session.execute(
            self._scoped(Resume)
            .options(selectinload(Resume.versions))
            .order_by(Resume.created_at.desc())
        )
        return result.scalars().all()

    async def get(self, resume_id: uuid.UUID) -> Resume | None:
        result = await self.session.execute(
            self._scoped(Resume)
            .where(Resume.id == resume_id)
            .options(selectinload(Resume.versions))
        )
        return result.scalar_one_or_none()

    async def get_version(self, version_id: uuid.UUID) -> ResumeVersion | None:
        result = await self.session.execute(
            self._scoped(ResumeVersion).where(ResumeVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def _next_version_no(self, resume_id: uuid.UUID) -> int:
        current = await self.session.scalar(
            select(func.max(ResumeVersion.version_no)).where(ResumeVersion.resume_id == resume_id)
        )
        return (current or 0) + 1

    async def create(
        self,
        *,
        label: str,
        source: ResumeVersionSource,
        status: ResumeVersionStatus,
        source_file_key: str | None = None,
        raw_text: str | None = None,
    ) -> tuple[Resume, ResumeVersion]:
        resume = Resume(user_id=self.user_id, label=label)
        version = ResumeVersion(
            user_id=self.user_id,
            resume=resume,
            version_no=1,
            source=source,
            status=status,
            source_file_key=source_file_key,
            raw_text=raw_text,
        )
        self.session.add(resume)
        await self.session.flush()
        return resume, version

    async def add_version(
        self, resume: Resume, *, source: ResumeVersionSource, status: ResumeVersionStatus
    ) -> ResumeVersion:
        version = ResumeVersion(
            user_id=self.user_id,
            resume_id=resume.id,
            version_no=await self._next_version_no(resume.id),
            source=source,
            status=status,
        )
        self.session.add(version)
        await self.session.flush()
        return version
