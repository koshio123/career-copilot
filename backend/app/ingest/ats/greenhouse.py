"""Greenhouse — GET boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true."""

from __future__ import annotations

from typing import Any

from app.ingest.ats.base import AtsError, get_json
from app.ingest.fetcher import PoliteFetcher
from app.ingest.textutil import html_to_text
from app.jobs.schema import FetchedJob, JobStructured
from app.models.enums import SourceType

_BASE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


class GreenhouseAdapter:
    vendor = "greenhouse"

    async def fetch(self, board_id: str, *, fetcher: PoliteFetcher) -> list[FetchedJob]:
        data = await get_json(_BASE.format(board=board_id), fetcher=fetcher)
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise AtsError("greenhouse response has no 'jobs' array")
        return [self._one(j, board_id) for j in jobs if isinstance(j, dict)]

    def _one(self, j: dict[str, Any], board_id: str) -> FetchedJob:
        description = html_to_text(j.get("content"))
        location = (j.get("location") or {}).get("name")
        offices = [o.get("name") for o in j.get("offices", []) if o.get("name")]
        remote = any("remote" in (name or "").lower() for name in [location, *offices])
        needs_review = ["salary"]
        if not description:
            needs_review.append("description")
        return FetchedJob(
            external_id=str(j["id"]),
            url=j.get("absolute_url") or _BASE.format(board=board_id),
            source_type=SourceType.ATS,
            ats_vendor=self.vendor,
            structured=JobStructured(
                title=j.get("title", "").strip() or "(untitled)",
                company_name=(j.get("company_name") or board_id).strip(),
                location=location,
                remote=remote or None,
                description=description,
                apply_url=j.get("absolute_url"),
                needs_review=needs_review,
            ),
        )
