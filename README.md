# Zita Boutique — backend

Zita Boutique is a mobile-first, **multi-tenant** storefront platform for small ladies'-clothing
sellers — Zita in Kigali is the first. **It handles no money.** A shopper browses a boutique,
keeps pieces in a device-local **Bag**, and can open **Tubaze** — a live customer–seller chat —
all without an account. Committing takes a lightweight email/password account: placing a no-pay,
cash-on-delivery **order** (the Bag plus name, phone and delivery address) that lands in the
seller's Orders inbox, or **favoriting** a piece. The seller settles payment and delivery offline.
Prices are in RWF.

One Django backend is the **single system of record** for catalog, orders, favorites, accounts and
boutiques over a shared Postgres, with every tenant isolated by `store_id`. **Stream** carries chat
and **Cloudflare R2** holds product images; nothing transactional lives outside Django
([ADR-0013](docs/adr/0013-django-sole-system-of-record-multi-tenant.md)).

Django 6 · django-ninja-extra · Celery + Redis · Neon Postgres · Cloudflare R2 · Python 3.12 ·
[uv](https://docs.astral.sh/uv/), never pip.

> **Where to read next:** [CLAUDE.md](CLAUDE.md) for how work is done here,
> [docs/backend-build.md](docs/backend-build.md) for the phased build plan,
> [USER_JOURNEYS.md](USER_JOURNEYS.md) for behaviour, and [docs/adr/](docs/adr/) for the decisions.

## Layout

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

Every domain table carries a non-nullable `store_id`; the public **slug** appears in the API path
(`/api/v1/stores/{slug}/…`) while the internal `store_id` UUID scopes the rows. Seller access is a
`Membership(user, boutique, role)`; `is_seller` is computed from it.

## Quickstart

```bash
make setup        # uv sync, copy .env, start Postgres/Redis/Mailpit, migrate
make test         # the suite, with branch coverage, against a real Postgres
make run          # dev server on :8000  (OpenAPI at /api/v1/docs/)
```

Fill `DJANGO_SECRET_KEY`, `DATABASE_URL`, the R2 keys and (for web push) the VAPID keys in `.env`
— see [.env.example](.env.example). Without an R2 bucket configured, image storage falls back to
an in-memory backend, so tests and local dev need no cloud credentials.

Seed the first store from the Supabase export (idempotent; re-keys images into R2):

```bash
uv run python src/manage.py seed_zita --owner-email you@example.com   # --dry-run to preview
```

## The contract

```bash
make check        # ruff format, ruff lint, mypy --strict, migrations, file-length, task-names
make test         # pytest, branch coverage, against a real Postgres
make deps-check   # licence + known-vulnerability audit
make fix          # auto-fix, then check
```

CI runs exactly these; `make help` lists everything. Two rules govern every gate: a gate is not
trusted until it has been [observed failing](docs/adr/0009-a-gate-must-be-seen-to-fail.md), and no
third-party code is [carried verbatim](docs/adr/0010-no-third-party-code-verbatim.md).
