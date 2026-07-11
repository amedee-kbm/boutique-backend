# Backend build plan — multi-tenant Django, from the scaffold

The checklist that takes this backend from its current state — a real `users` app and an empty
`products` scaffold — to the API the Next.js storefront and admin consume. It replaces an earlier
plan written for a **single seller**; that plan was deleted, not restored, because the product
changed underneath it.

Canonical decisions live in [ADR-0013](adr/0013-django-sole-system-of-record-multi-tenant.md):
Django is the **single** system of record, Supabase is removed in full, and the platform is
**multi-tenant** — many boutiques, Zita first. Where this document and an ADR disagree, the ADR
wins.

The old Supabase/Drizzle catalog is referenced **only for shape and business rules** — no code is
carried verbatim ([ADR-0010](adr/0010-no-third-party-code-verbatim.md)).

---

## Locked decisions

- **No money moves through the app.** No cart total, no card capture, no carrier integration. An
  order is a lead with item snapshots. Prices render in RWF.
- **Multi-tenant, tenancy first.** Every domain table carries a **non-nullable** `store_id` FK.
  Public **slug** in the API path (`/api/v1/stores/{slug}/…`), internal UUID `store_id` FK
  everywhere. Built in Phase 1, before any catalog or order code, so nothing needs a `store_id`
  retrofit.
- **Seller = membership.** `Membership(user, boutique, role=OWNER|STAFF)`. `is_seller` is
  computed (has ≥1 membership). Slug/membership mismatch → `403`.
- **Committing needs an account.** Orders and favorites are **authenticated** (customer JWT).
  Guests get browsing, a **device-local Bag**, and Tubaze chat — nothing that commits.
- **Server-authoritative pricing.** An order posts `variant_id` + quantity; the server re-prices
  from the variant and **stores a price snapshot**. The client never dictates price. The product
  payload must therefore expose `variant_id`.
- **"Bag", everywhere.** The device-local selection is the **Bag**. `Cart`/`Selection` do not
  appear in code, schemas, or the order payload field name.
- **Media on Cloudflare R2.** Django owns uploads via the `django-storages` S3 backend
  (`endpoint_url` → R2); public catalog images are served from a **custom bucket domain**, not
  signed URLs. Keys are tenant-scoped: `stores/{slug}/products/…`.
- **Chat is Stream, transport only.** No chat rows persist here. `chat_*` and `push_subscriptions`
  from the export are not ported.

---

## Supabase/Drizzle → Django model map

`store_id` is added to every row and is **not** in the export — the seed synthesizes it (Phase 6).

| Supabase table | Django model | App | Notes |
| --- | --- | --- | --- |
| `admins` | — (dropped) | — | replaced by `Boutique` + `Membership` |
| — | `Boutique` | boutiques | `slug` (public, in path), UUID `store_id` |
| — | `Membership` | boutiques | `(user, boutique, role)`; `role ∈ {OWNER, STAFF}` |
| — | `User` (exists) | users | global identity, email login; `is_seller` **computed**, not a column |
| `categories` | `Category` | catalog | `+ store_id`; slug unique **per store** |
| `products` | `Product` | catalog | `+ store_id`; slug unique per store; `visible`, `featured` |
| `product_images` | `ProductImage` | catalog | `+ store_id`; URL is an R2 public URL; circular FK with option |
| `product_variant_groups` | `ProductVariantGroup` | catalog | `+ store_id` |
| `product_variant_options` | `ProductVariantOption` | catalog | `+ store_id`; **`variant_id` exposed in payload** |
| `category_filters` | `CategoryFilter` | catalog | `+ store_id`; 0 rows in export, code path stays |
| `category_filter_options` | `CategoryFilterOption` | catalog | `+ store_id`; 0 rows |
| `product_filter_values` | `ProductFilterValue` | catalog | composite PK `(product, option)`; 0 rows |
| `home_filters` | `HomeFilter` | catalog | `+ store_id` |
| `orders` | `Order` | orders | **authed**; `+ store_id`, `+ customer` FK; **no** `created_by`-as-guest |
| `order_items` | `OrderItem` | orders | snapshot columns kept; `+ variant`, `+ price_snapshot` |
| `favorites` | `Favorite` | favorites | `(customer, store, product)`; account-gated |
| `chat_*`, `push_subscriptions` | — (excluded) | — | Stream owns chat; push is a fresh Django pipe (Phase 5) |

Type mapping: `uuid → UUIDField(default=uuid4)`, `numeric(10,2) → DecimalField(max_digits=10,
decimal_places=2)`, `text → TextField`, `slug unique → SlugField` **with a per-store
`UniqueConstraint`, not `unique=True`**, `timestamp defaultNow → auto_now_add`, `updatedAt →
auto_now`, `pgEnum → TextChoices`.

---

## What the reference repos taught us

Two local repos were studied for pattern, not for code. What we adopt and what we reject:

| From | Adopt | Reject |
| --- | --- | --- |
| `revel-backend` (multi-tenant event platform) | Owner has implicit all-permissions; operational capabilities open, governance (members/settings) gated; **one `has_permission` choke-point**; store-scoped credential models | Its granular JSONField permission map + per-event overrides — right for many-events delegation, over-built for one governance boundary (see ADR-0013) |
| `ecommerce-backend` (multi-store catalog) | Price **snapshot** on the order line at time of order; store-scoped credentials as their own models | **Nullable/`SET_NULL` store FK** (we require non-null); global-unique slugs (we scope per store); treebeard categories and the seller/packer/listing marketplace split (we stay flat) |

---

## Phase 0 — Dependencies & project config

- [ ] Add deps with **uv** (`uv add`, never pip): `django-storages[s3]` (R2 uploads),
      `pywebpush` (Phase 5). `psycopg[binary]`, `django-ninja-extra`, `django-ninja-jwt`,
      `django-cors-headers`, `django-environ` are already in.
- [ ] R2 env (gitignored `.env` + `.env.example`): `R2_BUCKET`, `R2_ENDPOINT`
      (`https://ACCOUNT.r2.cloudflarestorage.com`), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
      `R2_PUBLIC_HOST` (the custom bucket domain).
- [ ] `STORAGES["default"]` → S3 backend pointed at `endpoint_url = R2_ENDPOINT`, `querystring_auth
      = False` (public objects), `custom_domain = R2_PUBLIC_HOST`. Verify against the installed
      `django-storages` version — the setting names have moved between releases.
- [ ] Register the new apps: `apps.boutiques`, `apps.catalog`, `apps.orders`, `apps.favorites`.
- [ ] The Neon pooler traps in [engineering-notes.md](engineering-notes.md) still apply:
      `CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS=True`, and `list(...)` before `.iterator()`.

---

## Phase 1 — Tenancy (built first)

Nothing below this phase gets written until it stands, so no table is born without a `store_id`.

- [ ] `apps/boutiques/models.py`:
  ```python
  class Boutique(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # the store_id
      slug = models.SlugField(max_length=255, unique=True)   # public, appears in the API path
      name = models.CharField(max_length=255)
      created_at = models.DateTimeField(auto_now_add=True)

  class Membership(models.Model):
      class Role(models.TextChoices):
          OWNER = "owner", "Owner"
          STAFF = "staff", "Staff"
      user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="memberships")
      boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name="memberships")
      role = models.CharField(max_length=8, choices=Role.choices)

      class Meta:
          constraints = [models.UniqueConstraint(fields=["user", "boutique"],
                                                  name="uniq_membership")]
  ```
- [ ] `store_id` is the FK pattern every later table repeats:
      `store = models.ForeignKey("boutiques.Boutique", on_delete=models.PROTECT, db_column="store_id")`
      — **non-nullable**, `PROTECT` so a boutique with catalog cannot be deleted out from under it.
- [ ] **Tenant resolution** as one dependency, not per-view logic: resolve the `{slug}` path param
      to a `Boutique`; for seller routes, require a `Membership(request.user, boutique)` and
      **`403` on mismatch** (not `401` — the two-status rule in `CLAUDE.md`).
- [ ] **`is_seller` is computed** — `user.memberships.exists()` — never a column. A typed manager
      or property, so `mypy --strict` carries it.
- [ ] **`has_permission(membership, capability)`** is the single authorization choke-point.
      Operational capabilities (orders/inbox, Tubaze, catalog) return `True` for both roles;
      governance (`manage_members`, `edit_store_settings`) returns `True` only for `OWNER`. Every
      seller controller calls this; no controller writes `role == OWNER` inline. This is the seam
      ADR-0013 names for a future enum→permission-map graduation.
- [ ] **`/me`** returns the user plus `memberships: [{ store, role }]` — how the admin UI learns
      its tenant(s) and whether to show OWNER-only controls.
- [ ] Tests: a seller scoped to boutique A gets `403` on boutique B's path; a customer with no
      membership reads `is_seller = false`; the permission choke-point denies STAFF on a governance
      capability and allows it on an operational one. Prove each gate red before trusting it green
      ([ADR-0009](adr/0009-a-gate-must-be-seen-to-fail.md)).

---

## Phase 2 — Catalog (+ R2), at parity

The catalog is a **live, load-bearing** system today: storefront reads + admin CRUD, server-side
filtering, multi-facet AND/OR, price ranges, sort, slugs, cover images, live counts. Django
**replicates** it. Every model gains `store_id`; every query is filtered by the resolved tenant;
slugs are unique **per store**.

Endpoints owed to the frontend (all under `/api/v1/stores/{slug}/`):

- [ ] **Product list** with the existing filter / facet / price / sort params, **visible-only** for
      the storefront.
- [ ] **Facet-count** endpoint — the "Show N results" meta the current UI renders.
- [ ] **Category index** (with product counts + cover image), **category-by-slug**,
      **product-by-slug** (variants, images, filter values) — the product payload **exposes
      `variant_id`**, which the Bag stores and the order posts.
- [ ] **Image upload** → R2, returning the public custom-domain URL. Key `stores/{slug}/products/…`.
- [ ] **Atomic product-create** (product + variants + images in one transaction) — the parity
      replacement for today's single Drizzle transaction.
- [ ] Admin writes require a seller membership + the operational capability; storefront reads are
      public but still tenant-scoped by slug.
- [ ] Querysets: materialize ids with `list(...)` before any `.iterator()` (Neon pooler).

---

## Phase 3 — Orders

- [ ] **Authenticated only** (customer JWT). There is no open/guest order endpoint — this deletes
      the unauthenticated-write abuse surface entirely.
- [ ] **Server-authoritative price snapshot.** The create posts `bag` (a list of `variant_id` +
      quantity) + the contact details; the service re-prices each line from the variant and writes
      `price_snapshot`, `name_snapshot`, `image_url_snapshot` onto the `OrderItem`. The client
      never sends a price.
  ```python
  class Order(models.Model):
      class Status(models.TextChoices):
          NEW = "new", "New"
          CONFIRMED = "confirmed", "Confirmed"
          FULFILLED = "fulfilled", "Fulfilled"
          CANCELLED = "cancelled", "Cancelled"
      store = models.ForeignKey("boutiques.Boutique", on_delete=models.PROTECT, db_column="store_id")
      customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="orders")
      status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
      # contact snapshot taken from the account at order time:
      contact_name = models.TextField()
      phone = models.TextField()
      delivery_address = models.TextField()
      idempotency_key = models.CharField(max_length=255)
      created_at = models.DateTimeField(auto_now_add=True)

      class Meta:
          constraints = [models.UniqueConstraint(fields=["store", "idempotency_key"],
                                                  name="uniq_order_idem")]
  ```
- [ ] **Status vocabulary is four states:** `new → confirmed → fulfilled → cancelled`. (The
      WhatsApp-flow "contacted" state was considered and dropped; revisit only if the seller asks
      for a "reached out, awaiting confirm" signal.)
- [ ] **Idempotency key** on create, unique per store — a double-submit returns the first order,
      not a second.
- [ ] Contact details live on the **account**; prefill is a normal authed `/me` + saved-addresses
      fetch, snapshotted onto the order at creation.
- [ ] **Inbox is poll-based** (realtime is gone). The list endpoint supports a `since`/cursor or
      returns a new-count so polling stays cheap. Seller-scoped by membership.
- [ ] If an order confirmation email/push is dispatched on commit, note that
      `transaction.on_commit` **does not fire under `pytest-django`** — assert dispatch the way
      [engineering-notes.md](engineering-notes.md) prescribes, or the test passes vacuously.

---

## Phase 4 — Favorites & accounts

- [ ] `Favorite` is `(customer, store, product)`, account-gated — list / add / remove for the
      logged-in customer, scoped to the store in the path.
  ```python
  class Favorite(models.Model):
      customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
      store = models.ForeignKey("boutiques.Boutique", on_delete=models.CASCADE, db_column="store_id")
      product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
      created_at = models.DateTimeField(auto_now_add=True)

      class Meta:
          constraints = [models.UniqueConstraint(fields=["customer", "store", "product"],
                                                  name="uniq_favorite")]
  ```
- [ ] Customer account carries name, phone, and **saved delivery addresses** (Phase 3 prefill).
      Email login already exists ([ADR-0004](adr/0004-email-is-the-login-credential.md)); this
      subsystem is now **core**, required for both ordering and favoriting.
- [ ] The customer-visibility guardrail (ADR-0013): the admin's customer views select only users
      with an order or favorite **in that admin's store** — never the global user table.

---

## Phase 5 — Push (PWA-aware, one Django-owned pipe)

A PWA has one service worker and one background push subscription, so there is exactly **one**
background-push provider, and it is ours.

- [ ] VAPID web-push via `pywebpush`: one subscription, our service worker. Synchronous send is
      fine at this volume (the queue stays dormant — [ADR-0012](adr/0012-the-queue-is-dormant.md)).
- [ ] Carries **order-status** (targeted to the subscriber) and **new-arrivals** (per-store
      broadcast; the subscription row carries `store_id`).
- [ ] Foreground/in-app chat pings come free from Stream over its websocket — **no** web-push for
      chat. (Post-MVP, background chat pings ride this *same* pipe via a Stream `message.new`
      webhook — never a second provider.)

---

## Phase 6 — Seed Zita as store #1

The export (`data/supabase-export.json`) is single-tenant: 5 categories, 67 products, 134 variant
groups, 372 variant options, 67 images, 1 home filter, and **0** filter rows. It has `admins`, not
stores. The seed is a **schema-aware transformation**, not `loaddata`:

- [ ] Create **Zita** as `Boutique(slug="zita")` — store row #1 — and seed its `Membership` rows
      from the two `admins`.
- [ ] Stamp Zita's `store_id` onto every imported category, product, variant, image, home filter.
- [ ] Copy the 128 storage objects into R2 under `stores/zita/products/…`. The export already
      carries a precomputed `r2Key` per asset, so this is a copy, not a re-key; rewrite each
      `ProductImage.url` to the R2 public URL.
- [ ] Idempotent and re-runnable — a management command, not a migration.
- [ ] Stand up a **staging instance with the seeded Zita store** as the frontend's acceptance
      target, and publish OpenAPI (Ninja emits it free) for the frontend's client codegen.

---

## Frontend cutover order (recap)

The frontend adopts **after**, surface-by-surface behind flags, because the catalog is
Drizzle-direct and a big-bang is riskier: catalog reads → admin catalog + image storage →
customer-auth transport → favorites → orders (now auth-gated at checkout) → inbox polling →
**delete the Drizzle/Supabase clients last.**
