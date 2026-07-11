"""Tests for the seller catalog surface: create, update, delete, and image upload."""

import json
import typing as t

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from apps.boutiques.models import Boutique
from apps.products.models import Category, Product
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
PostJson = t.Callable[..., t.Any]

ADMIN = "/api/v1/stores/zita/admin/catalog"

MEMORY_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "product_images": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
        "OPTIONS": {"base_url": "http://testserver/media/"},
    },
}


@pytest.fixture
def dresses(boutique: Boutique) -> Category:
    return Category.objects.create(store=boutique, name="Dresses", slug="dresses")


def _product_payload(**overrides: t.Any) -> dict[str, t.Any]:
    payload: dict[str, t.Any] = {
        "category_slug": "dresses",
        "name": "New Gown",
        "description": "A gown.",
        "price": 40000,
        "is_featured": True,
        "images": [{"url": "https://cdn.example/x.jpg", "alt": "front", "position": 0}],
        "variant_groups": [
            {"name": "Colour", "position": 0, "options": [{"value": "Red", "hex": "#C0392B", "position": 0}]}
        ],
    }
    payload.update(overrides)
    return payload


# ─── Authorization ───────────────────────────────────────────────────────────


def test_anonymous_cannot_manage_catalog(client: Client, post_json: PostJson) -> None:
    assert post_json(client, "/stores/zita/admin/catalog/categories", {"name": "X"}).status_code == 401


def test_customer_cannot_manage_catalog(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    r = client.post(f"{ADMIN}/categories", json.dumps({"name": "X"}), "application/json", headers=bearer(customer))
    assert r.status_code == 403


def test_staff_can_manage_catalog(client: Client, staff: User, bearer: Bearer) -> None:
    """manage_catalog is operational, so staff — not only the owner — may write."""
    r = client.post(f"{ADMIN}/categories", json.dumps({"name": "Shoes"}), "application/json", headers=bearer(staff))
    assert r.status_code == 201
    assert r.json()["slug"] == "shoes"


def test_manage_catalog_on_unknown_store_is_404(client: Client, seller: User, bearer: Bearer) -> None:
    r = client.post(
        "/api/v1/stores/ghost/admin/catalog/categories",
        json.dumps({"name": "X"}),
        "application/json",
        headers=bearer(seller),
    )
    assert r.status_code == 404


# ─── Create ──────────────────────────────────────────────────────────────────


def test_create_product_persists_images_and_variants(
    client: Client, dresses: Category, seller: User, bearer: Bearer
) -> None:
    r = client.post(f"{ADMIN}/products", json.dumps(_product_payload()), "application/json", headers=bearer(seller))

    assert r.status_code == 201, r.content
    body = r.json()
    assert body["price"] == 40000
    assert [img["url"] for img in body["images"]] == ["https://cdn.example/x.jpg"]
    assert body["variant_groups"][0]["options"][0]["value"] == "Red"

    # Persisted and visible on the storefront.
    detail = client.get(f"/api/v1/stores/zita/catalog/products/{body['slug']}")
    assert detail.status_code == 200


def test_create_product_generates_a_unique_slug(
    client: Client, dresses: Category, seller: User, bearer: Bearer
) -> None:
    first = client.post(f"{ADMIN}/products", json.dumps(_product_payload()), "application/json", headers=bearer(seller))
    second = client.post(
        f"{ADMIN}/products", json.dumps(_product_payload()), "application/json", headers=bearer(seller)
    )

    assert first.json()["slug"] == "new-gown"
    assert second.json()["slug"] == "new-gown-2"


def test_create_product_unknown_category_is_404(client: Client, seller: User, bearer: Bearer) -> None:
    payload = _product_payload(category_slug="nope")
    r = client.post(f"{ADMIN}/products", json.dumps(payload), "application/json", headers=bearer(seller))
    assert r.status_code == 404


# ─── Update & delete ─────────────────────────────────────────────────────────


def test_update_product_changes_only_supplied_fields(
    client: Client, dresses: Category, boutique: Boutique, seller: User, bearer: Bearer
) -> None:
    product = Product.objects.create(store=boutique, category=dresses, name="Gown", slug="gown", price=30000)

    r = client.patch(
        f"{ADMIN}/products/{product.id}",
        json.dumps({"price": 25000, "is_visible": False}),
        "application/json",
        headers=bearer(seller),
    )

    assert r.status_code == 200
    product.refresh_from_db()
    assert product.price == 25000 and product.is_visible is False
    assert product.name == "Gown"  # untouched


def test_delete_product_removes_it(
    client: Client, dresses: Category, boutique: Boutique, seller: User, bearer: Bearer
) -> None:
    product = Product.objects.create(store=boutique, category=dresses, name="Gown", slug="gown", price=30000)

    r = client.delete(f"{ADMIN}/products/{product.id}", headers=bearer(seller))

    assert r.status_code == 204
    assert not Product.objects.filter(id=product.id).exists()


def test_cannot_touch_a_product_in_another_store(
    client: Client, dresses: Category, seller: User, bearer: Bearer
) -> None:
    """A product id belonging to another boutique is a 404, not someone else's to edit."""
    other = Boutique.objects.create(slug="other", name="Other")
    other_cat = Category.objects.create(store=other, name="Bags", slug="bags")
    foreign = Product.objects.create(store=other, category=other_cat, name="Tote", slug="tote", price=15000)

    r = client.delete(f"{ADMIN}/products/{foreign.id}", headers=bearer(seller))
    assert r.status_code == 404
    assert Product.objects.filter(id=foreign.id).exists()


# ─── Image upload ────────────────────────────────────────────────────────────


@override_settings(STORAGES=MEMORY_STORAGES)
def test_upload_image_returns_a_public_url(client: Client, seller: User, bearer: Bearer) -> None:
    upload = SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff\xe0jpegbytes", content_type="image/jpeg")

    r = client.post(f"{ADMIN}/images", {"file": upload}, headers=bearer(seller))

    assert r.status_code == 201, r.content
    url = r.json()["url"]
    assert url.startswith("http://testserver/media/stores/zita/products/")
    assert url.endswith(".jpg")
