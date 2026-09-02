"""Job ingestion pipeline (CLAUDE.local.md §4.2).

Given one ``JobSource``: fetch it, classify the route (A: ATS API, B: JSON-LD;
C is Phase 06 part 2b), then for each job — diff-gate, rule-filter, LLM
match-score, threshold-gate — persist the survivors and prune the rest.

Split so a DB transaction is never held across an LLM call:

- :meth:`JobIngestPipeline.resolve` — fetch, classify, filter, score. No DB.
- :func:`persist` — one short transaction: upsert jobs + postings, prune stale,
  write ``llm_usage`` rows.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from pydantic import ValidationError

from app.core.config import settings
from app.ingest.ats import get_adapter
from app.ingest.ats.base import AtsError
from app.ingest.detect import detect_ats
from app.ingest.errors import FetchError
from app.ingest.fetcher import PoliteFetcher
from app.ingest.jsonld import extract_job_postings
from app.jobs.diff import canonical_text, content_hash
from app.jobs.filter import rejection_reason
from app.jobs.matching import score_match
from app.jobs.normalize import dedup_key as fallback_dedup_key
from app.jobs.normalize import normalize_company, normalize_text
from app.jobs.schema import FetchedJob, MatchOutcome
from app.llm import LlmClient, StructuredResult
from app.models import Job, JobPosting, JobPreference
from app.models.enums import RobotsState
from app.repositories.jobs import JobIngestRepository

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class ScoredJob:
    job: FetchedJob
    canonical: str
    digest: str
    outcome: MatchOutcome | None
    usage: StructuredResult | None


@dataclass(slots=True)
class ResolvedIngest:
    route: str | None = None
    ats_vendor: str | None = None
    robots_state: RobotsState = RobotsState.UNKNOWN
    error: str | None = None
    needs_manual: bool = False
    fetched: int = 0
    unchanged: int = 0
    filtered: int = 0
    below_threshold: int = 0
    scoring_failed: int = 0
    keep: list[ScoredJob] = field(default_factory=list)
    # job identities that should remain in the DB after this run: freshly kept
    # jobs plus unchanged ones. Anything else held for the source is pruned
    # (disappeared from the board, or stopped matching).
    survivors: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return self.error is None


class JobIngestPipeline:
    def __init__(self, *, fetcher: PoliteFetcher, llm: LlmClient) -> None:
        self._fetcher = fetcher
        self._llm = llm
        self._threshold = settings.match_score_threshold

    async def resolve(
        self,
        *,
        source_url: str,
        known_hashes: dict[str, str],
        prefs: JobPreference | None,
    ) -> ResolvedIngest:
        out = ResolvedIngest()

        decision = None
        with contextlib.suppress(FetchError):
            decision = await self._fetcher.check_robots(source_url)
        if decision is not None and not decision.allowed:
            out.robots_state = RobotsState.DISALLOWED
            out.error = "robots.txt disallows this URL — add the job pages manually."
            out.needs_manual = True
            return out
        out.robots_state = decision.state if decision else RobotsState.UNKNOWN

        try:
            page = await self._fetcher.fetch(source_url)
        except FetchError as exc:
            out.error = f"Couldn't fetch the page: {exc}"
            return out
        if page.status_code >= 400:
            out.error = f"The page returned HTTP {page.status_code}."
            return out

        jobs, out.route, out.ats_vendor = await self._classify(page.text, str(page.url))
        out.fetched = len(jobs)
        if out.route is None:
            out.error = "Couldn't identify job listings on this page — add the roles manually."
            out.needs_manual = True
            return out

        for job in jobs:
            await self._resolve_one(job, known_hashes, prefs, out)
        return out

    async def _classify(
        self, html: str, url: str
    ) -> tuple[list[FetchedJob], str | None, str | None]:
        match = detect_ats(url, html)
        if match is not None:
            adapter = get_adapter(match.vendor)
            if adapter is not None:
                try:
                    jobs = await adapter.fetch(match.board_id, fetcher=self._fetcher)
                    return jobs, "ats", match.vendor
                except AtsError as exc:
                    log.info("ingest.ats_failed", vendor=match.vendor, error=str(exc))

        jsonld = extract_job_postings(html, base_url=url)
        if jsonld:
            return jsonld, "json_ld", None
        return [], None, None  # route C is part 2b

    async def _resolve_one(
        self,
        job: FetchedJob,
        known_hashes: dict[str, str],
        prefs: JobPreference | None,
        out: ResolvedIngest,
    ) -> None:
        canonical = canonical_text(job.structured)
        digest = content_hash(canonical)
        identity = job.external_id or job.url

        if known_hashes.get(identity) == digest:
            out.unchanged += 1
            out.survivors.add(identity)
            return

        if rejection_reason(job.structured, prefs) is not None:
            out.filtered += 1
            return

        outcome: MatchOutcome | None = None
        usage: StructuredResult | None = None
        if prefs is not None:
            try:
                outcome, usage = await score_match(prefs, job.structured, llm=self._llm)
            except ValidationError as exc:
                # The model returned a shape we can't use even after coercion.
                # Skip this job rather than failing (and retrying) the whole fetch.
                log.info("ingest.score_unusable", url=job.url, error=str(exc))
                out.scoring_failed += 1
                return
            if outcome.score < self._threshold:
                out.below_threshold += 1
                return

        out.keep.append(ScoredJob(job, canonical, digest, outcome, usage))
        out.survivors.add(identity)


def _payload(scored: ScoredJob) -> dict[str, object]:
    data = scored.job.structured.model_dump()
    data["source_type"] = scored.job.source_type.value
    if scored.job.ats_vendor:
        data["ats_vendor"] = scored.job.ats_vendor
    if scored.outcome is not None:
        data["match"] = scored.outcome.model_dump()
    return data


def _posting_key(job: FetchedJob) -> str:
    s = job.structured
    if job.ats_vendor and job.external_id:
        return f"{job.ats_vendor}:{job.external_id}"
    return fallback_dedup_key(company=s.company_name, title=s.title, location=s.location)


@dataclass(slots=True)
class PersistResult:
    saved: int = 0
    pruned: int = 0


async def persist(
    repo: JobIngestRepository,
    *,
    source_id: uuid.UUID,
    resolved: ResolvedIngest,
    llm: LlmClient,
) -> PersistResult:
    result = PersistResult()

    for scored in resolved.keep:
        job = scored.job
        score = scored.outcome.score if scored.outcome is not None else None
        payload = _payload(scored)
        existing = await repo.find_job(
            source_id=source_id, external_id=job.external_id, url=job.url
        )
        row = existing or Job(
            user_id=repo.user_id,
            job_source_id=source_id,
            url=job.url,
            source_type=job.source_type,
            first_seen_at=datetime.now(UTC),
        )
        row.url = job.url
        row.external_id = job.external_id
        row.source_type = job.source_type
        row.ats_vendor = job.ats_vendor
        row.raw_text = scored.canonical
        row.raw_text_hash = scored.digest
        row.structured = payload
        row.needs_review = bool(job.structured.needs_review)
        row.match_score = Decimal(score) if score is not None else None
        row.last_seen_at = datetime.now(UTC)
        if existing is None:
            repo.add(row)

        row.job_posting = await _upsert_posting(repo, job, payload, score)
        if scored.usage is not None:
            repo.add(
                llm.usage_row(
                    scored.usage,
                    purpose="job_match",
                    user_id=repo.user_id,
                    related_kind="job_source",
                    related_id=source_id,
                )
            )
        result.saved += 1

    # Prune jobs the source no longer lists, and jobs that stopped matching
    # (plan step 9: not kept in the DB — re-fetched next run if prefs change).
    pruned = 0
    for row in await repo.jobs_for_source(source_id):
        if (row.external_id or row.url) not in resolved.survivors:
            await repo.delete_job(row)
            pruned += 1
    await repo.session.flush()
    result.pruned = pruned + await repo.prune_orphan_postings()
    return result


async def _upsert_posting(
    repo: JobIngestRepository, job: FetchedJob, payload: dict[str, object], score: int | None
) -> JobPosting:
    key = _posting_key(job)
    posting = await repo.get_posting(key)
    s = job.structured
    if posting is None:
        posting = JobPosting(
            user_id=repo.user_id,
            dedup_key=key,
            company_name=s.company_name,
            company_name_normalized=normalize_company(s.company_name),
            canonical_title=s.title,
            location_normalized=normalize_text(s.location) if s.location else None,
        )
        repo.add(posting)
    if posting.match_score is None or score is None or score >= posting.match_score:
        posting.company_name = s.company_name
        posting.company_name_normalized = normalize_company(s.company_name)
        posting.canonical_title = s.title
        posting.location_normalized = normalize_text(s.location) if s.location else None
        posting.structured = payload
        if score is not None:
            posting.match_score = Decimal(score)
    return posting
