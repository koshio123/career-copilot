from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CsrfGuard, JobPostingSvc
from app.schemas.job import JobPostingManualIn, JobPostingOut, JobPostingUpdateIn

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(svc: JobPostingSvc) -> list[JobPostingOut]:
    return [JobPostingOut.of(p) for p in await svc.list()]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[CsrfGuard])
async def add_job(body: JobPostingManualIn, svc: JobPostingSvc) -> JobPostingOut:
    return JobPostingOut.of(await svc.create_manual(body))


@router.get("/{job_id}")
async def get_job(job_id: UUID, svc: JobPostingSvc) -> JobPostingOut:
    return JobPostingOut.of(await svc.get(job_id))


@router.patch("/{job_id}", dependencies=[CsrfGuard])
async def update_job(job_id: UUID, body: JobPostingUpdateIn, svc: JobPostingSvc) -> JobPostingOut:
    return JobPostingOut.of(await svc.update(job_id, body))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfGuard])
async def delete_job(job_id: UUID, svc: JobPostingSvc) -> None:
    await svc.remove(job_id)
