from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models import JobSource
from app.models.enums import JobSourceStatus, RobotsState, SourceType


class JobSourceCreateIn(BaseModel):
    url: str = Field(max_length=2000)
    label: str | None = Field(default=None, max_length=200)
    fetch_interval_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("url must be an http(s) URL")
        return value


class JobSourceOut(BaseModel):
    id: UUID
    url: str
    label: str | None
    status: JobSourceStatus
    source_type: SourceType | None
    ats_vendor: str | None
    robots_state: RobotsState
    fetch_interval_hours: int
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime

    @classmethod
    def of(cls, source: JobSource) -> JobSourceOut:
        return cls(
            id=source.id,
            url=source.url,
            label=source.label,
            status=source.status,
            source_type=source.source_type,
            ats_vendor=source.ats_vendor,
            robots_state=source.robots_state,
            fetch_interval_hours=source.fetch_interval_hours,
            last_fetched_at=source.last_fetched_at,
            last_success_at=source.last_success_at,
            last_error=source.last_error,
            consecutive_failures=source.consecutive_failures,
            created_at=source.created_at,
        )
