"""The job_source.fetch worker task (part 1: robots + reachability)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ingest.errors import FetchError
from app.ingest.http import FetchResult
from app.ingest.robots import RobotsDecision
from app.models import JobSource, User
from app.models.enums import JobSourceStatus, RobotsState
from app.workers.tasks import job_source_fetch as task_module


class FakeFetcher:
    def __init__(self, *, decision: RobotsDecision, result: FetchResult | Exception) -> None:
        self._decision = decision
        self._result = result

    async def __aenter__(self) -> FakeFetcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def check_robots(self, url: str) -> RobotsDecision:
        return self._decision

    async def fetch(self, url: str, **_: object) -> FetchResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _ok_result(status: int = 200) -> FetchResult:
    return FetchResult(
        url="https://acme.example/careers",
        status_code=status,
        headers=httpx.Headers(),
        content=b"<html></html>",
        content_type="text/html",
    )


@pytest.fixture
async def worker_sm(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: sm)
    yield sm
    async with sm() as session, session.begin():
        for model in (JobSource, User):
            await session.execute(delete(model))


async def _make_source(sm: async_sessionmaker[AsyncSession], **kw: object) -> str:
    async with sm() as session, session.begin():
        user = User(
            email=f"{datetime.now(UTC).timestamp()}@x.com", email_verified_at=datetime.now(UTC)
        )
        source = JobSource(user=user, url="https://acme.example/careers", **kw)
        session.add_all([user, source])
        await session.flush()
        return str(source.id)


async def _reload(sm: async_sessionmaker[AsyncSession], sid: str) -> JobSource:
    async with sm() as session:
        return (await session.execute(select(JobSource).where(JobSource.id == sid))).scalar_one()


async def test_successful_fetch_records_success(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_fetcher",
        lambda: FakeFetcher(
            decision=RobotsDecision(allowed=True, state=RobotsState.ALLOWED, crawl_delay=None),
            result=_ok_result(),
        ),
    )
    sid = await _make_source(worker_sm)

    await task_module.job_source_fetch({"source_id": sid})

    source = await _reload(worker_sm, sid)
    assert source.robots_state is RobotsState.ALLOWED
    assert source.last_success_at is not None
    assert source.last_error is None
    assert source.consecutive_failures == 0


async def test_robots_disallowed_is_surfaced(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_fetcher",
        lambda: FakeFetcher(
            decision=RobotsDecision(allowed=False, state=RobotsState.ALLOWED, crawl_delay=None),
            result=_ok_result(),
        ),
    )
    sid = await _make_source(worker_sm)

    await task_module.job_source_fetch({"source_id": sid})

    source = await _reload(worker_sm, sid)
    assert source.robots_state is RobotsState.DISALLOWED
    assert source.last_success_at is None
    assert "robots.txt" in (source.last_error or "")
    assert source.consecutive_failures == 1


async def test_fetch_error_increments_failures(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_fetcher",
        lambda: FakeFetcher(
            decision=RobotsDecision(allowed=True, state=RobotsState.ALLOWED, crawl_delay=None),
            result=FetchError("connection reset"),
        ),
    )
    sid = await _make_source(worker_sm, consecutive_failures=4)

    await task_module.job_source_fetch({"source_id": sid})

    source = await _reload(worker_sm, sid)
    assert source.consecutive_failures == 5
    assert source.status is JobSourceStatus.ERROR
