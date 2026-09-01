from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.models import Resume, ResumeVersion
from app.models.enums import ResumeVersionSource, ResumeVersionStatus
from app.queue.base import Queue, TaskMessage
from app.repositories.resumes import ResumeRepository
from app.resumes.schema import ResumeStructured
from app.schemas.resume import ResumeCreateIn
from app.storage import ResumeStorage
from app.storage.s3 import Upload

PROCESS_TASK = "resume.process"


class ResumeService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        storage: ResumeStorage,
        queue: Queue,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._repo = ResumeRepository(session, user_id=user_id)
        self._storage = storage
        self._queue = queue

    def create_upload(self, *, content_type: str) -> Upload:
        return self._storage.create_upload(user_id=self._user_id, content_type=content_type)

    async def register(self, data: ResumeCreateIn) -> Resume:
        if data.source_key:
            self._assert_owned_key(data.source_key)
            size = await self._storage.size(data.source_key)
            if size is None:
                raise ValidationError("The upload was not found — did it finish?")
            if size > settings.upload_max_bytes:
                raise ValidationError("That file is too large.")
            resume, version = await self._repo.create(
                label=data.label or "My résumé",
                source=ResumeVersionSource.UPLOAD,
                status=ResumeVersionStatus.PENDING,
                source_file_key=data.source_key,
            )
        else:
            resume, version = await self._repo.create(
                label=data.label or "My résumé",
                source=ResumeVersionSource.FORM,
                status=ResumeVersionStatus.STRUCTURING,
                raw_text=data.raw_text,
            )

        await self._queue.enqueue(
            TaskMessage(task=PROCESS_TASK, payload={"version_id": str(version.id)})
        )
        return resume

    async def list(self) -> Sequence[Resume]:
        return await self._repo.list()

    async def get(self, resume_id: uuid.UUID) -> Resume:
        resume = await self._repo.get(resume_id)
        if resume is None:
            raise NotFoundError("Résumé not found.")
        return resume

    async def get_version(self, version_id: uuid.UUID) -> ResumeVersion:
        version = await self._repo.get_version(version_id)
        if version is None:
            raise NotFoundError("Résumé version not found.")
        return version

    async def update_structured(
        self, version_id: uuid.UUID, structured: ResumeStructured
    ) -> ResumeVersion:
        version = await self.get_version(version_id)
        version.structured = structured.model_dump()
        version.status = ResumeVersionStatus.READY
        version.error = None
        await self._session.flush()
        return version

    def _assert_owned_key(self, key: str) -> None:
        if not key.startswith(f"resumes/{self._user_id}/"):
            raise NotFoundError("Upload not found.")
