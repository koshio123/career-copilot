# ADR-0013: Fetch etiquette — robots.txt, rate limits, and ToS

- Status: Accepted
- Date: 2026-09-01

## Context

Phase 06 has the server fetch URLs that a user registers: career top pages, job
lists, job detail pages, ATS public APIs, and (route C) a shallow crawl. This
raises three separate concerns that `CLAUDE.local.md §5` asks us to settle
before implementation:

1. **robots.txt** — do we honour it, and for which requests?
2. **Rate / politeness** — how hard may we hit one host?
3. **Terms of service** — under what framing is this ingestion acceptable?

SSRF defence (blocking private/link-local IPs, metadata endpoints, DNS
rebinding, redirect limits) is a related but distinct concern owned by ADR-0007
/ Phase 09; this ADR is about being a well-behaved client of a site that we are
*allowed* to reach.

## Decision

### Honour robots.txt for every fetched page

Before fetching any HTML page (routes B and C, and the initial classification
fetch), the worker fetches and parses `https://{host}/robots.txt` with
`protego` and checks the path against our User-Agent. `Disallow` ⇒ we do not
fetch it.

- Result is cached per host (in the worker process and, for the scheduler,
  on `job_sources.robots_state` + `robots_checked_at`) with a 24h TTL.
- A registered URL whose own path is disallowed sets the source to
  `robots_state = disallowed`, and the source is surfaced to the user as
  "can't fetch — register the job pages manually" rather than retried.
- `Crawl-delay`, if present, is honoured as the per-host minimum interval.
- robots.txt fetch failure (network error, 5xx) ⇒ treat as `unknown` and apply
  the conservative default delay; a 404 ⇒ `allowed` (no restrictions published).

### ATS public APIs: no robots gate, but same politeness

Routes A endpoints (`boards-api.greenhouse.io`, `api.lever.co`,
`api.ashbyhq.com`) exist to distribute postings and are not covered by a
meaningful robots.txt. We still: use the identifying User-Agent, stay on
documented endpoints only, and fetch each board at most once per source per
schedule run.

### Politeness defaults

- **User-Agent**: `career-copilot/<version> (+https://github.com/koshio123/career-copilot)`
  — identifiable, with a contact/repo URL. Never spoof a browser UA.
- **Per-host rate**: a token-bucket in the worker — default minimum **3s**
  between requests to the same host (overridden upward by `Crawl-delay`).
- **Route C crawl bounds**: same-host and at/below the registered URL's path
  prefix; **max depth 2**, **max 40 pages** per source per run; hard per-request
  timeout and response-size cap (shared with SSRF config).
- **Conditional requests**: send `If-None-Match` / `If-Modified-Since` when we
  have them; a `304` short-circuits to the diff-detection "unchanged" path.
- **Backoff**: `429` / `503` with `Retry-After` is honoured; repeated failures
  raise `consecutive_failures` and back the source's schedule off.

### ToS framing

- We ingest only pages a **user explicitly registers for their own job search**.
  No bulk discovery, no re-distribution, no aggregation product. This matches
  ADR-0006's rejection of broad board scraping.
- Fetched job pages are stored per-user (ADR-0009) and used to produce that
  user's match scores and résumé advice. Raw HTML is kept only transiently for
  extraction; we persist normalised text + hash, not page copies.
- We do not bypass logins, paywalls, or anti-bot challenges. A page that needs
  any of those ⇒ fetch fails ⇒ user is guided to manual entry.
- The single-user / personal-use context reduces but does not erase ToS risk;
  the decision to register a given company's page rests with the user, and the
  UI says so at registration time.

## Consequences

- Every route-B/C fetch pays one (cached) robots.txt round-trip and a politeness
  delay; ingestion is deliberately slow, which is fine for a scheduled job.
- Some sources will be un-fetchable (robots, JS-walls, anti-bot); the product
  degrades to manual entry rather than escalating evasion.
- `job_sources` needs `robots_state` / `robots_checked_at` (already modelled in
  ADR-0009) and per-source failure counters (already present).
- If a site operator objects, the identifying User-Agent + contact URL gives
  them a way to reach us, and per-source disable is a one-flag operation.

## Alternatives considered

- **Ignore robots.txt for "just a few pages"** — rejected; robots is the
  low-cost, universally-understood signal and honouring it is the whole basis
  for the ToS framing above.
- **Spoof a browser User-Agent to reduce blocking** — rejected; deceptive, and
  it removes the site operator's ability to identify or contact us.
- **Playwright/stealth to defeat anti-bot** — rejected as detection evasion;
  out of scope and against the "degrade to manual" principle. (Playwright is
  used only for legitimate JS rendering of pages we're allowed to fetch.)
