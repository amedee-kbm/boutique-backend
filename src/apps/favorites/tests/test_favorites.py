"""Tests for account-gated favorites: add, list, remove, and store scoping."""

import typing as t

import pytest
from django.test import Client

from apps.boutiques.models import Boutique
from apps.favorites.models import Favorite
from apps.products.models import Category, Product, ProductImage
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
MakeUser = t.Callable[..., User]

FAVORITES = "/api/v1/stores/zita/favorites"


def make_product(store: Boutique, *, slug: str = "gown", visible: bool = True) -> Product:
    category, _ = Category.objects.get_or_create(store=store, slug="dresses", defaults={"name": "Dresses"})
    product = Product.objects.create(
        store=store, category=category, name="Gown", slug=slug, price=30000, is_visible=visible
    )
    ProductImage.objects.create(store=store, product=product, url="https://cdn.example/x.jpg", position=0)
    return product


def test_favorites_require_authentication(client: Client, boutique: Boutique) -> None:
    assert client.get(FAVORITES).status_code == 401


def test_add_then_list_a_favorite(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = make_product(boutique)

    added = client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))
    assert added.status_code == 201
    assert added.json()["slug"] == "gown"

    listed = client.get(FAVORITES, headers=bearer(customer)).json()
    assert [p["slug"] for p in listed] == ["gown"]


def test_favoriting_is_idempotent(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = make_product(boutique)
    client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))
    client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))
    assert Favorite.objects.filter(customer=customer, product=product).count() == 1


def test_remove_a_favorite(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = make_product(boutique)
    client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))

    removed = client.delete(f"{FAVORITES}/{product.id}", headers=bearer(customer))
    assert removed.status_code == 204
    assert client.get(FAVORITES, headers=bearer(customer)).json() == []
    # Idempotent: removing again is still a 204.
    assert client.delete(f"{FAVORITES}/{product.id}", headers=bearer(customer)).status_code == 204


def test_favoriting_a_hidden_product_is_404(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = make_product(boutique, visible=False)
    assert client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer)).status_code == 404


def test_a_customers_favorites_are_their_own(
    client: Client, boutique: Boutique, customer: User, make_user: MakeUser, bearer: Bearer
) -> None:
    product = make_product(boutique)
    client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))
    stranger = make_user(email="c2@example.com", phone_number="+250788222333", name="C2")
    assert client.get(FAVORITES, headers=bearer(stranger)).json() == []


def test_favorites_are_scoped_to_the_store(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = make_product(boutique)
    client.post(f"{FAVORITES}/{product.id}", headers=bearer(customer))

    Boutique.objects.create(slug="other", name="Other")
    assert client.get("/api/v1/stores/other/favorites", headers=bearer(customer)).json() == []
