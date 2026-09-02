"""Lever — GET api.lever.co/v0/postings/{company}?mode=json."""

from __future__ import annotations

from typing import Any

from app.ingest.ats.base import AtsError, get_json
from app.ingest.fetcher import PoliteFetcher
from app.ingest.textutil import first_nonempty, html_to_text
from app.jobs.schema import FetchedJob, JobStructured
from app.models.enums import SourceType

_BASE = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverAdapter:
    vendor = "lever"

    async def fetch(self, board_id: str, *, fetcher: PoliteFetcher) -> list[FetchedJob]:
        data = await get_json(_BASE.format(company=board_id), fetcher=fetcher)
        if not isinstance(data, list):
            raise AtsError("lever response is not a list of postings")
        return [self._one(p, board_id) for p in data if isinstance(p, dict)]

    def _one(self, p: dict[str, Any], board_id: str) -> FetchedJob:
        cats = p.get("categories") or {}
        description = first_nonempty(p.get("descriptionPlain"), html_to_text(p.get("description")))
        workplace = (p.get("workplaceType") or "").lower()
        location = cats.get("location")
        needs_review = ["salary"]
        if not description:
            needs_review.append("description")
        return FetchedJob(
            external_id=str(p.get("id")),
            url=p.get("hostedUrl") or _BASE.format(company=board_id),
            source_type=SourceType.ATS,
            ats_vendor=self.vendor,
            structured=JobStructured(
                title=(p.get("text") or "").strip() or "(untitled)",
                company_name=board_id,
                location=location,
                remote=(workplace == "remote") or None,
                employment_type=cats.get("commitment"),
                description=description or "",
                apply_url=p.get("applyUrl") or p.get("hostedUrl"),
                needs_review=needs_review,
            ),
        )
