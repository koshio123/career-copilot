# Development log

Chronological record of what was built and why. One section per work session /
phase. The roadmap is `development-plan.md`; decisions are in `adr/`.

---

## 2026-08-31 — Phase 01: Domain model & DB schema

Branch: `phase-01-schema`.

### Goal

A schema that deduplicates jobs from multiple sources and protects sensitive
data, with a reversible baseline migration.

### What was built

**SQLAlchemy foundation** (`app/db/`)

- `base.py` — `Base(DeclarativeBase)` with a fixed constraint **naming
  convention** (stable Alembic autogenerate), `UUIDPrimaryKey` /`Timestamps`
  mixins, `TZDateTime` / `JsonDict` reusable column annotations.
- `session.py` — async engine (`pool_pre_ping`), `async_sessionmaker`
  (`expire_on_commit=False`), `get_session` request dependency.

**11 models** (`app/models/`, one file per aggregate)

- `user` (User, JobPreference), `resume` (Resume, ResumeVersion), `job`
  (JobSource, Job, JobPosting), `application` (Application, ApplicationEvent),
  `analysis` (AnalysisResult), `llm` (LlmUsage).
- Every domain table has `user_id` (cascade from `users`) + a uni-directional
  `user` relationship. `jobs` vs `job_postings` split per ADR-0009.
- `enums.py` — `StrEnum`s stored as plain `VARCHAR` (`native_enum=False`,
  **no DB CHECK** — it doesn't round-trip through `alembic check`; validation is
  Python + Pydantic).

**Alembic** — `alembic init -t async`, rewrote `env.py` to be driven by
`app.core.config` + `Base.metadata` (`compare_type`, `compare_server_default`).
Baseline `6e90a7ec4ec1_initial_schema`. `upgrade → downgrade base → upgrade`
round-trips; `alembic check` clean.

**Tests** — `conftest.py` gained a session-scoped `engine` (test DB name forced
to `*_test`, `create_all`/`drop_all`) and a per-test `db` session in a rolled-back
transaction (`join_transaction_mode="create_savepoint"`). `pyproject` sets
`asyncio_default_{fixture,test}_loop_scope = "session"` so engine and tests share
one loop. `test_models.py`: metadata table set, full domain round-trip, cascade
delete.

**Tooling** — `make migration` / `check-migrations` / `seed`; CI backend job runs
`alembic upgrade/downgrade/upgrade/check`; ruff `per-file-ignores` for
`alembic/versions`, mypy checks `alembic/env.py` + `scripts/` (excludes
versions). `scripts/seed.py` — idempotent dev dataset.

**Decisions** — ADR-0009 (data model shape, `jobs`/`job_postings` dedup,
per-user scoping, JSONB, **pgvector deferred**, no native enums / no CHECK).

### Verification

| Gate | Result |
|---|---|
| `make lint` | ruff + mypy strict (27 files) ✓; eslint + tsc ✓ |
| `make test` | pytest 4 ✓; vitest 1 ✓ |
| `make check-migrations` | `alembic check` → no drift |
| round-trip | `upgrade → downgrade base → upgrade` ✓ on dev and `_test` DBs |
| `make seed` | dev user created; re-run is a no-op |

### Deviations from `development-plan.md`

- Pulled a slice of Phase 02's "test infra with transaction isolation" forward —
  Phase 01 needs DB-backed tests to verify the models/migration.
- Plan said "VARCHAR + CHECK" for enums; ended up plain VARCHAR (CHECK doesn't
  survive `alembic check`). ADR-0009 updated.

### Follow-ups

- Pydantic schemas for the `structured` JSONB shapes land with the endpoints
  that read/write them (Phase 05+).
- `readyz` (DB-backed readiness) is Phase 02.

### 2026-08-31 (later) — auth design revisited before Phase 02

Reviewed the auth/authz option space (build vs. Cognito/Clerk/etc., credential
type, session mechanism, store, authz model, CSRF). Outcome — **ADR-0010
supersedes ADR-0004**:

- First factor → **email 6-digit OTP, no passwords** (was email + password +
  argon2). Passwords are the biggest security-critical surface; passwordless is
  the mainstream default for this product's reference class. Passkeys + OAuth are
  later, additive. `users.password_hash` will be dropped in the Phase 02
  migration; `argon2-cffi` removed.
- Session mechanism (opaque token, httpOnly/Secure/SameSite=Lax cookie,
  server-side record) and same-origin CSRF reasoning **carry forward unchanged**.
- Session/OTP store → **kept DynamoDB** (user's call): cost is effectively $0 at
  this scale (always-free tier / pennies on-demand, free TTL deletes), and it
  keeps auth-transient state off the primary DB. Behind `SessionStore` /
  `OtpStore` interfaces.
- Local dev gains LocalStack DynamoDB + MailHog.

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

### 2026-08-30 (later still) — clear the initial Dependabot backlog

Once CI was green, every recreated Dependabot PR passed. Merged:

- **GH Actions group** (PR #10): checkout v4→v7, setup-node v4→v7, setup-uv
  v5→v7, pnpm/action-setup v4→v6, setup-terraform v3→v4.
- **Frontend dev-deps**, squashed into one commit here instead of 4 merges:
  typescript 5.7→6.0, @vitejs/plugin-react 4→5, eslint-plugin-react-hooks 5→7,
  eslint-plugin-react-refresh 0.4→0.5. Gates green on all four (Phase 00 code is
  minimal enough that the majors are no-ops).
- Next: **Phase 01** — domain model & DB schema, `pgvector` decision, Alembic
  baseline.
