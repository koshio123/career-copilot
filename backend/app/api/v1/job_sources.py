from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CsrfGuard, JobSourceSvc
from app.models.enums import JobSourceStatus
from app.schemas.job_source import JobSourceCreateIn, JobSourceOut

router = APIRouter(prefix="/job-sources", tags=["job-sources"])


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[CsrfGuard])
async def register_source(body: JobSourceCreateIn, svc: JobSourceSvc) -> JobSourceOut:
    return JobSourceOut.of(await svc.register(body))


@router.get("")
async def list_sources(svc: JobSourceSvc) -> list[JobSourceOut]:
    return [JobSourceOut.of(s) for s in await svc.list()]


@router.get("/{source_id}")
async def get_source(source_id: UUID, svc: JobSourceSvc) -> JobSourceOut:
    return JobSourceOut.of(await svc.get(source_id))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfGuard])
async def delete_source(source_id: UUID, svc: JobSourceSvc) -> None:
    await svc.remove(source_id)


@router.post("/{source_id}/pause", dependencies=[CsrfGuard])
async def pause_source(source_id: UUID, svc: JobSourceSvc) -> JobSourceOut:
    return JobSourceOut.of(await svc.set_status(source_id, JobSourceStatus.PAUSED))


@router.post("/{source_id}/resume", dependencies=[CsrfGuard])
async def resume_source(source_id: UUID, svc: JobSourceSvc) -> JobSourceOut:
    return JobSourceOut.of(await svc.set_status(source_id, JobSourceStatus.ACTIVE))


@router.post("/{source_id}/fetch", dependencies=[CsrfGuard])
async def fetch_source_now(source_id: UUID, svc: JobSourceSvc) -> JobSourceOut:
    return JobSourceOut.of(await svc.trigger_fetch(source_id))
