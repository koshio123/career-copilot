from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.models import Resume, ResumeVersion
from app.models.enums import ResumeVersionSource, ResumeVersionStatus
from app.resumes.schema import ResumeStructured


class UploadRequestIn(BaseModel):
    filename: str = Field(max_length=255)
    content_type: str

    @model_validator(mode="after")
    def _allowed(self) -> UploadRequestIn:
        if self.content_type not in settings.allowed_upload_types:
            raise ValueError("only PDF and DOCX files are accepted")
        return self


class UploadOut(BaseModel):
    key: str
    url: str
    max_bytes: int


class ResumeCreateIn(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    source_key: str | None = None
    raw_text: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> ResumeCreateIn:
        if bool(self.source_key) == bool(self.raw_text):
            raise ValueError("provide exactly one of source_key or raw_text")
        if self.raw_text is not None and len(self.raw_text.strip()) < 40:
            raise ValueError("raw_text is too short to be a résumé")
        return self


class ResumeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_no: int
    source: ResumeVersionSource
    status: ResumeVersionStatus
    error: str | None
    structured: dict[str, Any]
    has_raw_text: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, version: ResumeVersion) -> ResumeVersionOut:
        return cls(
            id=version.id,
            version_no=version.version_no,
            source=version.source,
            status=version.status,
            error=version.error,
            structured=version.structured,
            has_raw_text=version.raw_text is not None,
            created_at=version.created_at,
            updated_at=version.updated_at,
        )


class ResumeOut(BaseModel):
    id: UUID
    label: str
    is_primary: bool
    created_at: datetime
    latest_version: ResumeVersionOut | None

    @classmethod
    def of(cls, resume: Resume) -> ResumeOut:
        latest = max(resume.versions, key=lambda v: v.version_no, default=None)
        return cls(
            id=resume.id,
            label=resume.label,
            is_primary=resume.is_primary,
            created_at=resume.created_at,
            latest_version=ResumeVersionOut.of(latest) if latest else None,
        )


class ResumeDetailOut(ResumeOut):
    versions: list[ResumeVersionOut]

    @classmethod
    def of(cls, resume: Resume) -> ResumeDetailOut:
        base = ResumeOut.of(resume)
        return cls(
            **base.model_dump(),
            versions=[ResumeVersionOut.of(v) for v in resume.versions],
        )


class VersionUpdateIn(BaseModel):
    structured: ResumeStructured
