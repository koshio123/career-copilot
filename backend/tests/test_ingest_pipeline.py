"""End-to-end ingestion: resolve() (fetch/classify/filter/score) + persist()."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobPosting, JobPreference, JobSource, LlmUsage, User
from app.repositories.jobs import JobIngestRepository
from app.services.ingest import JobIngestPipeline, persist
from tests.fakes import FakeLlmClient, FakePoliteFetcher, fetch_result

GH_PAGE = "https://boards.greenhouse.io/acme"


def _gh_api(*titles: str) -> str:
    return json.dumps(
        {
            "jobs": [
                {
                    "id": 100 + i,
                    "title": t,
                    "content": "&lt;p&gt;Do the work.&lt;/p&gt;",
                    "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{100 + i}",
                    "location": {"name": "Tokyo"},
                    "company_name": "Acme",
                }
                for i, t in enumerate(titles)
            ]
        }
    )


def _fetcher(api_body: str) -> FakePoliteFetcher:
    return FakePoliteFetcher(
        {
            "boards-api.greenhouse.io": fetch_result(api_body, content_type="application/json"),
            "greenhouse.io/acme": fetch_result("<html>careers</html>", url=GH_PAGE),
        }
    )


async def _user_and_source(db: AsyncSession, *, with_prefs: bool) -> tuple[User, JobSource]:
    user = User(email=f"{datetime.now(UTC).timestamp()}@x.com", email_verified_at=datetime.now(UTC))
    source = JobSource(user=user, url=GH_PAGE)
    db.add_all([user, source])
    if with_prefs:
        db.add(JobPreference(user=user, desired_roles=["Backend Engineer"], locations=["Tokyo"]))
    await db.flush()
    return user, source


async def _run(  # type: ignore[no-untyped-def]
    db: AsyncSession,
    source: JobSource,
    user: User,
    fetcher: FakePoliteFetcher,
    llm: FakeLlmClient,
):
    prefs = (
        await db.execute(select(JobPreference).where(JobPreference.user_id == user.id))
    ).scalar_one_or_none()
    repo = JobIngestRepository(db, user_id=user.id)
    known = await repo.known_hashes(source.id)
    pipeline = JobIngestPipeline(fetcher=fetcher, llm=llm)  # type: ignore[arg-type]
    resolved = await pipeline.resolve(source_url=source.url, known_hashes=known, prefs=prefs)
    result = await persist(
        repo,
        source_id=source.id,
        resolved=resolved,
        llm=llm,  # type: ignore[arg-type]
    )
    return resolved, result


async def test_greenhouse_jobs_scored_and_saved(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=True)
    llm = FakeLlmClient(data={"score": 70, "rationale": "fits", "matched": [], "concerns": []})

    resolved, result = await _run(db, source, user, _fetcher(_gh_api("Backend Engineer")), llm)

    assert resolved.route == "ats"
    assert result.saved == 1
    job = (await db.execute(select(Job))).scalar_one()
    assert job.match_score == 70
    assert job.structured["match"]["rationale"] == "fits"
    posting = (await db.execute(select(JobPosting))).scalar_one()
    assert posting.match_score == 70
    assert posting.canonical_title == "Backend Engineer"
    assert (await db.execute(select(LlmUsage))).scalar_one().purpose == "job_match"


async def test_below_threshold_is_not_saved(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=True)
    llm = FakeLlmClient(data={"score": 12, "rationale": "no", "matched": [], "concerns": []})

    # title passes the rule filter (shares "engineer"), but the LLM scores it low
    resolved, result = await _run(db, source, user, _fetcher(_gh_api("Data Engineer")), llm)

    assert resolved.below_threshold == 1
    assert result.saved == 0
    assert (await db.execute(select(Job))).first() is None


async def test_off_family_job_is_rule_filtered_without_llm(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=True)  # desired: Backend Engineer
    llm = FakeLlmClient(data={"score": 99, "rationale": "x", "matched": [], "concerns": []})

    resolved, result = await _run(db, source, user, _fetcher(_gh_api("Technical Recruiter")), llm)

    assert resolved.filtered == 1
    assert resolved.below_threshold == 0
    assert result.saved == 0
    assert (await db.execute(select(LlmUsage))).first() is None  # no LLM call


async def test_no_prefs_saves_without_scoring(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=False)
    llm = FakeLlmClient()

    _, result = await _run(db, source, user, _fetcher(_gh_api("Backend Engineer")), llm)

    assert result.saved == 1
    assert (await db.execute(select(Job))).scalar_one().match_score is None
    assert (await db.execute(select(LlmUsage))).first() is None


async def test_unchanged_job_is_skipped_on_second_run(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=False)
    llm = FakeLlmClient()
    await _run(db, source, user, _fetcher(_gh_api("Backend Engineer")), llm)

    resolved, result = await _run(db, source, user, _fetcher(_gh_api("Backend Engineer")), llm)

    assert resolved.unchanged == 1
    assert result.saved == 0


async def test_disappeared_job_is_pruned(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=False)
    llm = FakeLlmClient()
    await _run(db, source, user, _fetcher(_gh_api("A", "B")), llm)
    assert len((await db.execute(select(Job))).scalars().all()) == 2

    _, result = await _run(db, source, user, _fetcher(_gh_api("A")), llm)

    assert result.pruned == 2  # the disappeared job + its now-orphan posting
    remaining = (await db.execute(select(Job))).scalars().all()
    assert len(remaining) == 1
    assert len((await db.execute(select(JobPosting))).scalars().all()) == 1


async def test_unreachable_source_reports_error(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=False)
    fetcher = FakePoliteFetcher({})  # nothing canned → FetchError
    resolved, _ = await _run(db, source, user, fetcher, FakeLlmClient())
    assert resolved.error is not None
    assert not resolved.ok


async def test_robots_disallowed(db: AsyncSession) -> None:
    user, source = await _user_and_source(db, with_prefs=False)
    fetcher = FakePoliteFetcher({}, robots_allowed=False)
    resolved, _ = await _run(db, source, user, fetcher, FakeLlmClient())
    assert resolved.needs_manual is True
