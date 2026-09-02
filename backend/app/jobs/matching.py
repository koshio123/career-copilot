"""LLM match scoring (CLAUDE.local.md §4.2 step 8).

Runs only on jobs that passed the rule filter. Compares the user's *stated
preferences* (not their skills - that's Phase 07) to the job description and
returns a 0-100 score plus a grounded rationale. The job text is wrapped and
treated as untrusted (prompt-injection defence).
"""

from __future__ import annotations

from app.jobs.schema import (
    MATCH_PROMPT,
    MATCH_SYSTEM,
    MATCH_TOOL_SCHEMA,
    JobStructured,
    MatchOutcome,
)
from app.llm import LlmClient, StructuredResult
from app.models import JobPreference

_MAX_JOB_CHARS = 12_000


def describe_preferences(prefs: JobPreference) -> str:
    lines: list[str] = []
    if prefs.desired_roles:
        lines.append(f"- Roles: {', '.join(prefs.desired_roles)}")
    if prefs.locations:
        lines.append(f"- Locations: {', '.join(prefs.locations)}")
    lines.append(f"- Remote required: {'yes' if prefs.remote_required else 'no'}")
    if prefs.employment_types:
        lines.append(f"- Employment types: {', '.join(prefs.employment_types)}")
    if prefs.salary_min is not None:
        lines.append(f"- Minimum salary: ¥{prefs.salary_min:,}/year")
    if prefs.target_start is not None:
        lines.append(f"- Target start: {prefs.target_start.isoformat()}")
    return "\n".join(lines) or "- (no specific preferences stated)"


def _job_text(s: JobStructured) -> str:
    head = [f"Title: {s.title}", f"Company: {s.company_name}"]
    if s.location:
        head.append(f"Location: {s.location}")
    if s.remote is not None:
        head.append(f"Remote: {'yes' if s.remote else 'no'}")
    if s.employment_type:
        head.append(f"Employment type: {s.employment_type}")
    if s.salary_min or s.salary_max:
        head.append(f"Stated salary (JPY/yr): {s.salary_min} to {s.salary_max}")
    return "\n".join(head) + "\n\n" + s.description[:_MAX_JOB_CHARS]


async def score_match(
    prefs: JobPreference, structured: JobStructured, *, llm: LlmClient
) -> tuple[MatchOutcome, StructuredResult]:
    result = await llm.structured(
        prompt=MATCH_PROMPT.format(
            preferences=describe_preferences(prefs), job=_job_text(structured)
        ),
        schema=MATCH_TOOL_SCHEMA,
        tool_name="score_match",
        system=MATCH_SYSTEM,
        max_tokens=1024,
    )
    return MatchOutcome.model_validate(result.data), result
