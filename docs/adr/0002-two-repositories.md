# ADR-0002: Two repositories, not a monorepo

## Status

Accepted.

## Context

The project began as a Next.js app at the repository root. A `backend/` directory was later
added alongside a `frontend/` directory, making a monorepo — but only locally. The monorepo
was never pushed: the remote still held the frontend at the root.

Three facts made the choice unusually cheap to get right.

GitHub reads only a **root-level** `.github/`. Nested workflow directories never execute, so
neither half had ever had CI, and neither would until the layout was resolved.

The two halves share nothing at build time. No common package, no shared types, no
cross-imports. The only contract between them is HTTP, and it is versioned as `/api/v1`.

Their toolchains do not overlap: `uv` and `pytest` on one side, `npm` and `vitest` on the
other. A monorepo tool that understood both would be pure overhead.

## Decision

**Two repositories: `boutique-frontend` and `boutique-backend`.**

The frontend keeps the existing repository, whose history already contains exactly that, at
the root. The backend is extracted with `git filter-repo` into a new one, preserving the
trail from scaffold through the auth work.

Shared process files live in a public `amedee-kbm/.github` repository, which GitHub applies
as defaults to every repository owned by the account — including private ones.

## Consequences

Each repository has one `Makefile`, one CI pipeline, one language, one release cadence. CI
runs for the first time in this project's history.

A change spanning both halves — an API contract change, say — becomes two pull requests,
merged in an order that matters: the backend must ship the endpoint before the frontend may
call it. This is a real cost, paid in coordination rather than tooling.

Some things cannot be centralized. `LICENSE` (GitHub forbids defaulting it, so it travels
with a clone), `CODEOWNERS`, `dependabot.yml`, and the `.claude` skills are duplicated, and
they will drift. The org `.github` repository catches everything else.

We would revisit this if the halves ever needed to share generated types at build time — an
OpenAPI client generated from the backend and consumed by the frontend is the obvious
candidate, and a monorepo makes that one command instead of a publish step. Today that client
does not exist.
