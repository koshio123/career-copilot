"""Route B — schema.org/JobPosting extracted from JSON-LD (ADR-0006).

Many career pages (and every HRMOS / Talentio / Personio site) embed a
``<script type="application/ld+json">`` block with a ``JobPosting`` for Google
for Jobs. We parse those directly — zero tokens, no hallucination. Handles a
single object, a list, and the ``@graph`` wrapper; missing required fields are
flagged in ``needs_review``.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.ingest.textutil import html_to_text
from app.jobs.schema import FetchedJob, JobStructured
from app.models.enums import SourceType

_JPY_UNIT = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}


def _iter_nodes(payload: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            out.append(node)
            if "@graph" in node:
                stack.append(node["@graph"])
    return out


def _is_job_posting(node: dict[str, Any]) -> bool:
    t = node.get("@type")
    return t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t)


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _text(value.get("name"))
    if isinstance(value, list):
        for v in value:
            got = _text(v)
            if got:
                return got
    return None


def _location(node: Any) -> str | None:
    nodes = node if isinstance(node, list) else [node]
    parts: list[str] = []
    for loc in nodes:
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address")
        if isinstance(addr, str):
            parts.append(addr)
        elif isinstance(addr, dict):
            chunk = ", ".join(
                str(addr[k])
                for k in ("addressLocality", "addressRegion", "addressCountry")
                if addr.get(k)
            )
            if chunk:
                parts.append(chunk)
    return "; ".join(dict.fromkeys(parts)) or None


def _salary_jpy(base: Any) -> tuple[int | None, int | None]:
    if not isinstance(base, dict) or base.get("currency") not in (None, "JPY"):
        return None, None
    value = base.get("value")
    if not isinstance(value, dict):
        return None, None
    unit = str(value.get("unitText") or "YEAR").upper()
    mult = _JPY_UNIT.get(unit, 1)

    def scale(x: Any) -> int | None:
        return int(x * mult) if isinstance(x, int | float) else None

    lo = scale(value.get("minValue"))
    hi = scale(value.get("maxValue"))
    if lo is None and hi is None:
        single = scale(value.get("value"))
        return single, single
    return lo, hi


def _employment_type(value: Any) -> str | None:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or None
    return str(value) if value else None


def _one(node: dict[str, Any], base_url: str) -> FetchedJob | None:
    title = _text(node.get("title"))
    if not title:
        return None
    raw_desc = node.get("description")
    description = html_to_text(raw_desc if isinstance(raw_desc, str) else None)
    salary_min, salary_max = _salary_jpy(node.get("baseSalary"))
    remote = str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE" or None

    needs_review: list[str] = []
    if not description:
        needs_review.append("description")
    if salary_min is None and salary_max is None:
        needs_review.append("salary")

    apply_url = _text(node.get("url")) or _text(node.get("@id"))
    return FetchedJob(
        external_id=_text(node.get("identifier")) or apply_url,
        url=urljoin(base_url, apply_url) if apply_url else base_url,
        source_type=SourceType.JSON_LD,
        structured=JobStructured(
            title=title,
            company_name=_text(node.get("hiringOrganization")) or "(unknown)",
            location=_location(node.get("jobLocation")),
            remote=remote,
            employment_type=_employment_type(node.get("employmentType")),
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            apply_url=urljoin(base_url, apply_url) if apply_url else None,
            needs_review=needs_review,
        ),
    )


def extract_job_postings(html: str, *, base_url: str) -> list[FetchedJob]:
    tree = HTMLParser(html)
    seen: set[str] = set()
    jobs: list[FetchedJob] = []
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(deep=True, strip=False)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(payload):
            if not _is_job_posting(node):
                continue
            job = _one(node, base_url)
            if job and job.url not in seen:
                seen.add(job.url)
                jobs.append(job)
    return jobs
