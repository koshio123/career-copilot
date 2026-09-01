from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.jobs.schema import JobStructured
from app.models import JobPosting
from app.models.enums import JobPostingStatus


class JobPostingManualIn(BaseModel):
    """Add a job the pipeline can't reach — the user types it in (MVP§3.3)."""

    company_name: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    remote: bool | None = None
    employment_type: str | None = Field(default=None, max_length=60)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=20_000)
    apply_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _salary_order(self) -> JobPostingManualIn:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must not exceed salary_max")
        return self

    def to_structured(self) -> JobStructured:
        return JobStructured(
            title=self.title,
            company_name=self.company_name,
            location=self.location,
            remote=self.remote,
            employment_type=self.employment_type,
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            required_skills=self.required_skills,
            preferred_skills=self.preferred_skills,
            description=self.description,
            apply_url=self.apply_url,
        )


class JobPostingUpdateIn(BaseModel):
    status: JobPostingStatus | None = None
    bookmarked: bool | None = None


class JobPostingOut(BaseModel):
    id: UUID
    company_name: str
    canonical_title: str
    location_normalized: str | None
    status: JobPostingStatus
    bookmarked: bool
    match_score: float | None
    structured: dict[str, Any]
    source_type: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, posting: JobPosting) -> JobPostingOut:
        return cls(
            id=posting.id,
            company_name=posting.company_name,
            canonical_title=posting.canonical_title,
            location_normalized=posting.location_normalized,
            status=posting.status,
            bookmarked=posting.bookmarked,
            match_score=float(posting.match_score) if posting.match_score is not None else None,
            structured=posting.structured,
            source_type=(posting.structured or {}).get("source_type"),
            created_at=posting.created_at,
            updated_at=posting.updated_at,
        )
