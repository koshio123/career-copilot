"""The common structured job schema.

Every route (A: ATS, B: JSON-LD, C: LLM) and manual entry converge on this shape,
stored in ``jobs.structured`` / ``job_postings.structured`` (ADR-0006, ADR-0009).
Part 1 uses it for manual entry; part 2 fills it from the ingestion routes and
adds the LLM tool schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobStructured(BaseModel):
    title: str
    company_name: str
    location: str | None = None
    remote: bool | None = None
    employment_type: str | None = None
    salary_min: int | None = Field(default=None, ge=0)  # JPY, annual
    salary_max: int | None = Field(default=None, ge=0)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    description: str = ""
    apply_url: str | None = None
    # Fields the source left blank that a human should confirm.
    needs_review: list[str] = Field(default_factory=list)
