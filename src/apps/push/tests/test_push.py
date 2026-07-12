"""Tests for web-push: subscription, targeted order-status, and new-arrival broadcast."""

import json
import typing as t
from types import SimpleNamespace

import pytest
from django.test import Client, override_settings
from pywebpush import WebPushException

from apps.boutiques.models import Boutique
from apps.orders.models import Order
from apps.products.models import Category, Product, ProductImage
from apps.push import services
from apps.push.models import PushSubscription
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
PostJson = t.Callable[..., t.Any]

PUSH = "/api/v1/stores/zita/push"
SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "p256key", "auth": "authkey"}}


class Recorder:
    """Stands in for pywebpush.webpush, capturing each call's kwargs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, t.Any]] = []

    def __call__(self, **kwargs: t.Any) -> None:
        self.calls.append(kwargs)


def _product(store: Boutique) -> Product:
    category, _ = Category.objects.get_or_create(store=store, slug="dresses", defaults={"name": "Dresses"})
    product = Product.objects.create(store=store, category=category, name="Gown", slug="gown", price=30000)
    ProductImage.objects.create(store=store, product=product, url="https://cdn.example/x.jpg", position=0)
    return product


def _subscribe(store: Boutique, user: User, endpoint: str = "https://push.example/abc") -> PushSubscription:
    return services.subscribe(store, user, endpoint=endpoint, p256dh="p256key", auth="authkey")


# ─── The public key & subscription lifecycle ─────────────────────────────────


@override_settings(VAPID_PUBLIC_KEY="pub-key-123")
def test_vapid_public_key_is_public(client: Client, boutique: Boutique) -> None:
    r = client.get(f"{PUSH}/key")
    assert r.status_code == 200
    assert r.json()["vapid_public_key"] == "pub-key-123"


def test_subscribe_requires_authentication(client: Client, post_json: PostJson, boutique: Boutique) -> None:
    assert post_json(client, "/stores/zita/push/subscribe", SUB).status_code == 401


def test_subscribe_then_resubscribe_refreshes_one_row(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    first = post_json(client, "/stores/zita/push/subscribe", SUB, headers=bearer(customer))
    assert first.status_code == 201

    changed = {"endpoint": SUB["endpoint"], "keys": {"p256dh": "new-p256", "auth": "new-auth"}}
    post_json(client, "/stores/zita/push/subscribe", changed, headers=bearer(customer))

    subs = PushSubscription.objects.filter(store=boutique, endpoint=SUB["endpoint"])
    assert subs.count() == 1
    assert subs.get().p256dh == "new-p256"


def test_unsubscribe_removes_the_row(
    client: Client, post_json: PostJson, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    _subscribe(boutique, customer)
    r = post_json(client, "/stores/zita/push/unsubscribe", {"endpoint": SUB["endpoint"]}, headers=bearer(customer))
    assert r.status_code == 204
    assert not PushSubscription.objects.exists()


# ─── Targeted order-status push ──────────────────────────────────────────────


def test_order_status_change_pushes_to_the_subscriber(
    client: Client,
    post_json: PostJson,
    boutique: Boutique,
    customer: User,
    seller: User,
    bearer: Bearer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = Order.objects.create(
        store=boutique,
        customer=customer,
        idempotency_key="k",
        contact_name="Aline",
        phone="+250788112233",
        delivery_address="Kigali",
    )
    _subscribe(boutique, customer)
    recorder = Recorder()
    monkeypatch.setattr("apps.push.services.webpush", recorder)

    r = client.patch(
        f"/api/v1/stores/zita/admin/orders/{order.id}",
        '{"status": "confirmed"}',
        "application/json",
        headers=bearer(seller),
    )

    assert r.status_code == 200
    assert len(recorder.calls) == 1
    payload = json.loads(recorder.calls[0]["data"])
    assert payload["type"] == "order_status"
    assert payload["status"] == "confirmed"
    assert payload["order_id"] == str(order.id)


def test_a_dead_subscription_is_pruned(boutique: Boutique, customer: User, monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = _subscribe(boutique, customer)

    def gone(**kwargs: t.Any) -> None:
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr("apps.push.services.webpush", gone)
    services.notify_order_status(boutique, customer, order_id=subscription.id, status="confirmed")

    assert not PushSubscription.objects.filter(id=subscription.id).exists()


# ─── New-arrival broadcast ───────────────────────────────────────────────────


def test_seller_announces_a_new_arrival(
    client: Client,
    boutique: Boutique,
    customer: User,
    seller: User,
    bearer: Bearer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = _product(boutique)
    _subscribe(boutique, customer)
    recorder = Recorder()
    monkeypatch.setattr("apps.push.services.webpush", recorder)

    r = client.post(f"/api/v1/stores/zita/admin/push/announce/{product.id}", headers=bearer(seller))

    assert r.status_code == 202
    assert len(recorder.calls) == 1
    payload = json.loads(recorder.calls[0]["data"])
    assert payload["type"] == "new_arrival"
    assert payload["name"] == "Gown"


def test_a_customer_cannot_announce(client: Client, boutique: Boutique, customer: User, bearer: Bearer) -> None:
    product = _product(boutique)
    r = client.post(f"/api/v1/stores/zita/admin/push/announce/{product.id}", headers=bearer(customer))
    assert r.status_code == 403
