# ADR-0011: `src/` layout, settings package named `boutique`

## Status

Accepted.

## Context

`django-admin startproject` puts `manage.py` at the repository root and names the settings
package after the project. That is what this backend had: `manage.py`, `apps/`, `api/` and
`config/` at the top level, mixed in with the `Makefile`, Docker files, `.github/` and
`.claude/`.

Two problems, of different weights.

The small one is clutter: repository furniture and application source in one listing.

The sharp one is the name. **`config` is a real distribution on PyPI.** A top-level package
called `config` sits on `sys.path` and shadows it. Any dependency that does `import config`
gets the Django settings module instead, and the resulting traceback makes no sense.

Both were cheapest to fix at that moment: two apps, no tests, no CI, nothing deployed.

## Decision

**Adopt a `src/` layout and rename the settings package `config` → `boutique`.**

```
backend/
├── src/
│   ├── manage.py
│   ├── boutique/     settings, urls, wsgi, asgi, celery
│   ├── apps/         users, products
│   └── api/v1/
├── Makefile  Dockerfile  compose.yaml  pyproject.toml
└── .claude/  .github/  scripts/  docs/
```

Celery is `celery -A boutique`. `BASE_DIR` is the source root; settings gains `ROOT_DIR` for
the repository root, from which it reads `.env`.

The `src/` layout's canonical benefit — code cannot be imported accidentally from the working
directory, so tests exercise the *installed* package — does **not** apply here. This is a
Django application; it is never `pip install`ed. We took it for separation, and we say so
rather than claim a rationale we do not have.

## Consequences

`pytest` needs `pythonpath = "src"`, `mypy` needs `mypy_path = ["./src"]`, and every Makefile
target runs `python src/manage.py`. All of that was going to be written from scratch anyway
under [ADR-0010](0010-no-third-party-code-verbatim.md) — and, an accident but a welcome one,
it happens to match the upstream project's own layout, so their `pyproject` configuration values ported
directly.

Adding `src/api/__init__.py` and `src/api/v1/__init__.py` was required: they were implicit
namespace packages, which works at runtime but made mypy see every module under two names.

The `import config` collision is now impossible.

Rejected: keeping the flat Django-convention layout, on the grounds that every tutorial and
every buildpack assumes it. Render's Python detection expects `manage.py` at the root — but we
deploy from a Dockerfile, where the working directory is ours to choose, so the cost is one
line.

We would revisit only if a deployment platform we wanted could not be told where the source
lives. No candidate has that limitation.
