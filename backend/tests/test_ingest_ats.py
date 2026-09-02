"""ATS adapters normalise each vendor's shape onto JobStructured."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from app.ingest.ats import get_adapter
from app.ingest.ats.base import AtsError
from app.ingest.fetcher import PoliteFetcher
from app.models.enums import SourceType
from tests.fakes import FakePoliteFetcher, fetch_result


def _fetch(vendor: str, board: str, fetcher: FakePoliteFetcher) -> Any:
    adapter = get_adapter(vendor)
    assert adapter is not None
    return adapter.fetch(board, fetcher=cast(PoliteFetcher, fetcher))


async def test_greenhouse_adapter() -> None:
    body = json.dumps(
        {
            "jobs": [
                {
                    "id": 42,
                    "title": "Senior Backend Engineer",
                    "content": "&lt;p&gt;Build APIs.&lt;/p&gt;&lt;p&gt;Own reliability.&lt;/p&gt;",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
                    "location": {"name": "Remote - Japan"},
                    "company_name": "Acme",
                }
            ]
        }
    )
    fetcher = FakePoliteFetcher({"boards-api.greenhouse.io": fetch_result(body)})
    jobs = await _fetch("greenhouse", "acme", fetcher)

    assert len(jobs) == 1
    j = jobs[0]
    assert j.external_id == "42"
    assert j.source_type is SourceType.ATS
    assert j.ats_vendor == "greenhouse"
    assert j.structured.title == "Senior Backend Engineer"
    assert "Build APIs." in j.structured.description
    assert j.structured.remote is True
    assert "salary" in j.structured.needs_review


async def test_lever_adapter() -> None:
    body = json.dumps(
        [
            {
                "id": "abc-123",
                "text": "Platform Engineer",
                "descriptionPlain": "Run the platform.",
                "categories": {"location": "Tokyo", "commitment": "Full-time"},
                "workplaceType": "remote",
                "hostedUrl": "https://jobs.lever.co/acme/abc-123",
            }
        ]
    )
    fetcher = FakePoliteFetcher({"api.lever.co": fetch_result(body)})
    jobs = await _fetch("lever", "acme", fetcher)

    assert jobs[0].structured.employment_type == "Full-time"
    assert jobs[0].structured.remote is True
    assert jobs[0].structured.location == "Tokyo"


async def test_ashby_adapter_with_compensation() -> None:
    body = json.dumps(
        {
            "jobs": [
                {
                    "id": "j1",
                    "title": "SRE",
                    "descriptionPlain": "Keep it up.",
                    "location": "Remote",
                    "isRemote": True,
                    "employmentType": "FullTime",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/j1",
                    "compensation": {
                        "summaryComponents": [
                            {
                                "currencyCode": "JPY",
                                "interval": "year",
                                "minValue": 9000000,
                                "maxValue": 13000000,
                            }
                        ]
                    },
                }
            ]
        }
    )
    fetcher = FakePoliteFetcher({"api.ashbyhq.com": fetch_result(body)})
    jobs = await _fetch("ashby", "acme", fetcher)

    assert jobs[0].structured.salary_min == 9_000_000
    assert jobs[0].structured.salary_max == 13_000_000
    assert "salary" not in jobs[0].structured.needs_review


async def test_adapter_raises_on_bad_json() -> None:
    fetcher = FakePoliteFetcher({"boards-api.greenhouse.io": fetch_result("<html>nope</html>")})
    with pytest.raises(AtsError):
        await _fetch("greenhouse", "acme", fetcher)


async def test_adapter_raises_on_http_error() -> None:
    fetcher = FakePoliteFetcher(
        {"api.lever.co": fetch_result("nope", status=404, content_type="text/plain")}
    )
    with pytest.raises(AtsError):
        await _fetch("lever", "acme", fetcher)
