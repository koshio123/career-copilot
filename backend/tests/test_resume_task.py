"""The resume.process worker task (extraction + LLM structuring)."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.errors import ServiceUnavailableError
from app.models import LlmUsage, Resume, ResumeVersion, User
from app.models.enums import ResumeVersionSource, ResumeVersionStatus
from app.workers.tasks import resume_process as task_module
from tests.fakes import FakeLlmClient, FakeResumeStorage


@pytest.fixture
async def worker_sm(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: sm)
    yield sm
    async with sm() as session, session.begin():
        for model in (LlmUsage, ResumeVersion, Resume, User):
            await session.execute(delete(model))


async def _make_version(
    sm: async_sessionmaker[AsyncSession],
    *,
    source: ResumeVersionSource,
    status: ResumeVersionStatus,
    raw_text: str | None = None,
    source_file_key: str | None = None,
) -> str:
    async with sm() as session, session.begin():
        user = User(
            email=f"{datetime.now(UTC).timestamp()}@x.com", email_verified_at=datetime.now(UTC)
        )
        resume = Resume(user=user)
        version = ResumeVersion(
            user=user,
            resume=resume,
            version_no=1,
            source=source,
            status=status,
            raw_text=raw_text,
            source_file_key=source_file_key,
        )
        session.add_all([user, resume, version])
        await session.flush()
        return str(version.id)


async def _reload(sm: async_sessionmaker[AsyncSession], version_id: str) -> ResumeVersion:
    async with sm() as session:
        result = await session.execute(select(ResumeVersion).where(ResumeVersion.id == version_id))
        version: ResumeVersion = result.scalar_one()
        return version


async def test_structures_a_text_version(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_llm_client",
        lambda: FakeLlmClient(data={"summary": "x", "companies": [], "skills": ["go"]}),
    )
    vid = await _make_version(
        worker_sm,
        source=ResumeVersionSource.FORM,
        status=ResumeVersionStatus.STRUCTURING,
        raw_text="Backend engineer, six years, Python and Go.",
    )

    await task_module.resume_process({"version_id": vid})

    version = await _reload(worker_sm, vid)
    assert version.status is ResumeVersionStatus.READY
    assert version.structured["skills"] == ["go"]

    async with worker_sm() as session:
        usage = (await session.execute(select(LlmUsage))).scalars().all()
    assert len(usage) == 1
    assert usage[0].purpose == "resume_structure"


async def test_extracts_a_docx_then_structures(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    import docx

    document = docx.Document()
    document.add_paragraph(
        "Jane Doe — Platform Engineer. Six years across Kubernetes, Terraform and AWS. "
        "Cut deployment time and ran the on-call rotation."
    )
    buffer = io.BytesIO()
    document.save(buffer)

    storage = FakeResumeStorage()
    key = "resumes/u/abc.docx"
    storage.put(key, buffer.getvalue())
    monkeypatch.setattr(task_module, "get_resume_storage", lambda: storage)
    monkeypatch.setattr(task_module, "get_llm_client", lambda: FakeLlmClient())

    vid = await _make_version(
        worker_sm,
        source=ResumeVersionSource.UPLOAD,
        status=ResumeVersionStatus.PENDING,
        source_file_key=key,
    )
    await task_module.resume_process({"version_id": vid})

    version = await _reload(worker_sm, vid)
    assert version.status is ResumeVersionStatus.READY
    assert version.raw_text is not None
    assert "Kubernetes" in version.raw_text


async def test_unreadable_file_marks_the_version_failed(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = FakeResumeStorage()
    key = "resumes/u/broken.pdf"
    storage.put(key, b"this is not a pdf")
    monkeypatch.setattr(task_module, "get_resume_storage", lambda: storage)
    monkeypatch.setattr(task_module, "get_llm_client", lambda: FakeLlmClient())

    vid = await _make_version(
        worker_sm,
        source=ResumeVersionSource.UPLOAD,
        status=ResumeVersionStatus.PENDING,
        source_file_key=key,
    )
    await task_module.resume_process({"version_id": vid})

    version = await _reload(worker_sm, vid)
    assert version.status is ResumeVersionStatus.FAILED
    assert version.error is not None


async def test_llm_outage_propagates_for_retry(
    worker_sm: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        task_module,
        "get_llm_client",
        lambda: FakeLlmClient(error=ServiceUnavailableError("down")),
    )
    vid = await _make_version(
        worker_sm,
        source=ResumeVersionSource.FORM,
        status=ResumeVersionStatus.STRUCTURING,
        raw_text="Backend engineer with plenty of experience in distributed systems.",
    )

    with pytest.raises(ServiceUnavailableError):
        await task_module.resume_process({"version_id": vid})
