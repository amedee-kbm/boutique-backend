# Changelog

All notable changes to the Zita Boutique backend are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe **user- and API-facing impact**, not implementation detail. Breaking changes are
prefixed **Breaking**. Section order: Added, Changed, Fixed, Deprecated, Removed, Security.

## [Unreleased]

### Added
- Quality gate: `make check` runs ruff format, ruff lint, `mypy --strict`, a migration check, a
  file-length ceiling, and a Celery task-name check. `make test` runs the suite with branch
  coverage against a real Postgres. Supply chain: `bandit`, `licensecheck`, `pip-audit`.
- First test suite: 21 tests covering registration, login, token refresh, session identity, the
  seller gate, and password reset. 92% branch coverage, pinned as the floor.
- Custom `User` model with email login, `is_seller` flag, and UUID primary key.
- JWT authentication (`django-ninja-jwt`): `/auth/pair`, `/auth/refresh`, `/auth/blacklist`, plus
  `/auth/register` and a password-reset request/confirm pair that never reveals whether an email has
  an account.
- `IsSeller` permission gate. `GET /admin/me` doubles as the frontend's admin check: a 200 means the
  session belongs to a seller, a 403 means it does not.
- `GET /users/me` for the authenticated customer.
- Password-reset email delivered asynchronously via Celery.
- MIT `LICENSE`.

### Changed
- **Breaking (pre-release)**: login credential is `email`, not `phone_number`. Supersedes the
  phone-login decision recorded in the original build plan. `phone_number` remains a required,
  unique field on the user.
- Adopted a `src/` layout: `manage.py`, `apps/`, `api/`, and the settings package now live under
  `src/`, leaving repository furniture (Makefile, Docker files, `.claude/`, `.github/`, `pyproject.toml`)
  at the root. The Django settings package was renamed `config` → `boutique`; `config` is a generic
  top-level name that shadows a real PyPI distribution. Celery is now `celery -A boutique`.
- Celery's password-reset task now pins `name="users.send_password_reset_email"`. It previously
  registered under its module path, so moving the module would have stranded queued messages.

### Fixed
- **CORS was refusing every cross-origin request.** `CorsMiddleware` was installed but no
  `CORS_ALLOWED_ORIGINS` was ever set, so the allow-list was empty.
- **Neon's pooled endpoint is PgBouncer in transaction mode**, which orphans server-side cursors at
  COMMIT and does not permit persistent connections. Set `DISABLE_SERVER_SIDE_CURSORS = True` and
  `CONN_MAX_AGE = 0`. This class of failure cannot reproduce against a local Postgres.
- `apps.products` was in neither `INSTALLED_APPS` nor the API router — a dangling module. Registered.
- The database URL's port was ignored; connections always went to 5432.

### Removed
- Inherited engineering scaffolding that described a different product: CI workflows, an
  observability stack, a load-test suite, a documentation tree, and operational scripts. What Zita
  keeps of that methodology is rewritten from intent, not copied (`ADR-0010`).

[Unreleased]: https://github.com/amedee-kbm/boutique-backend/commits/main
