from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonDict, Timestamps, TZDateTime, UUIDPrimaryKey
from app.models.enums import (
    ApplicationEventKind,
    ApplicationStatus,
    pg_enum,
)

if TYPE_CHECKING:
    from app.models.job import JobPosting
    from app.models.user import User


class Application(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_posting_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[ApplicationStatus] = mapped_column(
        pg_enum(ApplicationStatus, "application_status"),
        default=ApplicationStatus.APPLIED,
    )
    applied_at: Mapped[TZDateTime | None] = mapped_column()
    next_action_at: Mapped[TZDateTime | None] = mapped_column()
    notes: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="applications")
    job_posting: Mapped[JobPosting] = relationship(back_populates="applications")
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.occurred_at",
    )


class ApplicationEvent(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "application_events"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ApplicationEventKind] = mapped_column(
        pg_enum(ApplicationEventKind, "application_event_kind")
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        pg_enum(ApplicationStatus, "app_event_from_status")
    )
    to_status: Mapped[ApplicationStatus | None] = mapped_column(
        pg_enum(ApplicationStatus, "app_event_to_status")
    )
    occurred_at: Mapped[TZDateTime] = mapped_column(server_default=func.now())
    # Free-form: {feedback, interviewer, note, ...}
    payload: Mapped[JsonDict] = mapped_column(default=dict)

    user: Mapped[User] = relationship()
    application: Mapped[Application] = relationship(back_populates="events")
