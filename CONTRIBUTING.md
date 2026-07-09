# Contributing

## The contract

```bash
make fix      # auto-fix formatting and lint
make check    # every gate. must pass.
make test     # the suite, with branch coverage
```

CI runs exactly these. If they pass locally and fail in CI, that is a bug in the Makefile, not
a reason to push again and hope.

## Setup

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, and GNU Make.

```bash
make setup    # deps, .env from the template, services, migrate
make run      # http://localhost:8000/api/v1/docs/
```

`make setup` starts Postgres, Redis and Mailpit from `compose.yaml`. Postgres is published on
**55432**, not 5432 — see [engineering-notes.md](docs/engineering-notes.md) if you want to know
why, and you probably will eventually.

Tests never touch Neon. `make test` overrides `DATABASE_URL` to the local container, and it does
so in the `Makefile` rather than `.env` precisely so that a stray `pytest` cannot.

## Branches and commits

Never commit to `main`. Branch as `feature/short-description` or `fix/short-description`.

[Conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`. One logical change per commit.

Where an AI assistant wrote the code, say so — add the
`Co-Authored-By: Claude <noreply@anthropic.com>` trailer. [AI_USAGE.md](AI_USAGE.md) states that
this project uses AI openly; the commit history should not quietly say otherwise.

The commit message explains **why**. The diff already shows what.

## Adding a gate

Two rules govern this, and they are not negotiable because the project learned both the hard way
(see [PM-0001](docs/postmortems/0001-guardrails-that-checked-nothing.md)).

**A gate is not trusted until it has been observed failing.** Write it, break something on
purpose, watch it go red, revert, watch it go green. Prove each *branch* — a default and its
override are two gates. ([ADR-0009](docs/adr/0009-a-gate-must-be-seen-to-fail.md))

**Never let a gate skip.** If a check cannot evaluate something, that is a failure, not a pass.
Skipping is how a gate ends up green while inspecting nothing.

## Style

Enforced, so you will find out anyway:

- `ruff format` and `ruff check`, line length 120.
- `mypy --strict`. Type hints on every signature, including tests and fixtures.
- Google-style docstrings. Write one when the contract is not obvious from the name; do not
  write one that restates the name.
- No file over 500 lines (`settings.py` is capped at 250). A per-file override carries a reason.

Conventions the linter cannot check:

- **Dependency direction is controllers → services → models.** Models never import services.
- **Business logic lives in `services.py`**, not in a controller. A controller validates, calls
  a service, and returns.
- **Every `@shared_task` pins `name=`.** The name is the contract, not the module path. See
  [engineering-notes.md](docs/engineering-notes.md).
- **Do not catch an exception you cannot handle**, especially in a Celery task. Let it propagate
  and let the retry policy do its job.

## Tests

Every feature ships with tests. Every bug fix ships with a test that reproduces the bug *first*.

Coverage is a ratchet ([ADR-0006](docs/adr/0006-coverage-is-a-ratchet.md)): `fail_under` is what
the suite genuinely achieves, and it only moves up. Lowering it to make a red build green is not
a fix.

Be honest about what a test proves. `pytest-django` rolls back the wrapping transaction, so
`transaction.on_commit` callbacks never fire — a test asserting that a task was dispatched will
pass whether or not the dispatch exists. Use `django_capture_on_commit_callbacks(execute=True)`.

## Non-trivial changes

Discuss before implementing. Present what you found, propose approaches with their trade-offs,
name your assumptions, and get agreement. This is the cheapest place to catch a wrong approach,
and the discussion is not a formality.

## Dependencies

`uv` only, never `pip`. `uv add <package>`, `uv add --dev <package>`, `uv sync --group dev`.

New dependencies are a last resort. Check `pyproject.toml` first; check the standard library and
Django before that. `make deps-check` runs the licence and vulnerability gates — copyleft and
source-available licences are rejected outright.
