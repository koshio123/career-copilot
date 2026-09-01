"""resume.process — extract text (if a file), then LLM-structure it."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import get_sessionmaker
from app.llm import get_llm_client
from app.models import ResumeVersion
from app.models.enums import ResumeVersionStatus
from app.resumes.extract import ExtractionError, content_type_for_key, extract_text
from app.resumes.schema import RESUME_TOOL_SCHEMA, STRUCTURE_PROMPT
from app.storage import get_resume_storage
from app.workers.registry import task

log = structlog.get_logger(__name__)

_MAX_PROMPT_CHARS = 60_000


async def _set(
    sessionmaker: async_sessionmaker[Any],
    version_id: UUID,
    **fields: Any,
) -> None:
    async with sessionmaker() as session, session.begin():
        version = await session.get(ResumeVersion, version_id)
        if version is not None:
            for key, value in fields.items():
                setattr(version, key, value)


@task("resume.process")
async def resume_process(payload: dict[str, Any]) -> None:
    version_id = UUID(payload["version_id"])
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        version = await session.get(ResumeVersion, version_id)
        if version is None:
            log.warning("resume.process.gone", version_id=str(version_id))
            return
        key, raw_text, user_id = version.source_file_key, version.raw_text, version.user_id

    try:
        if key and not raw_text:
            await _set(sessionmaker, version_id, status=ResumeVersionStatus.EXTRACTING)
            data = await get_resume_storage().download(key)
            raw_text = extract_text(data, content_type_for_key(key))
            await _set(sessionmaker, version_id, raw_text=raw_text)

        await _set(sessionmaker, version_id, status=ResumeVersionStatus.STRUCTURING)

        llm = get_llm_client()
        result = await llm.structured(
            prompt=STRUCTURE_PROMPT.format(text=(raw_text or "")[:_MAX_PROMPT_CHARS]),
            schema=RESUME_TOOL_SCHEMA,
        )
        async with sessionmaker() as session, session.begin():
            version = await session.get(ResumeVersion, version_id)
            if version is None:
                return
            version.structured = result.data
            version.status = ResumeVersionStatus.READY
            version.error = None
            session.add(
                llm.usage_row(
                    result,
                    purpose="resume_structure",
                    user_id=user_id,
                    related_kind="resume_version",
                    related_id=version_id,
                )
            )
        log.info("resume.process.done", version_id=str(version_id))
    except ExtractionError as exc:
        await _set(
            sessionmaker,
            version_id,
            status=ResumeVersionStatus.FAILED,
            error=f"Couldn't read that file: {exc}. Try pasting your résumé as text.",
        )
    # ServiceUnavailableError (LLM outage) propagates → queue retry → DLQ.
