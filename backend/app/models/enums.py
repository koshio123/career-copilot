"""Domain enums.

Stored as plain ``VARCHAR`` (``native_enum=False``, no DB CHECK). Native PG enums
are rejected (``ALTER TYPE`` pain); an implicit CHECK does not round-trip through
Alembic autogenerate (it re-proposes dropping it every ``alembic check``). Values
are validated at the Python layer by the ``Enum`` type (``validate_strings``) and
by Pydantic at the API boundary. See ADR-0009.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum


class SourceType(enum.StrEnum):
    ATS = "ats"
    JSON_LD = "json_ld"
    LLM = "llm"


class JobSourceStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class RobotsState(enum.StrEnum):
    ALLOWED = "allowed"
    DISALLOWED = "disallowed"
    UNKNOWN = "unknown"


class JobPostingStatus(enum.StrEnum):
    NEW = "new"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    ARCHIVED = "archived"


class ApplicationStatus(enum.StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    FIRST_INTERVIEW = "first_interview"
    FINAL_INTERVIEW = "final_interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationEventKind(enum.StrEnum):
    STATUS_CHANGE = "status_change"
    NOTE = "note"
    INTERVIEW = "interview"
    REMINDER = "reminder"


class ResumeVersionSource(enum.StrEnum):
    UPLOAD = "upload"
    FORM = "form"
    LLM_EXTRACT = "llm_extract"
    TAILORED = "tailored"


class ResumeVersionStatus(enum.StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    STRUCTURING = "structuring"
    READY = "ready"
    FAILED = "failed"


class AnalysisKind(enum.StrEnum):
    GAP_ANALYSIS = "gap_analysis"
    RESUME_TAILORING = "resume_tailoring"


class AnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def pg_enum(enum_cls: type[enum.StrEnum], name: str) -> SAEnum:
    """A VARCHAR column type backed by a StrEnum, validated in Python."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )
