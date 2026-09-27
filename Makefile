.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test test-all up down logs migrate collect-once fixtures probe sync-funds replay quality backfill docs docs-serve web-install web-dev web-test web-build check loadtest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies and git hooks
	uv sync
	uv run pre-commit install

lint: ## Ruff lint + format check
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-format and fix lint
	uv run ruff format .
	uv run ruff check --fix .

typecheck: ## mypy (strict)
	uv run mypy

test: ## Unit tests (no database needed)
	uv run pytest -m "not integration"

test-all: ## All tests; needs ClickHouse (make up) on localhost
	CLICKHOUSE_HOST=localhost CLICKHOUSE_PASSWORD=$${CLICKHOUSE_PASSWORD:-tsetmc} uv run pytest

up: ## Build and start the whole stack
	docker compose up -d --build

down: ## Stop the stack (data volume is kept)
	docker compose down

logs: ## Follow collector and api logs
	docker compose logs -f collector api

migrate: ## Apply schema migrations
	docker compose run --rm migrate

collect-once: ## Run a single collection cycle now
	docker compose run --rm collector collect-once

fixtures: ## Record real API responses and rebuild the small test sample (VPN off!)
	python3 scripts/capture_fixtures.py
	python3 scripts/trim_fixtures.py

probe: ## Measure market-watch delta requests; run during market hours (VPN off!)
	python3 scripts/probe_delta.py

sync-funds: ## Rebuild today's fund universe now
	docker compose run --rm collector sync-funds

replay: ## Rebuild clean ticks of DATE=YYYY-MM-DD from raw snapshots
	docker compose run --rm collector replay --date $(DATE)

backfill: ## Load 400 days of official daily history (VPN off!)
	docker compose run --rm collector backfill --days 400

quality: ## Data-quality report for DATE=YYYY-MM-DD
	docker compose run --rm collector quality --date $(DATE)

docs: ## Build the documentation site (strict)
	uv run mkdocs build --strict

docs-serve: ## Live-reload documentation on :8001
	uv run mkdocs serve -a 127.0.0.1:8001

web-install: ## Install the panel's npm dependencies
	cd web && npm ci

web-dev: ## Panel dev server on :5173 (proxies /api to API_URL, default localhost:8000)
	cd web && npm run dev

web-test: ## Panel typecheck + unit tests
	cd web && npm run typecheck && npm test

web-build: ## Production bundle into web/dist
	cd web && npm run build

check: lint typecheck ## Everything CI checks except the Docker smoke test; needs ClickHouse (make up)
	CLICKHOUSE_HOST=localhost CLICKHOUSE_PASSWORD=$${CLICKHOUSE_PASSWORD:-tsetmc} uv run pytest --cov
	cd web && npm run typecheck && npm test && npm run build
	uv run mkdocs build --strict

loadtest: ## Load-test the API read path (20 users, 20 s) against localhost:8000
	uv run python scripts/loadtest.py --users 20 --seconds 20 --mode plain
	uv run python scripts/loadtest.py --users 20 --seconds 20 --mode etag