"""Tests for the public storefront: listing, filtering, faceting, and detail."""

import typing as t

import pytest
from django.test import Client

from apps.boutiques.models import Boutique
from apps.products.models import Category, Product, ProductImage, VariantGroup, VariantOption

pytestmark = pytest.mark.django_db

CATALOG = "/api/v1/stores/zita/catalog"


def make_product(
    store: Boutique,
    *,
    category: Category,
    name: str,
    slug: str,
    price: int,
    visible: bool = True,
    featured: bool = False,
    colours: t.Sequence[tuple[str, str]] = (),
    sizes: t.Sequence[str] = (),
    images: t.Sequence[str] = (),
) -> Product:
    product = Product.objects.create(
        store=store, category=category, name=name, slug=slug, price=price, is_visible=visible, is_featured=featured
    )
    for i, url in enumerate(images):
        ProductImage.objects.create(store=store, product=product, url=url, position=i)
    if colours:
        group = VariantGroup.objects.create(store=store, product=product, name="Colour", position=0)
        for i, (value, hexcode) in enumerate(colours):
            VariantOption.objects.create(store=store, group=group, value=value, hex=hexcode, position=i)
    if sizes:
        group = VariantGroup.objects.create(store=store, product=product, name="Size", position=1)
        for i, value in enumerate(sizes):
            VariantOption.objects.create(store=store, group=group, value=value, position=i)
    return product


@pytest.fixture
def catalog(boutique: Boutique) -> dict[str, Category]:
    dresses = Category.objects.create(store=boutique, name="Dresses", slug="dresses", position=0)
    shoes = Category.objects.create(store=boutique, name="Shoes", slug="shoes", position=1)
    make_product(
        boutique,
        category=dresses,
        name="Satin Gown",
        slug="satin-gown",
        price=35000,
        featured=True,
        colours=[("Beige", "#E3D5B8"), ("Red", "#C0392B")],
        sizes=["S", "M"],
        images=["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"],
    )
    make_product(
        boutique,
        category=dresses,
        name="Linen Dress",
        slug="linen-dress",
        price=20000,
        colours=[("Red", "#C0392B")],
        sizes=["L"],
    )
    make_product(boutique, category=shoes, name="Heels", slug="heels", price=50000, colours=[("Beige", "#E3D5B8")])
    make_product(boutique, category=dresses, name="Hidden Piece", slug="hidden", price=99000, visible=False)
    return {"dresses": dresses, "shoes": shoes}


# ─── Categories ──────────────────────────────────────────────────────────────


def test_categories_index_counts_only_visible_and_carries_a_cover(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/categories").json()
    by_slug = {c["slug"]: c for c in body}

    assert by_slug["dresses"]["product_count"] == 2  # the hidden piece is not counted
    assert by_slug["shoes"]["product_count"] == 1
    assert by_slug["dresses"]["cover_image_url"] == "https://cdn.example/1.jpg"  # featured product's first image


# ─── Listing, filtering, sorting, pagination ─────────────────────────────────


def test_products_lists_visible_only(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products").json()
    assert body["count"] == 3
    assert "hidden" not in {item["slug"] for item in body["items"]}


def test_products_filter_by_category(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products", {"category": "shoes"}).json()
    assert {item["slug"] for item in body["items"]} == {"heels"}


def test_products_filter_by_colour(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products", {"colour": "Beige"}).json()
    assert {item["slug"] for item in body["items"]} == {"satin-gown", "heels"}


def test_products_filter_across_axes_is_and(client: Client, catalog: dict[str, Category]) -> None:
    """Red AND size M matches only the gown, not the L-only Red dress."""
    body = client.get(f"{CATALOG}/products", {"colour": "Red", "size": "M"}).json()
    assert {item["slug"] for item in body["items"]} == {"satin-gown"}


def test_products_filter_by_price_range(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products", {"price_min": 30000, "price_max": 60000}).json()
    assert {item["slug"] for item in body["items"]} == {"satin-gown", "heels"}


def test_products_sort_by_price_ascending(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products", {"sort": "price_asc"}).json()
    assert [item["price"] for item in body["items"]] == [20000, 35000, 50000]


def test_products_paginate_reports_total_count(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products", {"limit": 2, "offset": 0}).json()
    assert body["count"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


# ─── Facets ──────────────────────────────────────────────────────────────────


def test_facets_report_count_price_and_axes(client: Client, catalog: dict[str, Category]) -> None:
    facets = client.get(f"{CATALOG}/facets").json()

    assert facets["count"] == 3
    assert facets["price_min"] == 20000
    assert facets["price_max"] == 50000
    assert {c["slug"]: c["count"] for c in facets["categories"]} == {"dresses": 2, "shoes": 1}
    colours = {c["value"]: c for c in facets["colours"]}
    assert colours["Beige"]["count"] == 2
    assert colours["Beige"]["hex"] == "#E3D5B8"
    assert {s["value"] for s in facets["sizes"]} == {"S", "M", "L"}


def test_facets_dedupe_a_colour_with_inconsistent_hex(client: Client, boutique: Boutique) -> None:
    """Same colour value, different (or blank) hex across products, is one facet entry."""
    dresses = Category.objects.create(store=boutique, name="Dresses", slug="dresses")
    make_product(boutique, category=dresses, name="A", slug="a", price=10000, colours=[("Red", "#FF0000")])
    make_product(boutique, category=dresses, name="B", slug="b", price=12000, colours=[("Red", "")])

    reds = [c for c in client.get(f"{CATALOG}/facets").json()["colours"] if c["value"] == "Red"]
    assert len(reds) == 1
    assert reds[0]["count"] == 2


def test_facets_narrow_with_the_active_filter(client: Client, catalog: dict[str, Category]) -> None:
    facets = client.get(f"{CATALOG}/facets", {"category": "shoes"}).json()
    assert facets["count"] == 1
    assert {c["value"] for c in facets["colours"]} == {"Beige"}


# ─── Detail ──────────────────────────────────────────────────────────────────


def test_product_detail_includes_images_and_variants(client: Client, catalog: dict[str, Category]) -> None:
    body = client.get(f"{CATALOG}/products/satin-gown").json()

    assert body["name"] == "Satin Gown"
    assert body["category"]["slug"] == "dresses"
    assert [img["url"] for img in body["images"]] == ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"]
    groups = {g["name"]: [o["value"] for o in g["options"]] for g in body["variant_groups"]}
    assert groups == {"Colour": ["Beige", "Red"], "Size": ["S", "M"]}


def test_product_detail_hidden_is_404(client: Client, catalog: dict[str, Category]) -> None:
    assert client.get(f"{CATALOG}/products/hidden").status_code == 404


def test_product_detail_unknown_store_is_404(client: Client, catalog: dict[str, Category]) -> None:
    assert client.get("/api/v1/stores/ghost/catalog/products/satin-gown").status_code == 404


# ─── Tenant isolation ────────────────────────────────────────────────────────


def test_catalog_does_not_leak_across_stores(client: Client, catalog: dict[str, Category]) -> None:
    other = Boutique.objects.create(slug="other", name="Other Shop")
    cat = Category.objects.create(store=other, name="Bags", slug="bags")
    make_product(other, category=cat, name="Tote", slug="tote", price=15000)

    zita = client.get(f"{CATALOG}/products").json()
    assert "tote" not in {item["slug"] for item in zita["items"]}

    other_list = client.get("/api/v1/stores/other/catalog/products").json()
    assert {item["slug"] for item in other_list["items"]} == {"tote"}
