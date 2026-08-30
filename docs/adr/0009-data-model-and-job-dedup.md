# ADR-0009: Data model shape and job deduplication

- Status: Accepted
- Date: 2026-08-31

## Context

`CLAUDE.local.md §5` flags "DB schema that can deduplicate jobs from multiple
sources (`ats` / `json_ld` / `llm`)" as an open question to resolve in Phase 01.
The pipeline (ADR-0006) fetches the same logical job from different routes and
re-fetches it over time; the app must collapse those into one thing the user
sees, while keeping each raw fetch for diffing and provenance.

## Decision

### Two levels: `jobs` (fetch unit) and `job_postings` (logical posting)

- **`jobs`** — one row per `(job_source, external job identity)`. Holds the
  fetched + normalised data for *that* source/route: `source_type`,
  `ats_vendor`, `raw_text`, `raw_text_hash` (the diff gate), `structured`
  (JSONB), `match_score`, `needs_review`, `first_seen_at` / `last_seen_at`.
- **`job_postings`** — one row per logical job. Multiple `jobs` link to it via
  `job_posting_id`. Holds the merged "best" view the user interacts with
  (bookmark, triage status) and the canonical company/title/location.

### Deduplication key

`job_postings.dedup_key`, unique per user:

- If any contributing `job` has an ATS identity → `"{ats_vendor}:{external_id}"`.
- Otherwise → a hash of `normalize(company) | normalize(title) | normalize(location)`
  where `normalize` lowercases, strips legal suffixes (Inc./株式会社/…),
  collapses whitespace, and folds width/case.

Clustering is deterministic and done in the app when a `job` is saved: compute
the key, upsert the `job_posting`, attach. No fuzzy/vector matching (see below).

### Per-user scoping

Every domain table carries `user_id` (denormalised where it could be derived),
and `job_postings` are per-user. For a single-user product this is simpler and
removes any cross-user data-leak surface. Global dedup across users is explicitly
not a goal.

### JSONB for the structured schema, a few promoted columns

The common structured schema (title, required/preferred skills, salary, location,
remote, employment type, description) lives in a `structured` JSONB column on
`jobs` and `job_postings` — it will churn as adapters and prompts evolve.
Columns are promoted out of JSONB only when needed for indexing, filtering, or
FK use (`company_name_normalized`, `dedup_key`, `match_score`, `needs_review`,
salary bounds for range filters).

### Résumés: `resumes` + `resume_versions`

`resumes` is the container (usually one primary per user). `resume_versions` are
immutable snapshots: the evolving base, plus per-job tailored variants
(`tailored_for_job_posting_id`). Structured content is JSONB; `raw_text` and the
uploaded file's S3 key are kept for re-processing.

## Consequences

- Diffing, provenance, and "which source said what" are preserved on `jobs`;
  the user-facing surface stays clean on `job_postings`.
- Re-fetches update a `job` in place (hash unchanged → skip downstream); new
  logical jobs create a `job_posting`.
- JSONB means no migration for every schema tweak, at the cost of no DB-level
  validation of `structured` — Pydantic models guard it at the app boundary.
- The dedup key is deterministic and debuggable; its weakness is genuine
  company-name variance not covered by `normalize`. Acceptable for MVP; a
  normalisation table or vector similarity can be added later without schema
  change to `jobs`.

## Alternatives considered

- **Single `jobs` table** — loses the fetch-vs-logical distinction; can't hold
  multiple sources' views of one job without denormalising badly.
- **`pgvector` similarity for dedup and match scoring** — deferred. It needs the
  extension, an embeddings provider decision, and an embedding pipeline, for
  little gain at single-user / few-sources scale where deterministic keys and
  rule + LLM scoring (ADR-0006) are enough. Revisit in Phase 11 when tuning match
  precision; `jobs`/`job_postings` need no schema change to add a vector column.
- **Native PG enums** — rejected for status-like fields (`ALTER TYPE` pain).
- **`VARCHAR` + `CHECK` constraint** — tried, then dropped: Alembic autogenerate
  does not round-trip the implicit `CHECK` from a `native_enum=False` `Enum`, so
  `alembic check` perpetually re-proposes dropping it. Enums are now plain
  `VARCHAR`, validated in Python (`Enum(validate_strings=True)`) and by Pydantic
  at the API edge. A hand-written `CHECK` can be added later per column if a
  data-integrity need appears.
