"""Tests for order placement, idempotency, server pricing, and the seller inbox."""

import typing as t

import pytest
from django.test import Client

from apps.boutiques.models import Boutique
from apps.orders.models import Order
from apps.products.models import Category, Product, ProductImage, VariantGroup, VariantOption
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
PostJson = t.Callable[..., t.Any]
MakeUser = t.Callable[..., User]

ORDERS = "/api/v1/stores/zita/orders"
INBOX = "/api/v1/stores/zita/admin/orders"


def make_product(
    store: Boutique, *, name: str = "Gown", slug: str = "gown", price: int = 30000, visible: bool = True
) -> tuple[Product, VariantOption, VariantOption]:
    category, _ = Category.objects.get_or_create(store=store, slug="dresses", defaults={"name": "Dresses"})
    product = Product.objects.create(
        store=store, category=category, name=name, slug=slug, price=price, is_visible=visible
    )
    ProductImage.objects.create(store=store, product=product, url="https://cdn.example/x.jpg", position=0)
    colour = VariantGroup.objects.create(store=store, product=product, name="Colour", position=0)
    red = VariantOption.objects.create(store=store, group=colour, value="Red", hex="#C0392B")
    size = VariantGroup.objects.create(store=store, product=product, name="Size", position=1)
    medium = VariantOption.objects.create(store=store, group=size, value="M")
    return product, red, medium


def order_payload(
    product: Product, options: list[VariantOption], *, key: str = "k1", quantity: int = 2
) -> dict[str, t.Any]:
    return {
        "idempotency_key": key,
        "contact_name": "Aline",
        "phone": "+250788112233",
        "delivery_address": "Kigali, KG 11 Ave",
        "items": [{"product_id": str(product.id), "option_ids": [str(o.id) for o in options], "quantity": quantity}],
    }


# ─── Placement ───────────────────────────────────────────────────────────────


def test_placing_an_order_requires_authentication(client: Client, post_json: PostJson, boutique: Boutique) -> None:
    assert post_json(client, "/stores/zita/orders", {"idempotency_key": "k", "items": []}).status_code == 401


def test_place_order_prices_from_the_server_and_snapshots_options(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique, price=30000)

    r = post_json(
        client, "/stores/zita/orders", order_payload(product, [red, medium], quantity=2), headers=bearer(customer)
    )

    assert r.status_code == 201, r.content
    body = r.json()
    assert body["total"] == 60000  # 30000 × 2, priced by the server
    line = body["items"][0]
    assert line["unit_price"] == 30000
    assert line["line_total"] == 60000
    assert line["options"] == {"Colour": "Red", "Size": "M"}
    assert line["name"] == "Gown"
    assert body["status"] == "new"


def test_idempotency_key_returns_the_first_order(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique)
    payload = order_payload(product, [red, medium], key="same")

    first = post_json(client, "/stores/zita/orders", payload, headers=bearer(customer))
    second = post_json(client, "/stores/zita/orders", payload, headers=bearer(customer))

    assert first.status_code == 201
    assert second.status_code == 200  # replay, not a new order
    assert first.json()["id"] == second.json()["id"]
    assert Order.objects.count() == 1


def test_option_from_another_product_is_rejected(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique, name="Gown", slug="gown")
    _, other_red, _ = make_product(boutique, name="Heels", slug="heels")

    payload = order_payload(product, [other_red], key="x")
    r = post_json(client, "/stores/zita/orders", payload, headers=bearer(customer))
    assert r.status_code == 400


def test_ordering_a_hidden_product_is_404(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique, visible=False)
    r = post_json(client, "/stores/zita/orders", order_payload(product, [red], key="h"), headers=bearer(customer))
    assert r.status_code == 404


def test_an_empty_order_is_rejected(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    payload = {
        "idempotency_key": "e",
        "contact_name": "A",
        "phone": "+250788112233",
        "delivery_address": "X",
        "items": [],
    }
    assert post_json(client, "/stores/zita/orders", payload, headers=bearer(customer)).status_code == 400


# ─── Customer's own history ──────────────────────────────────────────────────


def test_my_orders_shows_only_the_callers_orders(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, make_user: MakeUser, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique)
    post_json(client, "/stores/zita/orders", order_payload(product, [red], key="mine"), headers=bearer(customer))
    stranger = make_user(email="c2@example.com", phone_number="+250788222333", name="C2")

    assert len(client.get(ORDERS, headers=bearer(customer)).json()) == 1
    assert client.get(ORDERS, headers=bearer(stranger)).json() == []


def test_a_customer_cannot_read_another_customers_order(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, make_user: MakeUser, bearer: Bearer
) -> None:
    product, red, medium = make_product(boutique)
    placed = post_json(client, "/stores/zita/orders", order_payload(product, [red], key="o"), headers=bearer(customer))
    stranger = make_user(email="c2@example.com", phone_number="+250788222333", name="C2")

    r = client.get(f"{ORDERS}/{placed.json()['id']}", headers=bearer(stranger))
    assert r.status_code == 404


# ─── Seller inbox ────────────────────────────────────────────────────────────


def _place(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer, key: str = "k1"
) -> str:
    product, red, medium = make_product(boutique)
    r = post_json(
        client, "/stores/zita/orders", order_payload(product, [red, medium], key=key), headers=bearer(customer)
    )
    return t.cast(str, r.json()["id"])


def test_inbox_is_forbidden_to_a_non_member(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    assert client.get(INBOX).status_code == 401
    assert client.get(INBOX, headers=bearer(customer)).status_code == 403


def test_inbox_lists_store_orders_for_staff(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, staff: User, bearer: Bearer
) -> None:
    _place(client, post_json, boutique, customer, bearer)
    body = client.get(INBOX, headers=bearer(staff)).json()
    assert len(body) == 1
    assert body[0]["item_count"] == 1


def test_seller_reads_an_order_in_full(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, staff: User, bearer: Bearer
) -> None:
    order_id = _place(client, post_json, boutique, customer, bearer)
    body = client.get(f"{INBOX}/{order_id}", headers=bearer(staff)).json()
    assert body["contact_name"] == "Aline"
    assert body["items"][0]["options"] == {"Colour": "Red", "Size": "M"}


def test_inbox_filters_by_status(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, seller: User, bearer: Bearer
) -> None:
    _place(client, post_json, boutique, customer, bearer)
    assert len(client.get(INBOX, {"status": "new"}, headers=bearer(seller)).json()) == 1
    assert client.get(INBOX, {"status": "confirmed"}, headers=bearer(seller)).json() == []


def test_inbox_since_cursor_excludes_older_orders(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, seller: User, bearer: Bearer
) -> None:
    _place(client, post_json, boutique, customer, bearer)
    future = client.get(INBOX, {"since": "2099-01-01T00:00:00Z"}, headers=bearer(seller))
    assert future.json() == []


def test_seller_moves_an_order_along(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, seller: User, bearer: Bearer
) -> None:
    order_id = _place(client, post_json, boutique, customer, bearer)

    r = client.patch(f"{INBOX}/{order_id}", '{"status": "confirmed"}', "application/json", headers=bearer(seller))

    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
    assert Order.objects.get(id=order_id).status == Order.Status.CONFIRMED


def test_a_customer_cannot_change_order_status(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    order_id = _place(client, post_json, boutique, customer, bearer)
    r = client.patch(f"{INBOX}/{order_id}", '{"status": "confirmed"}', "application/json", headers=bearer(customer))
    assert r.status_code == 403
