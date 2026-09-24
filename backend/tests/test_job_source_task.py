"""The job_source.fetch worker task — full pipeline wiring."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Job, JobPosting, JobPreference, JobSource, LlmUsage, User
from app.models.enums import JobSourceStatus, SourceType
from app.workers.tasks import job_source_fetch as task_module
from tests.fakes import FakeLlmClient, FakePoliteFetcher, fetch_result

GH_PAGE = "https://boards.greenhouse.io/acme"
_API = json.dumps(
    {
        "jobs": [
            {
                "id": 7,
                "title": "Backend Engineer",
                "content": "Build things.",
                "absolute_url": f"{GH_PAGE}/jobs/7",
                "location": {"name": "Tokyo"},
                "company_name": "Acme",
            }
        ]
    }
)


@pytest.fixture
async def worker_sm(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: sm)
    monkeypatch.setattr(
        task_module,
        "get_fetcher",
        lambda: FakePoliteFetcher(
            {
                "boards-api.greenhouse.io": fetch_result(_API, content_type="application/json"),
                "greenhouse.io/acme": fetch_result("<html>x</html>", url=GH_PAGE),
            }
        ),
    )
    monkeypatch.setattr(
        task_module,
        "get_llm_client",
        lambda: FakeLlmClient(data={"score": 66, "rationale": "ok", "matched": [], "concerns": []}),
    )
    yield sm
    async with sm() as session, session.begin():
        for model in (LlmUsage, Job, JobPosting, JobPreference, JobSource, User):
            await session.execute(delete(model))


async def _make_source(sm: async_sessionmaker[AsyncSession], *, prefs: bool = True) -> str:
    async with sm() as session, session.begin():
        user = User(
            email=f"{datetime.now(UTC).timestamp()}@x.com", email_verified_at=datetime.now(UTC)
        )
        source = JobSource(user=user, url=GH_PAGE)
        session.add_all([user, source])
        if prefs:
            session.add(JobPreference(user=user, desired_roles=["Backend Engineer"]))
        await session.flush()
        return str(source.id)


async def test_pipeline_saves_scored_jobs_and_updates_source(
    worker_sm: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _make_source(worker_sm)

    await task_module.job_source_fetch({"source_id": sid})

    async with worker_sm() as session:
        source = (await session.execute(select(JobSource).where(JobSource.id == sid))).scalar_one()
        jobs = (await session.execute(select(Job))).scalars().all()
        usage = (await session.execute(select(LlmUsage))).scalars().all()

    assert source.source_type is SourceType.ATS
    assert source.ats_vendor == "greenhouse"
    assert source.last_success_at is not None
    assert source.last_error is None
    assert len(jobs) == 1
    assert jobs[0].match_score == 66
    assert len(usage) == 1


async def test_unidentifiable_page_sets_error(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_fetcher",
        lambda: FakePoliteFetcher({"example.com": fetch_result("<html>no jobs</html>")}),
    )
    async with worker_sm() as session, session.begin():
        user = User(email="p@x.com", email_verified_at=datetime.now(UTC))
        source = JobSource(user=user, url="https://example.com/careers")
        session.add_all([user, source])
        await session.flush()
        sid = str(source.id)

    await task_module.job_source_fetch({"source_id": sid})

    async with worker_sm() as session:
        source = (await session.execute(select(JobSource).where(JobSource.id == sid))).scalar_one()
    assert source.last_error is not None
    assert source.consecutive_failures == 1
    assert source.status is JobSourceStatus.ACTIVE
