from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonDict, Timestamps, TZDateTime, UUIDPrimaryKey
from app.models.enums import (
    JobPostingStatus,
    JobSourceStatus,
    RobotsState,
    SourceType,
    pg_enum,
)

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User

# Match score, 0.00 to 100.00.
Score = Numeric(5, 2)


class JobSource(UUIDPrimaryKey, Timestamps, Base):
    """A career URL the user registered for periodic crawling (ADR-0006)."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("user_id", "url"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[JobSourceStatus] = mapped_column(
        pg_enum(JobSourceStatus, "job_source_status"),
        default=JobSourceStatus.ACTIVE,
    )

    # Resolved route (null until the first fetch classifies it).
    source_type: Mapped[SourceType | None] = mapped_column(pg_enum(SourceType, "source_type"))
    ats_vendor: Mapped[str | None] = mapped_column(String(50))
    ats_board_id: Mapped[str | None] = mapped_column(String(200))

    robots_state: Mapped[RobotsState] = mapped_column(
        pg_enum(RobotsState, "robots_state"), default=RobotsState.UNKNOWN
    )
    robots_checked_at: Mapped[TZDateTime | None] = mapped_column()

    fetch_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_fetched_at: Mapped[TZDateTime | None] = mapped_column()
    last_success_at: Mapped[TZDateTime | None] = mapped_column()
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="job_sources")
    jobs: Mapped[list[Job]] = relationship(
        back_populates="job_source", cascade="all, delete-orphan"
    )


class JobPosting(UUIDPrimaryKey, Timestamps, Base):
    """A logical job — the deduplicated unit the user interacts with (ADR-0009)."""

    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("user_id", "dedup_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    dedup_key: Mapped[str] = mapped_column(String(255))

    company_name: Mapped[str] = mapped_column(Text)
    company_name_normalized: Mapped[str] = mapped_column(Text, index=True)
    canonical_title: Mapped[str] = mapped_column(Text)
    location_normalized: Mapped[str | None] = mapped_column(Text)

    # Merged "best" structured view across contributing jobs.
    structured: Mapped[JsonDict] = mapped_column(default=dict)

    status: Mapped[JobPostingStatus] = mapped_column(
        pg_enum(JobPostingStatus, "job_posting_status"), default=JobPostingStatus.NEW
    )
    bookmarked: Mapped[bool] = mapped_column(default=False)
    match_score: Mapped[Decimal | None] = mapped_column(Score)

    user: Mapped[User] = relationship()
    jobs: Mapped[list[Job]] = relationship(back_populates="job_posting")
    applications: Mapped[list[Application]] = relationship(back_populates="job_posting")


class Job(UUIDPrimaryKey, Timestamps, Base):
    """One raw fetch of a job from one source/route. Kept for diffing and provenance."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("job_source_id", "url"),
        Index(
            "uq_jobs_job_source_id_external_id",
            "job_source_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), index=True
    )

    external_id: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(pg_enum(SourceType, "source_type"))
    ats_vendor: Mapped[str | None] = mapped_column(String(50))

    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_text_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex
    structured: Mapped[JsonDict] = mapped_column(default=dict)

    needs_review: Mapped[bool] = mapped_column(default=False)
    match_score: Mapped[Decimal | None] = mapped_column(Score)

    first_seen_at: Mapped[TZDateTime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[TZDateTime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship()
    job_source: Mapped[JobSource] = relationship(back_populates="jobs")
    job_posting: Mapped[JobPosting | None] = relationship(back_populates="jobs")
