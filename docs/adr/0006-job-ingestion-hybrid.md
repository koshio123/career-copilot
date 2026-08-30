# ADR-0006: Job ingestion — ATS API → JSON-LD → LLM hybrid

- Status: Accepted
- Date: 2026-08-30

## Context

Large job-board scraping carries legal/ToS risk and breaks on layout changes.
Most company career pages are served by a known ATS with an authless public JSON
API, or embed `schema.org/JobPosting` JSON-LD for Google for Jobs. Both give
structured data with zero LLM tokens and no hallucination. This is the core of
`CLAUDE.local.md §4`.

## Decision

For each user-registered career URL, resolve a source route in priority order:

- **A — ATS API**: detect vendor + board id (URL patterns + in-page
  scripts/iframes), call the vendor's public jobs API, normalise via a
  per-vendor adapter into a shared schema.
- **B — JSON-LD**: parse `<script type="application/ld+json">` for `JobPosting`
  (`@graph`, multiple postings, HTML entities). Missing required fields →
  `needs_review`.
- **C — Fallback**: crawl (httpx / Playwright), extract main text with
  trafilatura, structure with an LLM under a JSON Schema.

All routes converge on one schema carrying `source_type` (`ats` / `json_ld` /
`llm`) and, for A, `ats_vendor`. A content hash gates any LLM call. Rule-based
pre-filtering runs before the LLM; a score threshold gates persistence.

## Consequences

- LLM cost and hallucination shrink as more sources land on routes A/B.
- Per-vendor adapters are ongoing maintenance; unknown vendors fall back to C.
- robots.txt and each source's ToS are checked before fetching, including for
  public APIs.
- Detection heuristics need tuning; misdetection degrades gracefully to route C.

## Alternatives considered

- **Aggregator APIs (Adzuna etc.)** — unclear JP coverage; revisit post-MVP.
- **Broad scraping of major boards** — rejected on legal/ToS/fragility grounds.
- **Official APIs (Hello Work, Indeed)** — gated or discontinued.
