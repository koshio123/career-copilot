from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonDict, Timestamps, UUIDPrimaryKey
from app.models.enums import ResumeVersionSource, ResumeVersionStatus, pg_enum

if TYPE_CHECKING:
    from app.models.job import JobPosting
    from app.models.user import User


class Resume(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(200), default="My résumé")
    is_primary: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="resumes")
    versions: Mapped[list[ResumeVersion]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ResumeVersion.version_no",
    )


class ResumeVersion(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resume_versions"
    __table_args__ = (UniqueConstraint("resume_id", "version_no"),)

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    source: Mapped[ResumeVersionSource] = mapped_column(
        pg_enum(ResumeVersionSource, "resume_version_source")
    )
    status: Mapped[ResumeVersionStatus] = mapped_column(
        pg_enum(ResumeVersionStatus, "resume_version_status"),
        default=ResumeVersionStatus.PENDING,
    )
    error: Mapped[str | None] = mapped_column(Text)

    # Set when this version is a per-job tailored variant (Phase 07).
    tailored_for_job_posting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), index=True
    )

    raw_text: Mapped[str | None] = mapped_column(Text)
    # Structured content: {companies: [...], skills: [...], summary: "...", ...}
    structured: Mapped[JsonDict] = mapped_column(default=dict)
    # S3 key of the uploaded PDF/DOCX, if any.
    source_file_key: Mapped[str | None] = mapped_column(String(1024))

    user: Mapped[User] = relationship()
    resume: Mapped[Resume] = relationship(back_populates="versions")
    tailored_for: Mapped[JobPosting | None] = relationship()
