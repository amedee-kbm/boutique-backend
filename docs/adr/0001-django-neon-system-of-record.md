# ADR-0001: Django + Neon becomes the system of record

## Status

Accepted.

## Context

The storefront and seller admin were built on Supabase: Postgres reached through Drizzle,
Supabase Auth for sessions, Supabase Realtime for the Tubaze chat, Supabase Storage for
product images. It works, and it shipped.

Two things pushed against staying.

Drizzle connects directly to Postgres and **bypasses Row Level Security entirely**. RLS is
therefore not the gate on any admin write; the `'use server'` action is. That is a real
authorization boundary living in application code, with nothing but review to enforce it —
`frontend/src/features/auth/services/admin-guard.ts` says as much in a comment.

Second, the domain wants a place to live. Order snapshots, catalog integrity, seller
permissions, and the eventual inventory rules are business logic, and business logic in
server actions is business logic scattered across a UI.

## Decision

**Django, against Neon Postgres, becomes the system of record for identity, catalog and
orders.** The Next.js app becomes its client, and its BFF (see
[ADR-0003](0003-token-custody-in-the-bff.md)).

Identity has already moved: the `User` model, JWT issuance, and the `IsSeller` gate are live
in Django. Catalog and orders follow, per [backend-build.md](../backend-build.md).

## Consequences

**Supabase remains the system of record for chat, realtime, and the existing storefront data
until a separate decision retires it.** No cutover is scheduled by this ADR, and none should
be inferred from it.

That is not a formality. Tubaze — the live chat — is a *sales channel*, not a support widget,
and it is fully implemented on Supabase Realtime: presence, unread counts, an admin inbox,
product inquiry cards. An earlier plan assumed GetStream would take it over. No GetStream
dependency exists anywhere in either repository. **Retiring Supabase today would delete a
working sales channel and put nothing in its place.**

Two questions must be answered before any cutover, and neither has an answer yet:

- What owns chat afterwards?
- What identifies a returning guest? Guests currently ride Supabase anonymous auth
  (`is_anonymous`), which is how `useCustomer` tells a customer from a guest. Django's model
  has no anonymous user.

Both are recorded as open questions in [USER_JOURNEYS.md](../../USER_JOURNEYS.md).

Until then the app has two backends, and that is the honest state.

We would revisit the whole direction if the Django API failed to reach parity on catalog and
orders — at which point staying on Supabase and moving authorization *into* the database,
via RLS and a Postgres-side seller check, is the alternative we did not take.
