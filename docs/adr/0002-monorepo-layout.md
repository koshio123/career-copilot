# ADR-0002: Monorepo layout

- Status: Accepted
- Date: 2026-08-30

## Context

The project has a backend API, async workers, a frontend SPA, and IaC. They share
contracts (the OpenAPI schema, queue message shapes) and are developed by one
person who wants atomic cross-cutting changes.

## Decision

Single repository, top-level directories:

```
backend/   FastAPI API + async worker handlers (one Python project, shared code)
frontend/  Vite + React SPA
infra/     Terraform (infra/terraform) + LocalStack root module (infra/localstack)
scripts/   dev/ops helper scripts
docs/      plan, ADRs, data model, dev log
```

Backend API and workers live in one Python package (`backend/app`) so they share
models, config, and the DB layer. Deployment splits them (see ADR-0005); the
codebase does not.

## Consequences

- One PR can change an endpoint, its worker, and the frontend that calls it.
- No cross-repo version skew for the API contract.
- CI uses path filters so each area only runs its own pipeline.
- If a component is ever extracted, the package boundary in `backend/app` is the
  seam to cut along.

## Alternatives considered

- **Polyrepo** — heavier coordination for a solo dev, contract drift.
- **Nx / Turborepo** — real value at multi-team scale; here it is setup cost with
  little payoff. Plain `make` + per-area tooling is enough.
