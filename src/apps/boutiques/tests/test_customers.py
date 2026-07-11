"""Tests for the customer-visibility guardrail: per-store activity, never the global table."""

import typing as t

import pytest
from django.test import Client

from apps.boutiques.models import Boutique
from apps.favorites.models import Favorite
from apps.orders.models import Order
from apps.products.models import Category, Product
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
MakeUser = t.Callable[..., User]

CUSTOMERS = "/api/v1/stores/zita/admin/customers"


def _product(store: Boutique, slug: str = "gown") -> Product:
    category, _ = Category.objects.get_or_create(store=store, slug="dresses", defaults={"name": "Dresses"})
    return Product.objects.create(store=store, category=category, name="Gown", slug=slug, price=30000)


def test_customers_requires_membership(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    assert client.get(CUSTOMERS).status_code == 401
    assert client.get(CUSTOMERS, headers=bearer(customer)).status_code == 403


def test_admin_sees_only_customers_with_activity_in_this_store(
    client: Client, boutique: Boutique, seller: User, make_user: MakeUser, bearer: Bearer
) -> None:
    buyer = make_user(email="buyer@example.com", phone_number="+250788111111", name="Buyer")
    favoriter = make_user(email="fav@example.com", phone_number="+250788222222", name="Favoriter")
    # A user who exists globally but has no activity in this store.
    make_user(email="stranger@example.com", phone_number="+250788333333", name="Stranger")
    # A user active only at another store.
    other = Boutique.objects.create(slug="other", name="Other")
    elsewhere = make_user(email="elsewhere@example.com", phone_number="+250788444444", name="Elsewhere")
    Favorite.objects.create(customer=elsewhere, store=other, product=_product(other, slug="tote"))

    Order.objects.create(
        store=boutique,
        customer=buyer,
        idempotency_key="k",
        contact_name="Buyer",
        phone="+250788111111",
        delivery_address="Kigali",
    )
    Favorite.objects.create(customer=favoriter, store=boutique, product=_product(boutique))

    body = client.get(CUSTOMERS, headers=bearer(seller)).json()
    by_email = {c["email"]: c for c in body}

    assert set(by_email) == {"buyer@example.com", "fav@example.com"}
    assert by_email["buyer@example.com"]["order_count"] == 1
    assert by_email["buyer@example.com"]["favorite_count"] == 0
    assert by_email["fav@example.com"]["favorite_count"] == 1
