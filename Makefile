.DEFAULT_GOAL := help
SHELL := bash

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- local environment ---

up: ## Start local infra (Postgres + LocalStack)
	docker compose up -d

down: ## Stop local infra
	docker compose down

install: ## Install backend + frontend dependencies
	cd backend && uv sync --all-extras
	cd frontend && pnpm install

# --- run the app (each in its own terminal) ---

api: ## Run the API with autoreload on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web: ## Run the SPA dev server on :3000 (proxies /api to :8000)
	cd frontend && pnpm dev

migrate: ## Apply DB migrations
	cd backend && uv run alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add x"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

check-migrations: ## Fail if models and migrations have drifted
	cd backend && uv run alembic upgrade head && uv run alembic check

seed: ## Load a minimal dev dataset
	cd backend && uv run python -m scripts.seed

worker: ## Run the async worker loop locally (Phase 04+)
	cd backend && uv run python -m app.workers.runner

# --- quality gates ---

lint: ## Lint + type-check backend and frontend
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy .
	cd frontend && pnpm run lint && pnpm run typecheck

fmt: ## Auto-format backend and frontend
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm run format

test: ## Run backend + frontend test suites
	cd backend && uv run pytest
	cd frontend && pnpm run test

.PHONY: help up down install api web migrate migration check-migrations seed worker lint fmt test
