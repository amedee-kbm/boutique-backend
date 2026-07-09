# The Makefile is the contract. CI runs exactly what you run locally.
#
#   make check    everything that must be true before a commit
#   make test     the suite, with branch coverage
#   make fix      auto-fix what can be auto-fixed, then re-run check
#
# Nothing here is aspirational: every target works today. When a target stops
# working, fix it or delete it — a broken target teaches people to ignore the
# Makefile, and then the Makefile stops being the contract.

# Pin the shell: scripts/check-file-length.sh needs bash associative arrays,
# and GNU Make otherwise defaults to /bin/sh.
SHELL := /usr/bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# `docker compose` is a CLI plugin that the docker binary discovers at runtime.
# Under MSYS make (Git Bash on Windows) that discovery fails — recipes get an
# environment in which docker reports "unknown command: docker compose", while
# the identical command typed into the same shell works. Rather than chase the
# variable responsible, call the plugin binary directly; discovery is skipped.
# Override on any machine where the path differs:  make COMPOSE=... test
COMPOSE := docker compose
ifeq ($(shell uname -o 2>/dev/null),Msys)
COMPOSE := "/c/Program Files/Docker/cli-plugins/docker-compose.exe"

# MSYS make also strips the Windows profile variables. Two consequences:
#   * Python's expanduser() on Windows reads USERPROFILE (never HOME), so any
#     tool resolving "~" — pip-audit — dies with "Could not determine home
#     directory".
#   * uv falls back to a literal "~/AppData/Local" *relative to the cwd*, and
#     silently creates a `~` directory inside the repository.
# Override if your profile is not under C:\Users:  make USERPROFILE=... audit
export USERPROFILE ?= C:\Users\$(shell id -un)
export LOCALAPPDATA ?= $(USERPROFILE)\AppData\Local
export APPDATA ?= $(USERPROFILE)\AppData\Roaming
endif

MANAGE := uv run python src/manage.py

# Tests run against the local Postgres from compose.yaml, never against Neon.
# Exported here rather than in .env so that a stray `pytest` invocation without
# make cannot silently create a test database on the production host.
TEST_DATABASE_URL := postgresql://boutique:boutique@localhost:55432/boutique
TEST_ENV := DATABASE_URL=$(TEST_DATABASE_URL) CELERY_TASK_ALWAYS_EAGER=True

.DEFAULT_GOAL := help

# ─── Quality gate ────────────────────────────────────────────────────────────

.PHONY: check
check: format-check lint mypy migration-check file-length task-names  ## Every gate. Must pass before committing.
	@echo ""
	@echo "✓ all checks passed"

.PHONY: fix
fix:  ## Auto-fix formatting and lint, then verify.
	uv run ruff format .
	uv run ruff check . --fix
	@$(MAKE) --no-print-directory check

.PHONY: format-check
format-check:  ## Verify formatting without rewriting files (CI-safe).
	uv run ruff format --check .

.PHONY: lint
lint:  ## Lint without auto-fixing (CI-safe).
	uv run ruff check .

.PHONY: mypy
mypy:  ## Strict type check. Flags live here, not in pyproject, so they are visible.
	uv run mypy --strict --extra-checks --warn-unreachable --warn-unused-ignores src

.PHONY: migration-check
migration-check:  ## Fail if a model change has no migration. Touches no database.
	$(MANAGE) makemigrations --check --dry-run --no-input

.PHONY: file-length
file-length:  ## No source file past its ceiling.
	@./scripts/check-file-length.sh 500

.PHONY: task-names
task-names:  ## Every Celery task pins an explicit name=.
	@uv run python scripts/check_task_names.py src

# ─── Tests ───────────────────────────────────────────────────────────────────

.PHONY: test
test: services-up  ## Parallel suite with branch coverage.
	$(TEST_ENV) uv run pytest -n auto --cov --cov-report=term --cov-report=html src

.PHONY: test-linear
test-linear: services-up  ## Single process — use when debugging a failure.
	$(TEST_ENV) uv run pytest -vv src

.PHONY: test-failed
test-failed: services-up  ## Re-run only what failed last time.
	$(TEST_ENV) uv run pytest --last-failed -vv src

.PHONY: coverage-floor
coverage-floor:  ## Print the branch coverage the suite actually achieves.
	@$(TEST_ENV) uv run coverage report | tail -1

# ─── Security & supply chain ─────────────────────────────────────────────────

.PHONY: bandit
bandit:  ## Static application security testing.
	uv run bandit -c pyproject.toml -r src -ll -ii

.PHONY: licensecheck
licensecheck:  ## Refuse copyleft / source-available licences in the dependency tree.
	uv run licensecheck -r pyproject.toml

.PHONY: audit
audit:  ## Known vulnerabilities in the locked dependency graph.
	# --cache-dir is explicit because pip-audit otherwise calls expanduser("~"),
	# which raises under MSYS make (no USERPROFILE in the recipe environment).
	# --disable-pip because uv's managed Python has no ensurepip.
	uv export --no-hashes --no-emit-project --all-groups > .audit-reqs.txt
	uv run pip-audit --strict --no-deps --disable-pip --cache-dir .pip-audit-cache -r .audit-reqs.txt

.PHONY: deps-check
deps-check: licensecheck audit  ## Both supply-chain gates.

# ─── Services ────────────────────────────────────────────────────────────────

.PHONY: services-up
services-up:  ## Start Postgres, Redis and Mailpit; wait until Postgres answers.
	@$(COMPOSE) up -d --wait

.PHONY: services-down
services-down:  ## Stop them, keeping volumes.
	@$(COMPOSE) down

.PHONY: services-nuke
services-nuke:  ## DESTRUCTIVE. Stop and delete the local volumes.
	$(COMPOSE) down -v

# ─── Development ─────────────────────────────────────────────────────────────

.PHONY: run
run:  ## Django dev server on :8000.
	$(MANAGE) runserver

.PHONY: run-celery
run-celery:  ## Celery worker. The app is `boutique`, not the settings package name of old.
	cd src && uv run celery -A boutique worker -l info

.PHONY: run-celery-beat
run-celery-beat:  ## Celery scheduler.
	cd src && uv run celery -A boutique beat -l info

.PHONY: shell
shell:  ## Django shell.
	$(MANAGE) shell

.PHONY: migrations
migrations:  ## Create migrations for model changes.
	$(MANAGE) makemigrations

.PHONY: migrate
migrate:  ## Apply migrations.
	$(MANAGE) migrate

.PHONY: superuser
superuser:  ## Create a seller (create_superuser sets is_seller).
	$(MANAGE) createsuperuser

.PHONY: setup
setup:  ## One-time: install deps, copy env template, start services, migrate.
	uv sync --group dev
	@test -f .env || (cp .env.example .env && echo "created .env — fill in DJANGO_SECRET_KEY and DATABASE_URL")
	@$(MAKE) --no-print-directory services-up
	@$(MAKE) --no-print-directory migrate

.PHONY: count-lines
count-lines:  ## Source lines, excluding migrations.
	@find src -name '*.py' -not -path '*/migrations/*' -exec wc -l {} + | tail -1

.PHONY: help
help:  ## This list.
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
