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

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from pydantic import ValidationError

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
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
from app.llm import LlmClient, LlmRequestError, StructuredResult
from app.models import Job, JobPosting, JobPreference
from app.models.enums import RobotsState
from app.repositories.jobs import JobIngestRepository

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class _Pending:
    job: FetchedJob
    canonical: str
    digest: str
    identity: str


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

        # Route A when the URL itself is an ATS board: skip robots + the page
        # fetch entirely (ADR-0013 exempts ATS APIs) and go straight to the API.
        jobs = await self._try_ats_from_url(source_url, out)
        if out.route is None:
            jobs = await self._classify_page(source_url, out)
        if out.error is not None:
            return out
        if out.route is None:
            out.error = "Couldn't identify job listings on this page — add the roles manually."
            out.needs_manual = True
            return out

        out.fetched = len(jobs)

        # Cheap, sequential gates first (diff + rule filter), then score whatever
        # survives — concurrently, so a big board isn't dozens of serial LLM calls.
        pending: list[_Pending] = []
        for job in jobs:
            canonical = canonical_text(job.structured)
            digest = content_hash(canonical)
            identity = job.external_id or job.url
            if known_hashes.get(identity) == digest:
                out.unchanged += 1
                out.survivors.add(identity)
                continue
            if rejection_reason(job.structured, prefs) is not None:
                out.filtered += 1
                continue
            pending.append(_Pending(job, canonical, digest, identity))

        if prefs is None:
            for p in pending:
                out.keep.append(ScoredJob(p.job, p.canonical, p.digest, None, None))
                out.survivors.add(p.identity)
            return out

        await self._score_all(pending, prefs, out)
        return out

    async def _score_all(
        self, pending: list[_Pending], prefs: JobPreference, out: ResolvedIngest
    ) -> None:
        sem = asyncio.Semaphore(settings.job_scoring_concurrency)
        Scored = tuple[_Pending, MatchOutcome, StructuredResult]

        async def run(p: _Pending) -> _Pending | Scored:
            async with sem:
                try:
                    outcome, usage = await score_match(prefs, p.job.structured, llm=self._llm)
                except ValidationError as exc:
                    log.info("ingest.score_unusable", url=p.job.url, error=str(exc))
                    return p  # a bare _Pending means "couldn't score this one"
            return p, outcome, usage

        for result in await asyncio.gather(*(run(p) for p in pending), return_exceptions=True):
            if isinstance(result, LlmRequestError):
                out.error = out.error or f"Job scoring is unavailable: {result}"
                continue
            if isinstance(result, ServiceUnavailableError):
                out.error = out.error or (
                    "Job scoring is temporarily unavailable — will retry on the next fetch."
                )
                continue
            if isinstance(result, BaseException):
                raise result
            if isinstance(result, _Pending):
                out.scoring_failed += 1
                out.survivors.add(result.identity)  # keep an existing row we couldn't re-score
                continue
            p, outcome, usage = result
            if outcome.score < self._threshold:
                out.below_threshold += 1
                continue
            out.keep.append(ScoredJob(p.job, p.canonical, p.digest, outcome, usage))
            out.survivors.add(p.identity)

    async def _try_ats_from_url(self, url: str, out: ResolvedIngest) -> list[FetchedJob]:
        match = detect_ats(url)
        adapter = get_adapter(match.vendor) if match is not None else None
        if match is None or adapter is None:
            return []
        try:
            jobs = await adapter.fetch(match.board_id, fetcher=self._fetcher)
            out.route, out.ats_vendor = "ats", match.vendor
            return jobs
        except AtsError as exc:
            log.info("ingest.ats_failed", vendor=match.vendor, error=str(exc))
            return []  # fall through to a page fetch (embed / JSON-LD)

    async def _classify_page(self, url: str, out: ResolvedIngest) -> list[FetchedJob]:
        decision = None
        with contextlib.suppress(FetchError):
            decision = await self._fetcher.check_robots(url)
        if decision is not None and not decision.allowed:
            out.robots_state = RobotsState.DISALLOWED
            out.error = "robots.txt disallows this URL — add the job pages manually."
            out.needs_manual = True
            return []
        out.robots_state = decision.state if decision else RobotsState.UNKNOWN

        try:
            page = await self._fetcher.fetch(url)
        except FetchError as exc:
            out.error = f"Couldn't fetch the page: {exc}"
            return []
        if page.status_code >= 400:
            out.error = f"The page returned HTTP {page.status_code}."
            return []

        final_url = str(page.url)
        match = detect_ats(final_url, page.text)
        adapter = get_adapter(match.vendor) if match is not None else None
        if match is not None and adapter is not None:
            try:
                jobs = await adapter.fetch(match.board_id, fetcher=self._fetcher)
                out.route, out.ats_vendor = "ats", match.vendor
                return jobs
            except AtsError as exc:
                log.info("ingest.ats_failed", vendor=match.vendor, error=str(exc))

        jsonld = extract_job_postings(page.text, base_url=final_url)
        if jsonld:
            out.route = "json_ld"
            return jsonld
        return []  # route C is part 2b


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
    # Skip pruning on an incomplete run: we can't tell "gone" from "not reached".
    if resolved.error is None:
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
