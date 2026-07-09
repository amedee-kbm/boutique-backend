# Backend Rewrite — Django Ninja + Neon (from scratch)

> **Superseded in part.** This document's "Auth: phone-number login" decision was overtaken by
> the implementation and is now formally superseded by
> [ADR-0004](adr/0004-email-is-the-login-credential.md): **email is `USERNAME_FIELD`**.
> `phone_number` remains a required, unique field, but it is not a credential.
>
> Everything else here stands. Phases 0, 1 and 9 are largely done; Phases 2–8 are the plan of
> record for the catalog, orders, favorites and R2 uploads.

Build checklist to take the backend from its current scaffold (one health endpoint, empty apps) to a
complete API the Next.js frontend can consume. Written to be built **from scratch**, referencing the old
Supabase/Drizzle code only for shape and business rules.

## Locked decisions

- **Auth: Django owns identity fully.** Custom `User` (**phone-number login**) + JWT via `django-ninja-jwt`. No
  Supabase Auth. The old `admins` allowlist table is dropped — "seller/admin" becomes an `is_seller` flag on `User`.
- **Chat: excluded.** Do NOT port `chat_sessions`, `chat_messages`, `chat_message_items`, `push_subscriptions`.
  GetStream owns chat; product inquiry snapshots ride as GetStream message `extraData` (frontend concern later).
- **Guests never authenticate.** Orders are guest-allowed with contact details only — `orders.created_by` is
  dropped. Favorites are the only customer-account feature.
- **Fresh migrations.** Django is the schema source of truth now. No data migration from Supabase; `makemigrations`
  from the models below and `migrate` straight onto Neon.

## Drizzle → Django model map

| Drizzle table | Django model | App | Notes |
| --- | --- | --- | --- |
| `admins` | — (dropped) | — | replaced by `User.is_seller` |
| — | `User` | users | phone login, `is_seller` |
| `categories` | `Category` | catalog | |
| `products` | `Product` | catalog | |
| `product_images` | `ProductImage` | catalog | circular FK with variant option |
| `product_variant_groups` | `ProductVariantGroup` | catalog | |
| `product_variant_options` | `ProductVariantOption` | catalog | circular FK with image |
| `category_filters` | `CategoryFilter` | catalog | |
| `category_filter_options` | `CategoryFilterOption` | catalog | |
| `product_filter_values` | `ProductFilterValue` | catalog | composite PK |
| `home_filters` | `HomeFilter` | catalog | |
| `orders` | `Order` | orders | drop `created_by` |
| `order_items` | `OrderItem` | orders | snapshot columns kept |
| `favorites` | `Favorite` | favorites | composite PK, FK → User |
| `chat_*`, `push_subscriptions` | — (excluded) | — | GetStream |

Type mapping: `uuid` → `UUIDField(default=uuid4)`, `numeric(10,2)` → `DecimalField(max_digits=10, decimal_places=2)`,
`text` → `TextField`, `slug unique` → `SlugField(unique=True)`, `timestamp defaultNow` → `auto_now_add`,
`updatedAt` → `auto_now`, `pgEnum` → `TextChoices`.

---

## Phase 0 — Dependencies & project config

- [ ] Add deps (edit `backend/pyproject.toml`, then `uv sync`):
  - `psycopg[binary]` — Postgres/Neon driver (psycopg3, Django 6 default)
  - `django-ninja-extra` + `django-ninja-jwt` — JWT auth controllers + `JWTAuth`
  - `django-cors-headers` — CORS for the Next.js origin
  - `django-storages[s3]` — R2 uploads via the S3 backend (boto3 under the hood)
  - `django-environ` — env parsing (`DATABASE_URL`, secrets)
- [ ] Create `backend/.env` (gitignored) and `backend/.env.example`:
  ```dotenv
  DJANGO_SECRET_KEY=change-me
  DJANGO_DEBUG=True
  DATABASE_URL=postgresql://USER:PASS@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
  CORS_ORIGINS=http://localhost:3000
  # R2 (Phase 8)
  R2_BUCKET=product-images
  R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID=
  R2_SECRET_ACCESS_KEY=
  R2_PUBLIC_HOST=pub-xxxx.r2.dev
  ```
- [ ] Rewrite `backend/config/settings.py` env-driven section:
  ```python
  import environ
  env = environ.Env(DJANGO_DEBUG=(bool, False))
  environ.Env.read_env(BASE_DIR / ".env")

  SECRET_KEY = env("DJANGO_SECRET_KEY")
  DEBUG = env("DJANGO_DEBUG")
  ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

  INSTALLED_APPS = [
      "django.contrib.admin",
      "django.contrib.auth",
      "django.contrib.contenttypes",
      "django.contrib.sessions",
      "django.contrib.messages",
      "django.contrib.staticfiles",
      "corsheaders",
      "ninja_extra",
      "apps.users",
      "apps.catalog",
      "apps.orders",
      "apps.favorites",
  ]

  MIDDLEWARE = [
      "corsheaders.middleware.CorsMiddleware",       # first
      "django.middleware.security.SecurityMiddleware",
      "django.contrib.sessions.middleware.SessionMiddleware",
      "django.middleware.common.CommonMiddleware",
      "django.middleware.csrf.CsrfViewMiddleware",
      "django.contrib.auth.middleware.AuthenticationMiddleware",
      "django.contrib.messages.middleware.MessageMiddleware",
      "django.middleware.clickjacking.XFrameOptionsMiddleware",
  ]

  DATABASES = {"default": env.db("DATABASE_URL")}
  # Neon pooler is PgBouncer transaction mode — do not hold connections open.
  DATABASES["default"]["CONN_MAX_AGE"] = 0
  DATABASES["default"].setdefault("OPTIONS", {})
  DISABLE_SERVER_SIDE_CURSORS = True

  AUTH_USER_MODEL = "users.User"
  CORS_ALLOWED_ORIGINS = env.list("CORS_ORIGINS")

  NINJA_JWT = {
      "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
      "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
      "USER_ID_FIELD": "id",
  }
  ```
  > Verify against installed versions: the `STORAGES` block (Phase 8), `env.db()` parsing of the `sslmode`
  > query param, and that psycopg3 is picked up (`ENGINE` should be `django.db.backends.postgresql`).

---

## Phase 1 — Users app (custom User + JWT auth)

- [ ] Keep and flesh out the existing `backend/apps/users/` — it already has a phone-based `User`
      ([backend/apps/users/models.py](backend/apps/users/models.py)) and `UserManager`. Add the fields the API
      needs (UUID pk, `is_seller`, `is_active`, `is_staff`, `created_at`). Don't delete the app.
- [ ] `apps/users/models.py`:
  ```python
  import uuid
  from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
  from django.db import models
  from .managers import UserManager

  class User(AbstractBaseUser, PermissionsMixin):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      name = models.CharField(max_length=255, blank=True)
      phone_number = models.CharField(max_length=20, unique=True)
      is_seller = models.BooleanField(default=False)   # admin/seller
      is_active = models.BooleanField(default=True)
      is_staff = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)

      objects = UserManager()
      USERNAME_FIELD = "phone_number"
      REQUIRED_FIELDS = ["name"]

      class Meta:
          db_table = "users"

      def __str__(self):
          return self.phone_number
  ```
- [ ] `apps/users/managers.py` (your existing phone-based manager; add `is_seller` to the superuser defaults):
  ```python
  from django.contrib.auth.base_user import BaseUserManager

  class UserManager(BaseUserManager):
      def create_user(self, phone_number, password=None, **extra):
          if not phone_number:
              raise ValueError("Phone number is required")
          user = self.model(phone_number=phone_number, **extra)
          user.set_password(password)
          user.save(using=self._db)
          return user

      def create_superuser(self, phone_number, password=None, **extra):
          extra.update(is_staff=True, is_superuser=True, is_seller=True)
          return self.create_user(phone_number, password, **extra)
  ```
- [ ] `apps/users/api.py` — register JWT controllers + custom register/me. In `api/v1/router.py`
  switch `NinjaAPI` → `NinjaExtraAPI` (ninja-extra), then:
  ```python
  from ninja_extra import NinjaExtraAPI
  from ninja_jwt.controller import NinjaJWTDefaultController

  api = NinjaExtraAPI(version="1.0.0", title="Boutique API", docs_url="/docs/")
  api.register_controllers(NinjaJWTDefaultController)   # POST /token/pair, /token/refresh, /token/verify
  ```
  The `/token/pair` input field follows `USERNAME_FIELD`, so it takes `phone_number` + `password`.
- [ ] Custom auth endpoints (`apps/users/api.py`), added as a plain router on the api:
  ```python
  from ninja import Router, Schema
  from ninja_jwt.authentication import JWTAuth
  from .models import User

  auth_router = Router(tags=["auth"])

  class RegisterIn(Schema):
      phone_number: str
      password: str
      name: str = ""

  class UserOut(Schema):
      id: str
      phone_number: str
      name: str
      is_seller: bool

  @auth_router.post("/register", response=UserOut)
  def register(request, data: RegisterIn):
      return User.objects.create_user(
          phone_number=data.phone_number, password=data.password, name=data.name,
      )

  @auth_router.get("/me", response=UserOut, auth=JWTAuth())
  def me(request):
      return request.auth   # JWTAuth sets request.auth = User instance
  ```
- [ ] Seller guard used by every admin mutation/read:
  ```python
  from ninja_jwt.authentication import JWTAuth

  class SellerAuth(JWTAuth):
      def authenticate(self, request, token):
          user = super().authenticate(request, token)
          return user if user and user.is_seller else None
  ```
  Use `auth=SellerAuth()` on admin routes; `auth=JWTAuth()` on customer routes (favorites); no `auth` on public.

---

## Phase 2 — Catalog models

`python manage.py startapp catalog`; `apps/catalog/models.py`. Note the **circular FK** between
`ProductImage.option` and `ProductVariantOption.image` — use a string reference and `SET_NULL`.

- [ ] Core:
  ```python
  import uuid
  from django.db import models

  class Category(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      name = models.TextField()
      slug = models.SlugField(unique=True, max_length=255)
      created_at = models.DateTimeField(auto_now_add=True)
      class Meta: db_table = "categories"

  class Product(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      name = models.TextField()
      slug = models.SlugField(unique=True, max_length=255)
      description = models.TextField(null=True, blank=True)
      price = models.DecimalField(max_digits=10, decimal_places=2)
      category = models.ForeignKey(
          Category, null=True, blank=True, on_delete=models.PROTECT,   # blocks deleting a used category
          related_name="products", db_column="category_id",
      )
      visible = models.BooleanField(default=True)
      featured = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)
      class Meta: db_table = "products"
  ```
- [ ] Images + variants (circular FK):
  ```python
  class ProductImage(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", db_column="product_id")
      url = models.TextField()
      alt = models.TextField(null=True, blank=True)
      position = models.IntegerField(default=0)
      option = models.ForeignKey(
          "ProductVariantOption", null=True, blank=True, on_delete=models.SET_NULL,
          related_name="option_images", db_column="option_id",
      )
      class Meta: db_table = "product_images"

  class ProductVariantGroup(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variant_groups", db_column="product_id")
      name = models.TextField()
      position = models.IntegerField(default=0)
      class Meta: db_table = "product_variant_groups"

  class ProductVariantOption(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      group = models.ForeignKey(ProductVariantGroup, on_delete=models.CASCADE, related_name="options", db_column="group_id")
      value = models.TextField()
      position = models.IntegerField(default=0)
      image = models.ForeignKey(
          ProductImage, null=True, blank=True, on_delete=models.SET_NULL,
          related_name="+", db_column="image_id",
      )
      hex = models.TextField(null=True, blank=True)
      class Meta: db_table = "product_variant_options"
  ```
- [ ] Filters + home strip:
  ```python
  class CategoryFilter(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="filters", db_column="category_id")
      name = models.TextField()
      position = models.IntegerField(default=0)
      class Meta: db_table = "category_filters"

  class CategoryFilterOption(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      filter = models.ForeignKey(CategoryFilter, on_delete=models.CASCADE, related_name="options", db_column="filter_id")
      value = models.TextField()
      position = models.IntegerField(default=0)
      class Meta: db_table = "category_filter_options"

  class ProductFilterValue(models.Model):
      pk = models.CompositePrimaryKey("product", "option")   # Django 5.2+/6.0
      product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
      option = models.ForeignKey(CategoryFilterOption, on_delete=models.CASCADE, db_column="option_id")
      class Meta: db_table = "product_filter_values"

  class HomeFilter(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      label = models.TextField()
      href = models.TextField()
      position = models.IntegerField(default=0)
      visible = models.BooleanField(default=True)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)
      class Meta: db_table = "home_filters"
  ```
  > `CompositePrimaryKey` fallback if the version balks: give the model a normal `id` and add
  > `class Meta: constraints = [models.UniqueConstraint(fields=["product", "option"], name="uniq_pfv")]`.

---

## Phase 3 — Orders & Favorites models

- [ ] `apps/orders/models.py` (drop `created_by`; keep snapshot columns so a line renders after the product changes):
  ```python
  import uuid
  from django.db import models
  from apps.catalog.models import Product

  class Order(models.Model):
      class Status(models.TextChoices):
          NEW = "new", "New"
          CONTACTED = "contacted", "Contacted"
          DONE = "done", "Done"
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      guest_name = models.TextField()
      phone = models.TextField()
      address = models.TextField()
      note = models.TextField(null=True, blank=True)
      status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
      created_at = models.DateTimeField(auto_now_add=True)
      class Meta: db_table = "orders"

  class OrderItem(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", db_column="order_id")
      product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, db_column="product_id")
      position = models.IntegerField(default=0)
      name_snapshot = models.TextField()
      color_value = models.TextField(null=True, blank=True)
      size_value = models.TextField(null=True, blank=True)
      quantity = models.IntegerField(default=1)
      price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
      image_url_snapshot = models.TextField(null=True, blank=True)
      class Meta: db_table = "order_items"
  ```
- [ ] `apps/favorites/models.py`:
  ```python
  from django.conf import settings
  from django.db import models
  from apps.catalog.models import Product

  class Favorite(models.Model):
      pk = models.CompositePrimaryKey("user", "product")
      user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column="user_id")
      product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
      created_at = models.DateTimeField(auto_now_add=True)
      class Meta: db_table = "favorites"
  ```

---

## Phase 4 — Fresh migrations onto Neon

- [ ] `python manage.py makemigrations users catalog orders favorites`
- [ ] Inspect the generated SQL once: `python manage.py sqlmigrate catalog 0001` (confirm circular FK and
      composite PK come out right).
- [ ] `python manage.py migrate` (runs against Neon via `DATABASE_URL`).
- [ ] Seed the seller: `python manage.py createsuperuser` (sets `is_seller=True` via `create_superuser`).
- [ ] Sanity: `python manage.py dbshell` → `\dt` shows `users`, `products`, `orders`, etc.

---

## Phase 5 — Ninja schemas (response shapes)

Mirror what the frontend currently reads from Drizzle so the later frontend simplification is a straight swap.
Put these in each app's `schemas.py`. Prefer `ModelSchema` for flat rows, `Schema` for nested/computed.

- [ ] Flat example:
  ```python
  from ninja import ModelSchema
  from apps.catalog.models import Category

  class CategoryOut(ModelSchema):
      class Meta:
          model = Category
          fields = ["id", "name", "slug"]
  ```
- [ ] Nested product (PDP / admin detail):
  ```python
  from ninja import Schema
  from decimal import Decimal

  class ImageOut(Schema):
      id: str
      url: str
      alt: str | None = None
      position: int
      option_id: str | None = None

  class VariantOptionOut(Schema):
      id: str
      value: str
      position: int
      hex: str | None = None
      image_id: str | None = None

  class VariantGroupOut(Schema):
      id: str
      name: str
      position: int
      options: list[VariantOptionOut]

  class ProductDetailOut(Schema):
      id: str
      name: str
      slug: str
      description: str | None = None
      price: Decimal          # see note below
      category_id: str | None = None
      visible: bool
      featured: bool
      images: list[ImageOut]
      variant_groups: list[VariantGroupOut]
  ```
  > **Price serialization:** Drizzle returned `numeric` as a **string**. Pydantic v2 emits `Decimal` as a JSON
  > number. Either (a) let the frontend accept a number (it's being rewritten anyway), or (b) type `price` as
  > `str` in the schema and coerce. Pick one and be consistent across list + detail schemas.

---

## Phase 6 — Read endpoints

Split by authorization scope, exactly like the old `*-queries.ts` (storefront filters `visible=True`, admin does
not). Put query logic in `apps/<app>/selectors.py`, HTTP wiring in `apps/<app>/api.py`.

- [ ] Storefront (public, no auth):
  - `GET /storefront/products/` — visible feed; featured first, then newest. Supports `?category=<slug>` and
    filter query params. Prefetch images + variant groups/options.
  - `GET /storefront/products/{slug}/` — full PDP detail.
  - `GET /storefront/categories/` — visible category index.
  - `GET /storefront/home-filters/` — visible rows by position; fall back to categories when empty.
- [ ] Admin (`auth=SellerAuth()`):
  - `GET /products/` — full list incl. hidden; `GET /products/{id}/` — detail.
  - `GET /categories/` — list with filter/option children.
  - `GET /orders/` — inbox list (+ `new` count for the badge).
  - `GET /overview/stats/` — product count, category count, order counts (chat count omitted — GetStream).
- [ ] Customer (`auth=JWTAuth()`):
  - `GET /storefront/favorites/` — favorited product ids.
  - `GET /storefront/favorites/products/` — full card data.
- [ ] Bag utilities (public POST):
  - `POST /storefront/bag/availability/` — ids in → still-visible subset out.
  - `POST /storefront/bag/suggestions/` — bag ids in → same-category suggestion cards out.
- [ ] Selector example with prefetch:
  ```python
  def get_product_by_slug(slug: str):
      return (
          Product.objects
          .filter(slug=slug, visible=True)
          .prefetch_related("images", "variant_groups__options")
          .first()
      )
  ```

---

## Phase 7 — Write endpoints (mutations)

All admin mutations take `auth=SellerAuth()`. Order placement is public. Favorites take `auth=JWTAuth()`.
Wrap multi-row writes in `transaction.atomic()`.

- [ ] Categories: `POST /categories/`, `PUT /categories/{id}/`, `DELETE /categories/{id}/` (PROTECT surfaces a
      clean 409 when products exist), filter + option CRUD, reorder.
- [ ] Products: `POST /products/`, `POST /products/full/` (product + images + variants in one atomic call),
      `PUT /products/{id}/`, `DELETE /products/{id}/`, `PATCH /products/{id}/visibility/`,
      `PATCH /products/{id}/featured/`, `POST /products/bulk/`.
- [ ] Variants: group create/delete/reorder, option create/delete, `PATCH` option image + hex.
- [ ] Product images: `PUT /products/images/reorder/`, `PATCH /products/images/{id}/option/`
      (upload/delete in Phase 8).
- [ ] Product filter values: `POST /products/{id}/filter-values/` (set/unset an option for a product).
- [ ] Home filters: `PUT /merchandising/home-filters/` — replace the whole strip atomically.
- [ ] Orders: `POST /storefront/orders/` (public — creates order + item snapshots),
      `PATCH /orders/{id}/status/` (admin).
- [ ] Favorites: `POST /storefront/favorites/`, `DELETE /storefront/favorites/{product_id}/`.
- [ ] Order create example (snapshotting):
  ```python
  from django.db import transaction

  @router.post("/storefront/orders/", response=OrderOut)
  def place_order(request, data: PlaceOrderIn):
      with transaction.atomic():
          order = Order.objects.create(
              guest_name=data.guest_name, phone=data.phone, address=data.address, note=data.note,
          )
          OrderItem.objects.bulk_create([
              OrderItem(
                  order=order, product_id=i.product_id, position=idx,
                  name_snapshot=i.name, price_snapshot=i.price, quantity=i.quantity,
                  color_value=i.color, size_value=i.size, image_url_snapshot=i.image_url,
              )
              for idx, i in enumerate(data.items)
          ])
      return order
  ```

---

## Phase 8 — R2 image storage

- [ ] `STORAGES` in `settings.py` (Django 6 storage API):
  ```python
  STORAGES = {
      "default": {
          "BACKEND": "storages.backends.s3.S3Storage",
          "OPTIONS": {
              "bucket_name": env("R2_BUCKET"),
              "endpoint_url": env("R2_ENDPOINT"),          # https://ACCOUNT.r2.cloudflarestorage.com
              "access_key": env("R2_ACCESS_KEY_ID"),
              "secret_key": env("R2_SECRET_ACCESS_KEY"),
              "region_name": "auto",
              "custom_domain": env("R2_PUBLIC_HOST"),        # pub-xxxx.r2.dev  → clean public URLs
              "querystring_auth": False,                     # public objects, no signed query string
              "signature_version": "s3v4",
              "addressing_style": "virtual",
          },
      },
      "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
  }
  ```
- [ ] Upload endpoint — mirrors the old `{productId}/{timestamp}-{index}.{ext}` key pattern:
  ```python
  import time
  from pathlib import Path
  from django.core.files.storage import default_storage
  from ninja import File, Router
  from ninja.files import UploadedFile

  @router.post("/{product_id}/images/", auth=SellerAuth(), response=ImageOut)
  def upload_image(request, product_id: uuid.UUID, file: UploadedFile = File(...)):
      product = Product.objects.get(id=product_id)
      ext = Path(file.name).suffix
      key = f"{product_id}/{int(time.time() * 1000)}{ext}"
      saved = default_storage.save(key, file)          # streams to R2
      pos = product.images.count()
      return ProductImage.objects.create(product=product, url=default_storage.url(saved), position=pos)
  ```
- [ ] Delete endpoint — remove from R2 then the row:
  ```python
  @router.delete("/images/{image_id}/", auth=SellerAuth())
  def delete_image(request, image_id: uuid.UUID):
      img = ProductImage.objects.get(id=image_id)
      # public URL → key: strip the R2_PUBLIC_HOST prefix
      key = img.url.split(f"{env('R2_PUBLIC_HOST')}/", 1)[-1]
      default_storage.delete(key)
      img.delete()
      return {"ok": True}
  ```
  > Store the object **key** alongside `url` (or derive reliably) so deletes never depend on brittle URL parsing.

---

## Phase 9 — API assembly & errors

- [ ] `api/v1/router.py`: register every app router under a clear prefix.
  ```python
  from apps.users.api import auth_router
  from apps.catalog.api import router as catalog_router
  from apps.orders.api import router as orders_router
  from apps.favorites.api import router as favorites_router

  api.add_router("/auth/", auth_router)
  api.add_router("/", catalog_router)          # /products, /categories, /storefront/...
  api.add_router("/", orders_router)
  api.add_router("/", favorites_router)
  ```
- [ ] Global exception handlers (consistent JSON errors the frontend can branch on):
  ```python
  from django.db import IntegrityError
  from ninja_extra import exceptions

  @api.exception_handler(Product.DoesNotExist)   # and others
  def not_found(request, exc):
      return api.create_response(request, {"detail": "Not found"}, status=404)

  @api.exception_handler(IntegrityError)
  def conflict(request, exc):
      return api.create_response(request, {"detail": "Conflict"}, status=409)
  ```
- [ ] Confirm CORS: preflight from `http://localhost:3000` succeeds on a protected route with `Authorization`.

---

## Phase 10 — Verify (drive the real API, not just unit tests)

- [ ] `python manage.py runserver` → open `/api/v1/docs/`; every router shows up.
- [ ] Auth round-trip:
  ```bash
  # get tokens
  curl -X POST localhost:8000/api/v1/token/pair -H 'content-type: application/json' \
    -d '{"phone_number":"+250788000000","password":"..."}'
  # call a protected admin read
  curl localhost:8000/api/v1/products/ -H "Authorization: Bearer <access>"
  ```
- [ ] Smoke the critical paths unmocked: register customer → login → favorite a product; create product with an
      image upload (lands in R2, public URL resolves) → toggle visibility → delete; place a guest order → move
      status `new → contacted → done`; storefront feed returns only `visible=True`.
- [ ] Confirm an uploaded image URL opens in a browser and a deleted one 404s in R2.

---

## Open items to resolve while building

- **Price as string vs number** (Phase 5) — decide once, apply to all product schemas.
- **`CompositePrimaryKey` support** on the installed Django — fall back to `UniqueConstraint` + surrogate id if needed.
- **Slug generation** — old code slugified on the client (`shared/lib/slug`). Decide whether the API slugifies
  server-side on create or trusts a supplied slug.
- **Pagination** — the admin product/order lists used client tables; add Ninja pagination (`paginate`) if lists grow.
