from __future__ import annotations

from datetime import date

from app.jobs.matching import describe_preferences, score_match
from app.jobs.schema import JobStructured
from app.models import JobPreference
from tests.fakes import FakeLlmClient


def test_describe_preferences() -> None:
    prefs = JobPreference(
        desired_roles=["Backend Engineer"],
        locations=["Tokyo", "Remote"],
        remote_required=True,
        salary_min=9_000_000,
        target_start=date(2026, 10, 1),
    )
    text = describe_preferences(prefs)
    assert "Backend Engineer" in text
    assert "¥9,000,000/year" in text
    assert "Remote required: yes" in text


async def test_score_match_returns_outcome_and_usage() -> None:
    llm = FakeLlmClient(
        data={
            "score": 82,
            "rationale": "Backend role in Tokyo, matches well.",
            "matched": ["role", "location"],
            "concerns": ["salary not stated"],
        }
    )
    prefs = JobPreference(desired_roles=["Backend Engineer"], locations=["Tokyo"])
    job = JobStructured(title="Backend Engineer", company_name="Acme", description="Build APIs.")

    outcome, usage = await score_match(prefs, job, llm=llm)  # type: ignore[arg-type]

    assert outcome.score == 82
    assert outcome.concerns == ["salary not stated"]
    assert usage.input_tokens == 100
