"""Content hash for the diff gate (CLAUDE.local.md §4.2 step 5).

The hash is compared to the stored ``jobs.raw_text_hash`` *before* any LLM call.
For routes A/B we hash a fixed-field-order serialisation of the structured data
(raw HTML/JSON changes every fetch); route C hashes the extracted body text.
"""

from __future__ import annotations

import hashlib

from app.jobs.schema import JobStructured

_FIELDS = (
    "title",
    "company_name",
    "location",
    "remote",
    "employment_type",
    "salary_min",
    "salary_max",
    "description",
)


def canonical_text(structured: JobStructured) -> str:
    dumped = structured.model_dump()
    lines = [f"{name}={dumped.get(name)!r}" for name in _FIELDS]
    lines.append(f"required_skills={sorted(structured.required_skills)!r}")
    lines.append(f"preferred_skills={sorted(structured.preferred_skills)!r}")
    return "\n".join(lines)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
