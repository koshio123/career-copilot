from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, TZDateTime, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import JobSource
    from app.models.resume import Resume


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    # Auth is passwordless (email OTP — ADR-0010); no password_hash.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    email_verified_at: Mapped[TZDateTime | None] = mapped_column()
    display_name: Mapped[str | None] = mapped_column(String(120))

    preferences: Mapped[JobPreference | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    resumes: Mapped[list[Resume]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_sources: Mapped[list[JobSource]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class JobPreference(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job_preferences"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    desired_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    locations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    employment_types: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    salary_min: Mapped[int | None] = mapped_column(Integer)  # JPY, annual
    salary_max: Mapped[int | None] = mapped_column(Integer)
    remote_required: Mapped[bool] = mapped_column(default=False)
    target_start: Mapped[date | None] = mapped_column()

    user: Mapped[User] = relationship(back_populates="preferences")
