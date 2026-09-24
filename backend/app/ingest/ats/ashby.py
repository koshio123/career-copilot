"""Ashby — GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true."""

from __future__ import annotations

from typing import Any

from app.ingest.ats.base import AtsError, get_json
from app.ingest.fetcher import PoliteFetcher
from app.ingest.textutil import first_nonempty, html_to_text
from app.jobs.schema import FetchedJob, JobStructured
from app.models.enums import SourceType

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true"
_JPY_UNIT = {"year": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}


def _annual_jpy(comp: dict[str, Any]) -> tuple[int | None, int | None]:
    for component in comp.get("summaryComponents", []) or []:
        if component.get("currencyCode") != "JPY":
            continue
        interval = (component.get("interval") or "year").lower().rstrip("s")
        mult = _JPY_UNIT.get(interval, 1)
        lo, hi = component.get("minValue"), component.get("maxValue")
        return (
            int(lo * mult) if isinstance(lo, int | float) else None,
            int(hi * mult) if isinstance(hi, int | float) else None,
        )
    return None, None


class AshbyAdapter:
    vendor = "ashby"

    async def fetch(self, board_id: str, *, fetcher: PoliteFetcher) -> list[FetchedJob]:
        data = await get_json(_BASE.format(name=board_id), fetcher=fetcher)
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise AtsError("ashby response has no 'jobs' array")
        return [self._one(j, board_id) for j in jobs if isinstance(j, dict)]

    def _one(self, j: dict[str, Any], board_id: str) -> FetchedJob:
        description = first_nonempty(
            j.get("descriptionPlain"), html_to_text(j.get("descriptionHtml"))
        )
        salary_min, salary_max = _annual_jpy(j.get("compensation") or {})
        needs_review: list[str] = []
        if salary_min is None and salary_max is None:
            needs_review.append("salary")
        if not description:
            needs_review.append("description")
        return FetchedJob(
            external_id=str(j.get("id")),
            url=j.get("jobUrl") or _BASE.format(name=board_id),
            source_type=SourceType.ATS,
            ats_vendor=self.vendor,
            structured=JobStructured(
                title=(j.get("title") or "").strip() or "(untitled)",
                company_name=board_id,
                location=j.get("location"),
                remote=bool(j.get("isRemote")) or None,
                employment_type=j.get("employmentType"),
                salary_min=salary_min,
                salary_max=salary_max,
                description=description or "",
                apply_url=j.get("applyUrl") or j.get("jobUrl"),
                needs_review=needs_review,
            ),
        )
