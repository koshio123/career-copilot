# ADR-0005: Async workers split across Lambda and Fargate

- Status: Accepted
- Date: 2026-08-30

## Context

Async work has two very different shapes:

1. **Short, bursty, CPU-light**: LLM structuring, gap analysis, ATS/JSON-LD
   fetches, matching. Seconds to a couple of minutes. Spiky volume.
2. **Long, browser-bound**: crawling JS-rendered career sites with Playwright.
   Can exceed Lambda's 15-minute ceiling; needs a ~400 MB browser runtime that is
   painful to package in a Lambda zip.

SQS is the queue for both (`CLAUDE.local.md`).

## Decision

- **Class 1 → Lambda**, triggered by SQS event source mapping, with partial batch
  responses (`batchItemFailures`), a DLQ, and idempotent handlers.
- **Class 2 → a long-running Fargate service** that polls its own SQS queue and
  runs Playwright from a container image.
- Both call the **same handler functions** in `backend/app`; only the wrapper
  (Lambda entrypoint vs. poll loop) differs.

## Consequences

- No Playwright-in-Lambda packaging problem.
- Class 1 keeps zero idle cost and scales to burst automatically.
- Two deployment targets to run and monitor instead of one.
- Handler code stays runtime-agnostic; a job can be moved between classes by
  changing which queue feeds it.

## Alternatives considered

- **All Lambda** — the 15-minute limit and browser packaging make crawl jobs
  fragile.
- **All Fargate (Celery/Dramatiq)** — always-on cost and more infra for the 90%
  of jobs that are short and spiky.
