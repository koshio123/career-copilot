"""Rule-based primary filter (CLAUDE.local.md §4.2 step 6).

Cheap, deterministic, and deliberately timid: it only drops jobs that are an
*obvious* mismatch for the user's stated preferences, so we never spend an LLM
call scoring them. Anything borderline passes through to the LLM match score
(step 8). Dropped jobs are not stored.
"""

from __future__ import annotations

import re

from app.jobs.normalize import normalize_text
from app.jobs.schema import JobStructured
from app.models import JobPreference

_SEP = re.compile(r"[\s_-]+")


def _key(value: str) -> str:
    """Fold "full_time" / "Full-time" / "full time" to one token."""
    return _SEP.sub("", normalize_text(value))


def _norm_set(values: list[str]) -> set[str]:
    return {_key(v) for v in values if v.strip()}


def rejection_reason(structured: JobStructured, prefs: JobPreference | None) -> str | None:
    """Return why this job is an obvious mismatch, or None if it should be kept."""
    if prefs is None:
        return None

    wanted_types = _norm_set(prefs.employment_types or [])
    if wanted_types and structured.employment_type:
        job_types = _norm_set(structured.employment_type.replace(",", " ").split())
        if job_types and job_types.isdisjoint(wanted_types):
            return f"employment type {structured.employment_type!r} not in preferences"

    if prefs.remote_required and structured.remote is False:
        wanted_locs = _norm_set(prefs.locations or [])
        job_loc = normalize_text(structured.location or "")
        on_site_ok = bool(wanted_locs) and any(loc in job_loc for loc in wanted_locs if loc)
        if not on_site_ok:
            return "on-site only, but remote is required"

    return None


def passes_primary_filter(structured: JobStructured, prefs: JobPreference | None) -> bool:
    return rejection_reason(structured, prefs) is None
