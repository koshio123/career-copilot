from __future__ import annotations

from app.jobs.filter import passes_primary_filter, rejection_reason
from app.jobs.schema import JobStructured
from app.models import JobPreference


def _job(**kw: object) -> JobStructured:
    return JobStructured(title="Engineer", company_name="Acme", **kw)


def test_no_prefs_keeps_everything() -> None:
    assert passes_primary_filter(_job(employment_type="Internship"), None) is True


def test_employment_type_mismatch_is_dropped() -> None:
    prefs = JobPreference(employment_types=["full_time"])
    assert rejection_reason(_job(employment_type="Internship"), prefs) is not None
    assert rejection_reason(_job(employment_type="Full-time"), prefs) is None
    # unknown employment type on the job → keep (borderline goes to the LLM)
    assert rejection_reason(_job(), prefs) is None


def test_remote_required_vs_onsite() -> None:
    prefs = JobPreference(remote_required=True, locations=["Tokyo"])
    assert rejection_reason(_job(remote=False, location="Osaka"), prefs) is not None
    assert rejection_reason(_job(remote=False, location="Tokyo Office"), prefs) is None
    assert rejection_reason(_job(remote=True, location="Osaka"), prefs) is None
    assert rejection_reason(_job(remote=None), prefs) is None
