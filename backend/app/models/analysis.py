from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonDict, Timestamps, UUIDPrimaryKey
from app.models.enums import AnalysisKind, AnalysisStatus, pg_enum

if TYPE_CHECKING:
    from app.models.job import JobPosting
    from app.models.user import User


class AnalysisResult(UUIDPrimaryKey, Timestamps, Base):
    """Output of a gap analysis or résumé-tailoring run (Phase 07)."""

    __tablename__ = "analysis_results"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), index=True
    )

    kind: Mapped[AnalysisKind] = mapped_column(pg_enum(AnalysisKind, "analysis_kind"))
    status: Mapped[AnalysisStatus] = mapped_column(
        pg_enum(AnalysisStatus, "analysis_status"), default=AnalysisStatus.PENDING
    )

    # gap: {missing_skills, recommendations, evidence: [{quote, source}], confidence}
    # tailoring: {summary_of_changes, diff, ...}
    result: Mapped[JsonDict] = mapped_column(default=dict)

    # For tailoring runs: the résumé version this run generated.
    produced_resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL")
    )

    needs_review: Mapped[bool] = mapped_column(default=False)
    model: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship()
    job_posting: Mapped[JobPosting] = relationship()
