"""The structured résumé shape.

Used two ways: as the JSON Schema the LLM must fill (forced tool use), and as
Pydantic models that validate user edits at the API boundary. Keep them in sync.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Achievement(BaseModel):
    text: str
    has_metric: bool = Field(
        description="True if the achievement already contains a concrete number or metric."
    )
    suggestion: str | None = Field(
        default=None,
        description="If has_metric is false, a short hint on how to quantify it.",
    )


class Company(BaseModel):
    name: str
    role: str
    period_start: str | None = None
    period_end: str | None = None
    achievements: list[Achievement] = Field(default_factory=list)


class ResumeStructured(BaseModel):
    summary: str = ""
    companies: list[Company] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


# JSON Schema for the Anthropic tool. Derived from the Pydantic model but hand-held
# so descriptions read well to the model.
RESUME_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-3 sentence professional summary."},
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "period_start": {"type": ["string", "null"], "description": "e.g. 2021-04"},
                    "period_end": {"type": ["string", "null"], "description": "null if current"},
                    "achievements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "has_metric": {"type": "boolean"},
                                "suggestion": {
                                    "type": ["string", "null"],
                                    "description": "How to quantify it, if has_metric is false.",
                                },
                            },
                            "required": ["text", "has_metric"],
                        },
                    },
                },
                "required": ["name", "role", "achievements"],
            },
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete skills/technologies, deduplicated.",
        },
    },
    "required": ["summary", "companies", "skills"],
}

STRUCTURE_PROMPT = """\
Structure the résumé below into the tool schema. Use only what the text says —
never invent employers, dates, or achievements.

For every achievement, set `has_metric` true only if it already contains a
concrete number/percentage/scale. When false, put a one-line `suggestion` for how
the person could quantify it.

<resume>
{text}
</resume>
"""
