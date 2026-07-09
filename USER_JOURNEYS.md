# Zita Boutique — User Journeys

This document maps every user journey through Zita Boutique, organized by persona. It is the source
of truth for Playwright E2E cases in the frontend repository. Each journey describes the **what** and
the **why** from the user's perspective; the exact selectors and assertions live in the test suite.

Each journey carries a **System** marker naming which backend owns it today. Zita is mid-migration:
Django owns identity going forward, Supabase still owns everything else, and no cutover is scheduled
(`ADR-0001`).

- 🟩 **Supabase** — live today
- 🟦 **Django** — live today
- ⬜ **Not built**

> **Note on location.** This document lives in the backend repository because the backend will own the
> domain once the catalog, orders, and favorites move off Supabase. Until then it describes behaviour
> that is mostly implemented in the frontend. Keep it here; keep it current.

---

## Platform overview

Zita Boutique is a **mobile-first fashion storefront** for a single seller. It sells affordable
fashion and **handles no money in the app.**

The sale closes the WhatsApp-shop way: a customer builds a **Selection**, then either places a
**no-pay order** (their items plus name, phone, and delivery address) which the seller works from an
**Orders inbox**, or opens **Tubaze** — a live chat with the seller — to ask questions first. The
seller then arranges payment and delivery directly with the customer, offline. Prices render in RWF.

There is no cart total to check out, no card capture, no carrier integration. The order is a lead with
item snapshots attached.

---

## Personas

| Persona | Account | What they can do |
| --- | --- | --- |
| **Guest** | none | Browse, build a Selection, place an order, chat via Tubaze |
| **Customer** | email + password | Everything a guest can, plus **Favorites** |
| **Seller** | email + password, `is_seller` | The entire admin panel |

Two facts follow from this table and drive most of the tests:

**Guests are first-class.** Ordering and chatting never require an account. An account buys exactly
one thing — Favorites persisted across devices. Any journey that forces a guest to register is a bug.

**"Seller" is a flag, not a role table.** Authorization is a single boolean on the user. A valid token
belonging to a non-seller must receive **403**, not 404 and not 200. Absent or invalid token is
**401**. The distinction is the whole authorization model; test both.

---

## Journey 1: Guest — discover

**System:** 🟩 Supabase

### 1.1 Home feed
Land on `/`. The feed is server-paged and virtualized: it renders uniform 3:4 tiles, featured products
first, then newest. Scrolling appends a page without unbounded DOM growth. A category strip sits above
the feed; on desktop a category sidebar replaces it.

### 1.2 Category listing
`/category/[slug]` lists visible products in that category. Filters derive from `category_filters` and
their options; filter state lives in the **URL** (nuqs), so a filtered view is shareable and the back
button restores it.

### 1.3 Shop index
`/shop` lists categories. When the seller has configured a home-filter strip
(`/admin/merchandising`), that strip replaces the default category list; when it is empty the
categories are the fallback.

### 1.4 Hidden products are invisible
Storefront reads filter `visible = true`. A product toggled hidden in the admin must vanish from the
feed, its category, and search — and its detail page must 404 rather than render.

**Assert:** the storefront never returns a product with `visible = false`, on any route.

---

## Journey 2: Guest — product detail

**System:** 🟩 Supabase

`/product/[slug]` is a photo carousel with a colour/size/quantity sheet.

Selecting a colour swaps the carousel to that colour's image, because a variant option may carry an
`image_id`. Selecting a size and quantity enables **Add to Selection**. The swipe pager prefetches the
neighbouring product's detail via `/api/products/[slug]` as it approaches a slide.

**Assert:** a product with no variants still adds to the Selection. A product with variants cannot be
added until every variant group has a chosen option.

---

## Journey 3: Guest — the Selection

**System:** 🟩 Supabase + `localStorage`

The Selection is a Zustand `persist` store keyed to `localStorage`, with a `storage`-event listener so
two tabs stay in sync. It survives a refresh and requires no account. `/bag` presents it as two tabs:
**Bag** and **Favorites**.

### 3.1 Add, adjust, remove
Quick-add from a feed card, or add with variants from the product page. Quantity is adjustable in
place. The bag icon animates on add and shows a count badge.

### 3.2 Availability reconciliation
A Selection can outlive the product. On opening `/bag`, ids are checked against the still-visible set;
items the seller has hidden or deleted are surfaced to the customer rather than silently dropped.

### 3.3 Suggestions
An empty bag shows an empty state. A non-empty bag shows suggestions drawn from the same categories as
its contents.

**Assert:** client-only state is gated on hydration, so the server render and first client render
agree. A count badge that flickers on load is a hydration bug.

---

## Journey 4: Guest — place a no-pay order

**System:** 🟩 Supabase

From the Bag, submit **name, phone, delivery address, and an optional note**. No account. No payment.
No total to confirm.

The order writes an `orders` row plus one `order_items` row per line, each carrying **snapshot
columns**: `name_snapshot`, `price_snapshot`, `color_value`, `size_value`, `image_url_snapshot`,
`quantity`. Snapshots exist so a line still renders correctly after the seller edits or deletes the
product.

**Assert:** editing a product's name and price after an order is placed does not change what the
seller sees in the Orders inbox. This is the single most important data-integrity test in the app.

**Assert:** an order with an empty Selection is rejected. Phone and address are required.

---

## Journey 5: Guest — Tubaze live chat

**System:** 🟩 Supabase Realtime

Tubaze is a **sales channel**, not a support widget. It is always reachable and starts with nothing
but a display name.

A chat session is a row; messages are child rows delivered over a Realtime subscription. A customer
may attach product context — an inquiry card carrying a product snapshot — from the product page or
the Bag. Presence and unread counts are live on both sides.

**Assert:** a guest with no account and no Selection can open Tubaze, send a message, and see the
seller's reply without reloading.

**Assert:** unread counts survive a refresh and clear when the conversation is opened.

---

## Journey 6: Customer — account lifecycle

**System:** 🟦 Django (identity) · 🟩 Supabase (favorites)

### 6.1 Register
`/account/register` with email + password. No email confirmation. `POST /auth/register` creates the
user and returns tokens.

### 6.2 Sign in
`/account/login` posts to the same-origin BFF at `/api/auth/login`, which exchanges credentials at
Django's `/auth/pair` and stores both tokens in **HttpOnly cookies**. Only the user object returns to
the browser.

**Assert:** the access token appears nowhere in the page source, in the RSC Flight payload, or in any
response body reaching the browser (`ADR-0003`, enforced by `check-rsc-token`).

### 6.3 Session refresh is invisible
An expired access token produces a 401 at `/api/django/*`. The proxy refreshes once and retries; the
customer never sees an error, never re-authenticates mid-action.

**Assert:** with a deliberately expired access token, a favorites toggle still succeeds.

### 6.4 Sign out
`/api/auth/logout` blacklists the refresh token server-side and clears both cookies. Best-effort: if
the blacklist call fails, the cookies clear anyway and the browser is logged out.

### 6.5 Password reset
Request a reset by email. **The response is identical whether or not the address has an account** — no
enumeration. A reset link arrives asynchronously via Celery. An expired or tampered token yields 400.

**Assert:** `/auth/password/reset-request` returns the same status and body for a known and an unknown
email.

---

## Journey 7: Customer — Favorites

**System:** 🟩 Supabase

The only account-gated feature. Toggling a favorite writes optimistically to the query cache and
rolls back on error. `/bag`'s Favorites tab renders full product cards, not just ids.

**Assert:** a guest sees a prompt to sign in, not a broken toggle. A signed-in customer's favorites
survive sign-out and sign-in on another device.

---

## Journey 8: Seller — sign in and the admin gate

**System:** 🟦 Django (`IsSeller`) · 🟩 Supabase (current admin guard)

`/admin/login`. `proxy.ts` redirects an unauthenticated visitor away from every `/admin/*` route, and
redirects an authenticated one away from `/admin/login`.

`GET /admin/me` is the gate: **200** means this session is a seller.

**Assert, exhaustively:**

| Request | Expected |
| --- | --- |
| No token | 401 |
| Malformed / expired token | 401 |
| Valid token, `is_seller = false` | **403** |
| Valid token, `is_seller = true` | 200 |

The third row is the one that matters. A customer must never reach an admin surface, and must be told
*forbidden*, not *unauthorized* — the difference tells the frontend whether to re-authenticate or to
refuse.

> **Server-side authorization is mandatory.** Drizzle writes bypass RLS entirely, so the database is
> **not** the gate on the admin mutation path. Every `'use server'` admin action must call the guard
> itself. A missing guard is not caught by any type check.

---

## Journey 9: Seller — products

**System:** 🟩 Supabase

### 9.1 List
`/admin/products`: a Shopify-style list with filter chips (All / Active / Draft) and search.

### 9.2 Create
One screen creates product details **and** photos together. Images stage locally and upload in
parallel on Save. Rapid successive drops must not drop staged photos.

### 9.3 Edit
`ProductEditor` composes the admin patterns: `MediaZone` → title → `FieldRow`s opening `SubScreen`s.
Save lives top-right in the header; nothing persists until then. Prose and one-tap pickers commit live
to draft state; value inputs (price) keep an explicit Done.

### 9.4 Visibility and featured
Toggling visibility removes the product from every storefront read immediately. Featured products sort
first in the home feed.

### 9.5 Delete
Deleting a product must not break the Orders inbox — order lines render from snapshots
(Journey 4). Deleting a category that still has products is refused with a clean conflict, not a
cascade.

**Assert:** a slug collision reports a friendly conflict, not a raw database error. Slugs are
generated from names that may contain non-ASCII characters and must never slugify to empty.

---

## Journey 10: Seller — images and variants

**System:** 🟩 Supabase Storage

Images upload, reorder by drag, and carry alt text. The first image is the main photo. A variant
option may be bound to an image (a colour swatch) and to a hex value.

**Assert:** reordering persists. Deleting an image bound to a variant option leaves the option intact
with no image, rather than orphaning a reference.

---

## Journey 11: Seller — categories, filters, merchandising

**System:** 🟩 Supabase

Categories CRUD. Each category owns ordered filters, each filter owns ordered options. A product is
tagged with filter option values, which drive the storefront's category filtering.

`/admin/merchandising` edits the home strip: an ordered, visibility-toggled list of label + href rows,
replaced atomically. When empty, the storefront falls back to the category list (Journey 1.3).

---

## Journey 12: Seller — Orders inbox

**System:** 🟩 Supabase

`/admin/orders` lists incoming no-pay orders newest first, with a **new** count badge. Each order shows
contact details and the item snapshots. Status moves `new → contacted → done`.

This is the primary close-the-sale path. The seller reads the phone number and calls.

**Assert:** the badge reflects only `new` orders and updates without a reload.

---

## Journey 13: Seller — Tubaze inbox

**System:** 🟩 Supabase Realtime

`/admin/chat` lists open conversations with unread badges and live presence. The seller replies in
real time. Product inquiry cards render the snapshot the customer attached.

**Assert:** a message sent by a guest appears in the seller's inbox without a reload, and the unread
badge increments.

---

## Journey 14: Seller — overview

**System:** 🟩 Supabase

`/admin` shows new orders, product count, active chats, and recently added items. Every number is a
link into the surface it counts.

---

## Journey 15: Resilience — offline, maintenance, PWA

**System:** 🟩 Supabase

The app is installable. `/offline` serves when the service worker has no network. `/maintenance` is
driven **solely by database reachability**: a keep-alive ping trips it only on a genuine outage.

**Assert:** an RLS permission denial (`42501`) means the database answered — it is **up** — and must
never trip maintenance. Pinging a table anyone can read would false-trip on any policy change. This is
a real trap; test it.

---

## Cross-cutting concerns

**Mobile first.** 375px is the base. Touch targets ≥ 44×44px. No hover-only interactions. Every screen
is checked at 375, 768, and 1280.

**Accessibility.** WCAG 2.1 AA. Semantic elements, keyboard reachability, visible focus, alt text on
every image. Colour never carries meaning alone — semantic colours are separated by lightness, not
hue, because protanopia and deuteranopia collapse red/purple/amber.

**The security boundary is `src/lib/`.** `db/` is Drizzle over direct Postgres and **bypasses RLS**;
`supabase/` is the SDK and honours it. Keeping them separate is not organization, it is the boundary.

**What a mocked test cannot prove.** If a test mocks the thing that would fail, it cannot catch that
failure. Every mutation in this document needs one unmocked path.

---

## Open questions

Recorded rather than guessed. Each blocks a journey that is not yet written.

1. **Tubaze after the Supabase cutover.** Chat is Supabase Realtime today, and the original build plan
   assumed GetStream would take it over — a dependency that exists nowhere. Retiring Supabase without
   an answer deletes a working sales channel. No decision, no cutover.
2. **Guest identity.** Guests currently ride Supabase anonymous auth (`is_anonymous`), which is how
   `useCustomer` distinguishes a customer from a guest. Django's model has no anonymous user. What
   identifies a returning guest's chat session after the swap?
3. **Order → account linkage.** `orders.created_by` was dropped by design. Should a signed-in customer
   see their past orders? Today nobody can.
4. **Kinyarwanda.** The UI carries hardcoded Kinyarwanda strings and no i18n library (`ADR-0005`). Is
   the target bilingual, and if so, which is the default locale?
5. **Stock.** Products have no inventory count. Does the seller need one, or is "hidden" sufficient?
