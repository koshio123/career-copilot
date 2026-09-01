# ADR-0012: ATS vendor support and priority

- Status: Proposed
- Date: 2026-09-01

## Context

ADR-0006 commits to route **A** — call an ATS's public, authless job-board API
and normalise it through a per-vendor adapter — as the preferred ingestion path.
`CLAUDE.local.md §5` leaves open which vendors to build first and whether the
domestic Japanese ATSes (HERP / HRMOS / Talentio) expose usable public APIs.
This ADR settles both before Phase 06 implementation.

### What the market looks like (survey, 2026-09)

Vendors with a **documented, authless** job-board API, one board per company:

| Vendor | List endpoint | Detail / notes |
|---|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | full content inline; `?content=true` returns HTML descriptions; no pagination |
| Lever | `GET api.lever.co/v0/postings/{site}?mode=json` | flat list; `skip`/`limit` params; no auth |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true` | structured compensation opt-in; no pagination |
| Workable | `GET www.workable.com/api/accounts/{subdomain}?details=true` | list + companion location/department endpoints |
| SmartRecruiters | `GET api.smartrecruiters.com/v1/companies/{id}/postings` | offset pagination (`offset`/`limit`, 100 max) |
| Recruitee | `GET {company}.recruitee.com/api/offers/` | lighter metadata |
| Personio | `GET {company}.jobs.personio.de/xml` | XML feed, not JSON |

**Domestic ATS (HERP / HRMOS / Talentio):** none publishes a documented public
job-board API. Their career sites (`*.herp.careers`, `hrmos.co/pages/{c}/jobs`,
`open.talentio.com/...`) are rendered from **undocumented** internal JSON
endpoints. HRMOS and Talentio also offer official APIs, but those are
tenant-token-gated (for the employer's own integrations), not a public feed.
However, all three commonly emit `schema.org/JobPosting` JSON-LD on their public
job pages for Google for Jobs.

## Decision

### Ship adapters for Greenhouse, Lever, Ashby

Phase 06 builds route-A adapters for **Greenhouse, Lever, and Ashby** only.
They are documented, stable, authless, one-board-per-company, need no
pagination handling, and cover a large share of Japanese companies that hire
for global or engineering roles (the product's target user).

### Defer the other public-API vendors to Phase 11

SmartRecruiters, Workable, Recruitee, and Personio are known-good but add
pagination quirks (SmartRecruiters), XML (Personio), or lower JP prevalence.
They are a mechanical follow-on once the adapter interface has proven itself.

### No dedicated adapter for domestic ATS — rely on routes B and C

HERP / HRMOS / Talentio pages go through route **B** (JSON-LD) and, failing
that, route **C** (crawl + LLM). We do **not** call their undocumented internal
JSON endpoints: that is scraping a private API by another name (ADR-0013,
ADR-0006's "no broad scraping" line) and breaks silently on their changes.
Revisit if any of them publishes an official public feed.

### Adapter contract

Each adapter is `fetch(board_id) -> list[NormalizedJob]`, pure over an injected
HTTP client. Vendor detection (URL pattern + in-page scripts/links) yields
`(vendor, board_id)`; an unknown or failing vendor falls back to route C. The
normalisation layer maps each vendor's shape, date formats, and location model
onto the shared structured schema from ADR-0009, setting `source_type="ats"`
and `ats_vendor`.

## Consequences

- Three adapters is a small, testable surface; each is ~a screen of code plus a
  recorded fixture.
- Companies on deferred or domestic ATSes still work, just via B/C with the
  usual `needs_review` flagging and (for C) LLM cost.
- Adding a vendor later is additive: new detector entry + new adapter + fixtures,
  no schema change.
- We take on the maintenance of tracking three external API shapes; recorded
  fixtures + a contract test per vendor contain the risk.

## Alternatives considered

- **Build all seven public-API vendors now** — more upfront adapter code and
  fixture maintenance than MVP needs; deferring is cheap and reversible.
- **Reverse-engineer HERP / HRMOS / Talentio internal JSON** — rejected: no
  contract, ToS-questionable, fragile. JSON-LD gives most of the same data with
  a public spec.
- **Use a paid aggregator (Adzuna, TheirStack, jobdataapi, …)** — cost, unclear
  JP coverage, and it moves us away from "the user registers a specific
  company's page". Still parked per ADR-0006.
