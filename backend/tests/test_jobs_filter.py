from __future__ import annotations

import pytest

from app.core.config import settings
from app.jobs.filter import (
    passes_primary_filter,
    rejection_reason,
    title_matches_desired_roles,
)
from app.jobs.schema import JobStructured
from app.models import JobPreference


def _job(**kw: object) -> JobStructured:
    kw.setdefault("title", "Engineer")
    return JobStructured(company_name="Acme", **kw)


@pytest.mark.parametrize(
    ("title", "roles", "expected"),
    [
        ("Senior Backend Engineer", ["Backend Engineer"], True),
        ("Engineering Manager", ["Backend Engineer"], True),  # engineer ~ engineering
        ("Staff Software Developer", ["Software Developer"], True),
        ("Product Manager", ["Backend Engineer"], False),
        ("Data Scientist", ["Backend Engineer", "Platform Engineer"], False),
    ],
)
def test_title_matches_desired_roles(title: str, roles: list[str], expected: bool) -> None:
    assert title_matches_desired_roles(title, roles) is expected


def test_strict_mode_drops_titles_that_dont_match_desired_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_title_match_mode", "strict")
    prefs = JobPreference(desired_roles=["Backend Engineer"])
    assert rejection_reason(_job(title="Product Manager"), prefs) is not None
    assert rejection_reason(_job(title="Senior Backend Engineer"), prefs) is None
    # no desired roles → strict mode can't filter on title
    assert rejection_reason(_job(title="Product Manager"), JobPreference()) is None


def test_off_mode_disables_title_filtering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "job_title_match_mode", "off")
    prefs = JobPreference(desired_roles=["Backend Engineer"])
    assert rejection_reason(_job(title="Sales Development Representative"), prefs) is None


def test_no_prefs_keeps_everything() -> None:
    assert passes_primary_filter(_job(employment_type="Internship"), None) is True


def test_employment_type_mismatch_is_dropped() -> None:
    prefs = JobPreference(employment_types=["full_time"])
    assert rejection_reason(_job(employment_type="Internship"), prefs) is not None
    assert rejection_reason(_job(employment_type="Full-time"), prefs) is None
    # unknown employment type on the job → keep (borderline goes to the LLM)
    assert rejection_reason(_job(), prefs) is None


def test_off_family_title_without_role_overlap_is_dropped() -> None:
    prefs = JobPreference(desired_roles=["Backend Engineer", "Platform Engineer"])
    assert rejection_reason(_job(title="Sales Development Representative"), prefs) is not None
    assert rejection_reason(_job(title="Technical Recruiter"), prefs) is not None
    # shares "engineer" → keep even though "sales" appears
    assert rejection_reason(_job(title="Sales Engineer"), prefs) is None
    # no off-family word, no overlap → ambiguous, keep for the LLM
    assert rejection_reason(_job(title="Software Developer"), prefs) is None
    # no desired roles set → never drop on family
    assert rejection_reason(_job(title="Recruiter"), None) is None


def test_remote_required_vs_onsite() -> None:
    prefs = JobPreference(remote_required=True, locations=["Tokyo"])
    assert rejection_reason(_job(remote=False, location="Osaka"), prefs) is not None
    assert rejection_reason(_job(remote=False, location="Tokyo Office"), prefs) is None
    assert rejection_reason(_job(remote=True, location="Osaka"), prefs) is None
    assert rejection_reason(_job(remote=None), prefs) is None
