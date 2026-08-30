# Development log

Chronological record of what was built and why. One section per work session /
phase. The roadmap is `development-plan.md`; decisions are in `adr/`.

---

## 2026-08-30 — Phase 00: Foundation and workflow

Branch: `phase-00-foundation`.

### Goal

Anyone can `clone → install → up → test`; CI enforces the quality gates from the
first commit.

### What was built

**Repo skeleton & dev environment**

- Monorepo layout: `backend/` `frontend/` `infra/{terraform,localstack}/`
  `scripts/` `docs/` (ADR-0002).
- `.editorconfig`, `.gitignore` (Python / Node / Terraform / secrets).
- `docker-compose.yml`: Postgres 17 on host port **5433** (native PG holds 5432
  on this machine) + LocalStack (SQS/S3 only). `scripts/postgres-init.sql`
  creates the `_test` database.
- `Makefile`: `up/down install api web migrate worker lint fmt test` (+ `make help`).
- `backend/.env.example` — all vars under the `APP_` prefix.

**Backend (`backend/`)**

- `uv` project, `package = false` (it's an app, not a library). Optional-dep
  groups `worker` (boto3, trafilatura, selectolax, protego) and `browser`
  (playwright) keep those out of the API image.
- Ruff (`E,F,I,UP,B,SIM,C4,PTH,ASYNC,RUF`), mypy `strict` + pydantic plugin,
  pytest with `asyncio_mode=auto`.
- `app/core/config.py` — pydantic-settings, `get_settings()` cached.
- `app/core/logging.py` — structlog; console locally, JSON when `APP_LOG_JSON`.
- `app/main.py` — `create_app()` composition root.
- `app/api/health.py` — `/healthz` liveness only (readiness w/ DB is Phase 02).
- `app/workers/runner.py` — stub for `make worker` (Phase 04).
- Test: `GET /healthz` via `httpx.ASGITransport` (no socket).

**Frontend (`frontend/`)**

- Vite + React 19 + TS SPA (ADR-0008). Not Next.js: no SSR/SEO need.
- ESLint flat config, Prettier, `tsc -b` project references, Vitest + Testing
  Library. Dev server proxies `/api` → `:8000` (same-origin model).
- `pnpm-workspace.yaml` allowlists the `esbuild` build script (pnpm 11 blocks
  build scripts by default).
- Test: `App` renders its title.

**CI / automation**

- `.github/workflows/{backend,frontend,infra}.yml`, path-filtered. Backend runs a
  Postgres service; infra validates each Terraform root module (skips cleanly
  while none exist).
- `.github/dependabot.yml` — weekly, grouped, for uv / npm / actions / terraform.
- `.pre-commit-config.yaml` — generic hooks + detect-secrets (with
  `.secrets.baseline`) + local hooks calling the project's own uv/pnpm/terraform.

**Decisions recorded**: ADR-0001..0008 (ADR process, monorepo, API on Lambda
first, cookie-session auth, worker split, ingestion hybrid, data-protection
baseline, React SPA).

### Verification

| Gate | Result |
|---|---|
| `make lint` | ruff ✓, ruff format ✓, mypy strict ✓ (12 files); eslint ✓, tsc ✓ |
| `make test` | pytest 1 ✓; vitest 1 ✓ |
| `make up` | Postgres + LocalStack healthy; `career_copilot` + `career_copilot_test` present |
| API boot | `uvicorn app.main:app` → `GET /healthz` `200 {"status":"ok"}` |

### Deviations from `development-plan.md`

None. The plan's "real Lambda locally via LocalStack+tflocal" is deferred to
Phase 04 as written; Phase 00 only stands up SQS/S3 emulation.

### Follow-ups / notes

- `astral-sh/setup-uv@v5`, `pnpm/action-setup@v4`, `hashicorp/setup-terraform@v3`
  pinned by major; run `pre-commit autoupdate` and let Dependabot bump actions.
- `pre-commit` binary not installed locally — config is ready; enable with
  `uvx pre-commit install`.
- UI component approach (design system vs. headless kit) is still open — decided
  in Phase 03 when real screens exist. Architecture (SPA, data, forms) is fixed
  in ADR-0008.

### 2026-08-30 (later) — post-merge cleanup

- Flattened the Phase 00 history to one commit (no `Co-Authored-By` trailer),
  `main` set as the default branch on GitHub, `phase-00-foundation` deleted.
- Node pinned to **24** (Active LTS "Krypton") instead of 22 (now Maintenance
  LTS): `frontend/.nvmrc`, CI `node-version`, `@types/node@^24`,
  `engines.node >=24`. Gates re-verified on Node 24. Dependabot keeps
  `@types/node` off "Current" (26); it's bumped manually with the runtime.
- All 9 initial Dependabot PRs were branched off the pre-rewrite commit and must
  be recreated; see the PR review notes.
- Python pinned to **3.13** (`.python-version`, `requires-python`, ruff
  `target-version`, mypy `python_version`). The bump surfaced UP043 in
  `conftest.py` (`AsyncGenerator[AsyncClient, None]` → `AsyncGenerator[AsyncClient]`
  — the return type now has a default). Gates green on 3.13.6.

### 2026-08-30 (later still) — CI fixes from the first real runs

First push to `main` surfaced two CI bugs, plus a dependency-audit approach that
was too fragile:

- **`pnpm/action-setup` "No pnpm version specified"** — `defaults.run.working-directory`
  does not apply to action inputs, and there is no root `package.json`. Fix:
  `package_json_file: frontend/package.json`.
- **`pip-audit` tried to build `lxml` from source** (re-resolved the exported
  requirements in a throwaway venv without system headers). Replaced the whole
  approach: new `security.yml` runs **OSV-Scanner** directly against
  `backend/uv.lock` + `frontend/pnpm-lock.yaml` (both ecosystems, one tool, no
  venv/resolution) on lockfile changes + weekly. Dropped the per-workflow
  `pip-audit` / `pnpm audit` steps.
- Removed the `terraform` Dependabot ecosystem until `infra/terraform` has real
  `.tf` files (it errored with no manifest). Back in Phase 10.
- Next: **Phase 01** — domain model & DB schema, `pgvector` decision, Alembic
  baseline.
