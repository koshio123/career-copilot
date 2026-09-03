"""Rule-based primary filter (CLAUDE.local.md §4.2 step 6).

Cheap, deterministic gate before the LLM match score (step 8). Dropped jobs are
not stored. On a large board this is the main cost lever, tuned by
``APP_JOB_TITLE_MATCH_MODE``:

- ``loose`` (default) — drop only obvious mismatches: wrong employment type,
  on-site when remote is required, or a title in a clearly different function
  (sales, recruiting, …) that shares no word with the user's desired roles.
- ``strict`` — additionally require the title to match one of the user's
  desired-role keywords (prefix-aware, so "engineer" matches "Engineering
  Manager"). Everything else is dropped without an LLM call.
- ``off`` — no title-based filtering at all.
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.jobs.normalize import normalize_text
from app.jobs.schema import JobStructured
from app.models import JobPreference

_SEP = re.compile(r"[\s_-]+")
_WORD = re.compile(r"[a-z0-9]+")

# Seniority / filler words carry no role signal — ignore them when matching.
_GENERIC = frozenset(
    {"senior", "junior", "lead", "staff", "principal", "mid", "level", "i", "ii", "iii", "iv"}
)

# Job-family words that are unambiguously a different function from an
# engineering / product / data search. If a title has one of these and shares
# no word with the user's desired roles, it's an obvious category mismatch.
_OFF_FAMILY = frozenset(
    {
        "sales",
        "seller",
        "salesperson",
        "marketing",
        "recruiter",
        "recruiting",
        "sourcer",
        "accountant",
        "accounting",
        "payroll",
        "bookkeeper",
        "paralegal",
        "attorney",
        "receptionist",
        "concierge",
        "barista",
        "janitor",
    }
)


def _key(value: str) -> str:
    """Fold "full_time" / "Full-time" / "full time" to one token."""
    return _SEP.sub("", normalize_text(value))


def _norm_set(values: list[str]) -> set[str]:
    return {_key(v) for v in values if v.strip()}


def _words(text: str) -> set[str]:
    return set(_WORD.findall(normalize_text(text))) - _GENERIC


def _prefix_match(a: str, b: str, *, n: int = 4) -> bool:
    """True if a and b share a leading run of >= n chars (engineer / engineering)."""
    return len(a) >= n and len(b) >= n and (a.startswith(b[:n]) or b.startswith(a[:n]))


def title_matches_desired_roles(title: str, desired_roles: list[str]) -> bool:
    title_words = _words(title)
    role_words = {w for role in desired_roles for w in _words(role) if len(w) >= 3}
    if role_words & title_words:
        return True
    return any(_prefix_match(rw, tw) for rw in role_words for tw in title_words)


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

    desired = prefs.desired_roles or []
    mode = settings.job_title_match_mode
    if desired and mode != "off":
        matches = title_matches_desired_roles(structured.title, desired)
        if not matches and mode == "strict":
            return f"title {structured.title!r} doesn't match your desired roles"
        if not matches and (_words(structured.title) & _OFF_FAMILY):
            return f"title {structured.title!r} is a different job family from your desired roles"

    return None


def passes_primary_filter(structured: JobStructured, prefs: JobPreference | None) -> bool:
    return rejection_reason(structured, prefs) is None
