from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CsrfGuard, ResumeSvc
from app.schemas.resume import (
    ResumeCreateIn,
    ResumeDetailOut,
    ResumeOut,
    ResumeVersionOut,
    UploadOut,
    UploadRequestIn,
    VersionUpdateIn,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/uploads")
async def create_upload_url(body: UploadRequestIn, svc: ResumeSvc) -> UploadOut:
    upload = svc.create_upload(content_type=body.content_type)
    return UploadOut(key=upload.key, url=upload.url, max_bytes=upload.max_bytes)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[CsrfGuard])
async def create_resume(body: ResumeCreateIn, svc: ResumeSvc) -> ResumeOut:
    return ResumeOut.of(await svc.register(body))


@router.get("")
async def list_resumes(svc: ResumeSvc) -> list[ResumeOut]:
    return [ResumeOut.of(r) for r in await svc.list()]


@router.get("/{resume_id}")
async def get_resume(resume_id: UUID, svc: ResumeSvc) -> ResumeDetailOut:
    return ResumeDetailOut.of(await svc.get(resume_id))


@router.get("/{resume_id}/versions/{version_id}")
async def get_version(resume_id: UUID, version_id: UUID, svc: ResumeSvc) -> ResumeVersionOut:
    return ResumeVersionOut.of(await svc.get_version(version_id))


@router.patch("/{resume_id}/versions/{version_id}", dependencies=[CsrfGuard])
async def update_version(
    resume_id: UUID, version_id: UUID, body: VersionUpdateIn, svc: ResumeSvc
) -> ResumeVersionOut:
    return ResumeVersionOut.of(await svc.update_structured(version_id, body.structured))
