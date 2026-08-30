# Career Copilot

A job-search assistant: import job postings, analyse the gap between your work
history and each posting, and tailor your résumé per application.

Private project. Built for the developer's own job search first; see
`CLAUDE.local.md` for the product spec and `docs/development-plan.md` for the
roadmap.

## Architecture (target)

```
Vite/React SPA  ──/api──►  FastAPI (Lambda + API Gateway)  ──►  PostgreSQL (RDS)
   (S3 + CloudFront)              │
                                 ├─► SQS ─► short jobs        (Lambda)
                                 └─► SQS ─► browser crawl jobs (Fargate)
                                              │
                                    Anthropic API, ATS public APIs, career pages
```

Rationale for the main choices lives in `docs/adr/`.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI API **and** async worker handlers (one Python project) |
| `frontend/` | Vite + React SPA |
| `infra/terraform/` | AWS infrastructure (Terraform) |
| `infra/localstack/` | LocalStack root module for local AWS emulation |
| `scripts/` | dev/ops helpers |
| `docs/` | plan, ADRs, data model, development log |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- Node 22 + pnpm (`corepack enable pnpm`)
- Docker (Postgres + LocalStack)
- Terraform (for `infra/`)

## Getting started

### First time only

```bash
make install                       # backend (uv) + frontend (pnpm) dependencies
cp backend/.env.example backend/.env
```

### Every time — run the app

```bash
# terminal 1 — local infra (Postgres :5433 + LocalStack :4566), runs in background
make up

# terminal 2 — API on http://localhost:8000
make api

# terminal 3 — SPA on http://localhost:3000  (proxies /api to :8000)
make web
```

Then open <http://localhost:3000>. Stop: `Ctrl-C` in terminals 2 and 3, then
`make down`.

Local Postgres uses host port **5433** because this machine runs a native
PostgreSQL on 5432.

## Quality gates

```bash
make lint    # ruff + ruff format + mypy(strict) ; eslint + tsc
make test    # pytest ; vitest
make fmt     # auto-format both sides
```

Optionally: `uvx pre-commit install` to run the same checks on commit.

Detailed test instructions (filters, coverage, DB-backed tests, the no-Docker
fallback): `docs/local-testing.md`.

## Common tasks

| Command | Does |
|---|---|
| `make up` / `make down` | start / stop local infra |
| `make api` / `make web` | run the API / the SPA dev server |
| `make migrate` | apply DB migrations (Phase 01+) |
| `make worker` | run the async worker loop locally (Phase 04+) |
| `make help` | list all targets |
