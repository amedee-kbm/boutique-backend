# ADR-0013: Django is the sole system of record; the platform is multi-tenant

## Status

Accepted. Supersedes [ADR-0001](0001-django-neon-system-of-record.md).

## Context

[ADR-0001](0001-django-neon-system-of-record.md) made Django the system of record for
identity, catalog and orders, and then deliberately stopped there. Supabase kept chat,
realtime, and the live storefront data; no cutover was scheduled. It named two blockers by
name, and both were real at the time:

- **Nothing owned chat after Supabase.** Tubaze is a sales channel, not a support widget, and
  it was fully implemented on Supabase Realtime. "No GetStream dependency exists anywhere in
  either repository." Retiring Supabase would have deleted a working channel and put nothing in
  its place.
- **Nothing identified a returning guest.** Guests rode Supabase anonymous auth (`is_anonymous`),
  which is how the frontend told a customer from a guest. Django's model had no anonymous user.

Three things have changed since, and together they retire both blockers and the "no cutover"
posture with them.

**The product is multi-tenant.** ADR-0001, the deleted `backend-build.md`, and the old
`CLAUDE.md` all assumed a single seller — Zita. The product is now a platform: many small
ladies'-clothing boutiques, Zita being the first, each running a catalog and taking no-pay
orders in isolation from the others. A single-seller schema makes `store_id` a later migration
on **every** table — the most expensive retrofit there is, and the one guaranteed to be
forgotten on exactly one table. Tenancy has to exist before the first catalog row, not after.

**Chat has an owner.** Stream is the chat transport — guest tokens minted in the BFF
([ADR-0003](0003-token-custody-in-the-bff.md)), the Bag and favorites riding along as product
context, no chat rows persisted in our database. That answers ADR-0001's first blocker directly:
retiring Supabase no longer deletes a sales channel into a vacuum; it moves the channel to Stream.

**The guest question dissolved rather than got answered.** Committing — placing an order or
favoriting — now requires an email/password account. A guest browses, keeps a **device-local
Bag**, and chats under a `guest_*` Stream identity; none of that is server state to preserve. So
there is no anonymous server user to reconcile on login, and ADR-0001's second blocker is moot
rather than solved. (Carrying a guest's chat history across registration is a post-MVP nicety on
the Stream side, not a database concern.)

With both blockers gone, "Supabase remains the system of record until a separate decision retires
it" is no longer the honest state. This is that separate decision.

## Decision

**Django, against Neon Postgres, is the _single_ system of record** for boutiques, memberships,
catalog, orders, favorites and accounts. Nothing transactional lives outside it.

**Supabase is removed in full** — not just orders and favorites, but the catalog (today
Drizzle-direct to Supabase Postgres), product images (Supabase Storage), web-push subscriptions,
and the unused `chat_*` tables. **Stream** carries chat and persists no rows here. **Cloudflare
R2** holds product images, written through Django and served from a custom bucket domain.

**The data model is multi-tenant from the first migration.**

- A **`Boutique`** carries a public **`slug`** — which appears in the API path,
  `/api/v1/stores/{slug}/…` — and an internal **UUID `store_id`** that is a **non-nullable**
  foreign key on every domain table. There is no such thing as a store-less product or order.
- Seller access is a **`Membership(user, boutique, role)`** join. `is_seller` is **computed**:
  a user is a seller iff they hold at least one membership. A request's tenant is the membership
  whose boutique matches the path slug; a **slug/membership mismatch is `403`, not `401`**
  (the session is valid; the door is closed — the two-status rule in `CLAUDE.md`). A user may
  hold memberships at several boutiques and is scoped per-request by the slug, so the
  multi-shop-owner case costs nothing extra.
- **Customer identity is global.** `email` and `phone` stay globally unique; a customer is *not*
  a membership. The guardrail that keeps this safe under strict tenancy: **an admin may only ever
  see customers who have an order or favorite in that admin's own store — never the global user
  table.** Global existence, per-store visibility.

**Roles are an enum — `OWNER` and `STAFF` — not a permission map.** Both roles work
orders/inbox, Tubaze, and catalog. **OWNER-only** is managing members (add/remove staff) and
store settings/credentials. The check runs through a single `has_permission(membership, capability)`
choke-point, never a scattered `role == OWNER`.

**Build order is dependency-first:** tenancy → catalog (+R2) → orders → favorites/accounts →
push. The phased plan is [backend-build.md](../backend-build.md).

## Consequences

**Every domain query is store-scoped by construction, and the multi-shop case is free.** A
missing `store_id` on a new table is a tenancy hole, and review must treat it the way it treats
a missing migration — not a nit, a defect. The frontend's `SELLER_STREAM_ID = 'zita-seller'`
constant and its `admins` allowlist stop being constants and become real `Boutique` and
`Membership` rows.

**There is no "global" product or order, so the seed is a transformation, not a load.** The
Supabase export is single-tenant: it has `admins`, not stores. Seeding it "respecting our schema"
means synthesizing **Zita as store row #1** and stamping its `store_id` onto all 67 products, 5
categories, 134 variant groups and the rest — and copying 128 storage objects into R2 under
`stores/zita/products/…`. This is described in [backend-build.md](../backend-build.md); it is why
the seed is code, not a `loaddata`.

**The role model is the alternative we did not take, and it is worth recording why.** The
reference we studied — a multi-tenant Django event platform — does *not* use a role enum. Its
organization carries an `owner` foreign key with implicit all-permissions, and each staff row
carries a **granular JSON permission map**: two dozen capability booleans, per-event overrides,
validated by a pydantic schema. That is the correct shape for an org with many events and
fine-grained delegation. A boutique has a handful of staff and exactly **one** governance
boundary — members and settings — so the JSON map is flexibility nobody asked for, and the enum
sits at the right altitude. What we keep from that reference is structural, not its mechanism:

- **The operational/governance split**, which its own defaults corroborate — operational
  capabilities default *on*, `manage_members` and `edit_organization` default *off*.
- **One choke-point for the check.** If a "works the inbox but not the catalog" role ever
  appears, graduating the enum to a per-membership permission map is a change *behind*
  `has_permission`, not a new scatter of conditionals across controllers.

**ADR-0001's RLS alternative is now doubly closed.** Its fallback — if Django failed to reach
parity, stay on Supabase and move authorization *into* Postgres via Row Level Security — is
harder under tenancy, not easier: cross-boutique row isolation in RLS is more machinery than
app-layer store-scoping, not less. We are committed to the application being the authorization
boundary, which is the very thing ADR-0001 disliked about the Drizzle status quo — the
difference is that the boundary now lives in typed services behind a strict type checker, not in
scattered `'use server'` actions.

**This ADR authorizes the removal; it does not perform it.** Supabase, Drizzle, and the storefront
data come out surface-by-surface behind flags on the frontend, catalog-reads first and the
Drizzle/Supabase clients last, per the cutover order in [backend-build.md](../backend-build.md).
Until a surface flips, two systems run — the same honest two-backend state ADR-0001 described,
now with a scheduled end.

## Reversal

Two conditions, at very different costs.

1. **The platform never gets a second boutique.** Then the tenancy tax — a `store_id` join on
   every query, a slug on every path — bought nothing, and a single-tenant schema would have been
   cheaper. But that reversal is a schema collapse across every table, not a config change, which
   is precisely why tenancy is built now rather than deferred: the cheap direction is *toward*
   multi-tenant from an empty schema, and there is no cheaper moment than before the first row.

2. **Delegation needs outgrow the binary before MVP ships.** Then the `OWNER`/`STAFF` enum
   graduates to a per-membership permission map at the `has_permission` choke-point named above.
   That is a change of mechanism behind a stable boundary — an implementation detail, not a new
   ADR.
