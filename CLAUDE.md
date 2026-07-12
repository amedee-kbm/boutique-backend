# CLAUDE.md — Zita Boutique backend

Guidance for Claude Code and other AI assistants working in this repository.

Read [AI_USAGE.md](AI_USAGE.md) once. It explains why the guardrails exist and what they cost.
Then read this.

---

## How you work

**Think before coding.** State your assumptions out loud. If a request has two readings,
present both rather than picking one silently. If a simpler approach exists, say so. If
something is unclear, stop and name what is confusing — a clarifying question before
implementation is free; one after is a rewrite.

**The best code is the code you never wrote.** Before writing, stop at the first rung that
satisfies the task: Does it need to exist? Does Django or the standard library already do it?
Is it already a dependency? Can it be one line? Only then write the minimum that works.

Reject unrequested abstractions — a factory for a single implementation, flexibility nobody
asked for, error handling for impossible states. If the diff is 200 lines and could be 50,
rewrite it.

Never simplify away: input validation at a trust boundary, permission checks, error handling
that prevents data loss, or accessibility. "Lazy" means less code, never a flimsier algorithm.

**Surgical changes.** Touch only what the request requires. Do not reformat adjacent code or
refactor what is not broken. Match the surrounding style even where you would do it
differently. Remove imports your change orphaned; flag pre-existing dead code rather than
deleting it. Every changed line should trace to the request.

**Verify, do not assume.** "Add validation" means write tests for invalid input, then make them
pass. "Fix the bug" means write a test that reproduces it first. Drive the real thing — an
endpoint, a task, a browser — not only the test suite.

---

## The contract

```bash
make check    # ruff format, ruff lint, mypy --strict, migrations, file-length, task-names
make test     # pytest, branch coverage, against a real Postgres
make fix      # auto-fix, then check
```

CI runs exactly these. `make help` lists everything.

**Do not run the whole suite for a one-line change.** Run the tests that cover what you touched.

Two rules govern every gate, and they were paid for
([PM-0001](docs/postmortems/0001-guardrails-that-checked-nothing.md)):

- **A gate is not trusted until it has been observed failing.** Break it on purpose, watch it go
  red, revert. ([ADR-0009](docs/adr/0009-a-gate-must-be-seen-to-fail.md))
- **No third-party code is carried verbatim.** Adopt intent and configuration values; write the
  implementation. ([ADR-0010](docs/adr/0010-no-third-party-code-verbatim.md))

---

## The product, in one paragraph

Zita Boutique is a mobile-first, **multi-tenant** fashion storefront platform for small
ladies'-clothing sellers — Zita in Kigali is the first. **It handles no money.** A shopper
browses a boutique, keeps pieces in a device-local **Bag**, and can open **Tubaze** — a live
customer–seller chat — all without an account. Committing takes a lightweight email/password
account: placing a no-pay, cash-on-delivery order (the Bag plus name, phone and delivery address)
that the seller works from an Orders inbox, or **favoriting** a piece. Payment and delivery are
arranged offline. Prices are in RWF.

[USER_JOURNEYS.md](USER_JOURNEYS.md) is the source of truth for behaviour.

---

## Architecture

```
src/
├── manage.py
├── boutique/        settings, urls, wsgi, asgi, celery, media (R2 storage config)
├── apps/
│   ├── users/       custom User (email login), JWT, password reset, saved addresses
│   ├── boutiques/   Boutique + Membership (tenancy), store-scoped admin, seed_zita
│   ├── products/    catalog — storefront reads (filter/facet/sort/slug), admin writes, R2 upload
│   ├── orders/      authenticated placement, server pricing, idempotency, seller inbox
│   ├── favorites/   account-gated favorites (customer, store, product)
│   └── push/        one VAPID web-push pipe (order-status + new-arrivals)
└── api/v1/          NinjaExtraAPI assembly, permissions
```

Django 6 · django-ninja-extra · Celery + Redis · Neon Postgres · Cloudflare R2 · Python 3.12 ·
**uv, never pip**.

The settings package is `boutique`, not `config` — `config` is a real PyPI distribution and a
top-level package by that name shadows it ([ADR-0011](docs/adr/0011-src-layout-and-boutique-package.md)).

**Django is the single system of record** for catalog, orders, favorites, accounts and boutiques.
Supabase is gone; **Stream** carries chat (no rows persist here) and **Cloudflare R2** holds
product images ([ADR-0013](docs/adr/0013-django-sole-system-of-record-multi-tenant.md), superseding
ADR-0001). The platform is **multi-tenant**: a `Boutique` has a public `slug` (in the API path,
`/api/v1/stores/{slug}/…`) and an internal `store_id` on every domain table.

---

## Conventions

**Dependency direction is controllers → services → models.** Models never import services.
Business logic lives in `services.py`; a controller validates, calls a service, returns.

**Controllers stay thin.** No `try/except` in a view — raise from the service, and let the
exception handler map it to a status code. Use `get_object_or_404`.

**Schemas.** `ModelSchema` for flat rows; declare a field at class level only when it needs
special handling. Use the model's enum class directly, never a bare `str`. Datetimes are
`pydantic.AwareDatetime`, never `datetime.datetime`.

**Typing.** `mypy --strict`, every signature, including tests and fixtures. Prefer a typed
manager over a `t.cast` at the call site — typing `UserManager` deleted two casts from the test
suite, which is the type checker paying for itself.

**Celery tasks pin `name=`.** Always. The name is the contract; the module path is an
implementation detail. `make task-names` enforces it, and it found a real instance of this bug
on its first run.

**Tenancy is not optional.** Every domain table carries a non-nullable `store_id`, and every
query is scoped to the boutique in the path. A new table without a `store_id` is a tenancy hole —
treat it like a missing migration. Seller access is a `Membership(user, boutique, role)`;
`is_seller` is computed (has ≥1 membership). Authorization runs through one
`has_permission(membership, capability)` choke-point — operational capabilities are open to any
member, governance (managing members, store settings) is OWNER-only — never a scattered
`role == OWNER` ([ADR-0013](docs/adr/0013-django-sole-system-of-record-multi-tenant.md)).

**Authorization is three status codes.** 401 means no valid token — re-authenticate. 404 means no
boutique by that slug. 403 means a valid token whose holder is not a member of this boutique, or is
a member lacking the capability — the session is fine, the door is closed. Conflating 401 and 403
sends a signed-in customer into a login loop.

---

## Before you touch a queryset or a task

Read [docs/engineering-notes.md](docs/engineering-notes.md). It covers the failures that cannot
reproduce locally:

- Neon's pooler is PgBouncer in transaction mode. `.iterator()` opens a server-side cursor that
  the pooler orphans at `COMMIT`. Materialise ids with `list(...)` first.
- `transaction.on_commit` never fires under `pytest-django`. A test asserting a task was
  dispatched passes whether or not the dispatch exists.
- The Windows traps in the `Makefile`, which are not your imagination.

---

## Hard rules

- **Never commit to `main`.** Branch `feature/…` or `fix/…`. Conventional commits.
- **Always ask before committing.** Show `git status`, draft the message, wait.
- **Disclose AI assistance** with the `Co-Authored-By: Claude` trailer.
- **Discuss before implementing** anything non-trivial.
- **uv, never pip.** A new dependency is a last resort.
- **Never lower a coverage floor** to make a build green.
- **Never let a gate skip.** A check that cannot evaluate something has failed, not passed.
