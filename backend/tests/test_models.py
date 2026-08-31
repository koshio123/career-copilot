from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import (
    AnalysisResult,
    Application,
    ApplicationEvent,
    Job,
    JobPosting,
    JobPreference,
    JobSource,
    LlmUsage,
    Resume,
    ResumeVersion,
    User,
)
from app.models.enums import (
    AnalysisKind,
    ApplicationEventKind,
    ApplicationStatus,
    ResumeVersionSource,
    SourceType,
)

EXPECTED_TABLES = {
    "users",
    "job_preferences",
    "resumes",
    "resume_versions",
    "job_sources",
    "jobs",
    "job_postings",
    "applications",
    "application_events",
    "analysis_results",
    "llm_usage",
}


def test_metadata_has_the_expected_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


async def test_full_domain_round_trip(db: AsyncSession) -> None:
    user = User(email="dev@example.com", password_hash="argon2$dummy")
    user.preferences = JobPreference(desired_roles=["Backend Engineer"], remote_required=True)
    resume = Resume(user=user)
    resume.versions.append(
        ResumeVersion(
            user=user,
            version_no=1,
            source=ResumeVersionSource.FORM,
            structured={"skills": ["python", "postgres"]},
        )
    )
    user.resumes.append(resume)

    source = JobSource(user=user, url="https://boards.greenhouse.io/acme")
    user.job_sources.append(source)

    posting = JobPosting(
        user=user,
        dedup_key="greenhouse:acme-123",
        company_name="Acme Inc.",
        company_name_normalized="acme",
        canonical_title="Backend Engineer",
    )
    job = Job(
        user=user,
        job_source=source,
        job_posting=posting,
        url="https://boards.greenhouse.io/acme/jobs/123",
        external_id="123",
        source_type=SourceType.ATS,
        raw_text_hash="0" * 64,
        structured={"title": "Backend Engineer"},
    )

    application = Application(
        user=user,
        job_posting=posting,
        resume_version_id=None,
        status=ApplicationStatus.APPLIED,
    )
    application.events.append(
        ApplicationEvent(
            user=user,
            kind=ApplicationEventKind.STATUS_CHANGE,
            to_status=ApplicationStatus.SCREENING,
            occurred_at=datetime.now(UTC),
        )
    )

    analysis = AnalysisResult(user=user, job_posting=posting, kind=AnalysisKind.GAP_ANALYSIS)
    usage = LlmUsage(user=user, purpose="job_structure", model="claude-sonnet-5", input_tokens=10)

    db.add_all([user, job, application, analysis, usage])
    await db.flush()
    db.expunge_all()

    loaded = (await db.execute(select(User).where(User.email == "dev@example.com"))).scalar_one()
    assert loaded.id is not None
    assert loaded.created_at is not None

    prefs = (
        await db.execute(select(JobPreference).where(JobPreference.user_id == loaded.id))
    ).scalar_one()
    assert prefs.desired_roles == ["Backend Engineer"]

    version = (
        await db.execute(select(ResumeVersion).where(ResumeVersion.user_id == loaded.id))
    ).scalar_one()
    assert version.structured["skills"] == ["python", "postgres"]
    assert version.source is ResumeVersionSource.FORM

    saved_job = (await db.execute(select(Job).where(Job.user_id == loaded.id))).scalar_one()
    assert saved_job.job_posting_id == posting.id
    assert saved_job.first_seen_at is not None  # server default


async def test_cascade_delete_removes_user_graph(db: AsyncSession) -> None:
    user = User(email="cascade@example.com", password_hash="x")
    posting = JobPosting(
        user=user,
        dedup_key="k",
        company_name="C",
        company_name_normalized="c",
        canonical_title="T",
    )
    db.add_all([user, posting])
    await db.flush()
    user_id = user.id

    await db.delete(user)
    await db.flush()

    remaining = (
        (await db.execute(select(JobPosting).where(JobPosting.user_id == user_id))).scalars().all()
    )
    assert remaining == []
