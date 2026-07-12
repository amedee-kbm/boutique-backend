"""The single Django-owned web-push pipe: subscribe, and send order-status / new-arrivals.

Sends are synchronous — the volume is low and the queue is dormant (ADR-0012).
A push to a browser that has dropped its subscription prunes the dead row.
"""

import json
import logging
import typing as t
from uuid import UUID

from django.conf import settings
from pywebpush import WebPushException, webpush

from apps.boutiques.models import Boutique
from apps.push.models import PushSubscription
from apps.users.models import User

logger = logging.getLogger(__name__)


def subscribe(store: Boutique, user: User, *, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
    """Register (or refresh) a browser's push subscription for a store."""
    subscription, _ = PushSubscription.objects.update_or_create(
        store=store, endpoint=endpoint, defaults={"user": user, "p256dh": p256dh, "auth": auth}
    )
    return subscription


def unsubscribe(store: Boutique, user: User, endpoint: str) -> None:
    """Drop a browser's push subscription. Idempotent."""
    PushSubscription.objects.filter(store=store, user=user, endpoint=endpoint).delete()


def _send(subscription: PushSubscription, payload: dict[str, t.Any]) -> None:
    """Deliver one push; prune the subscription if the browser has dropped it."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):  # Not Found / Gone — the subscription is dead.
            subscription.delete()
        else:
            logger.warning("web-push failed for subscription %s: %r", subscription.pk, exc)


def notify_order_status(store: Boutique, customer: User, *, order_id: UUID, status: str) -> None:
    """Targeted push to a customer when their order moves along."""
    payload = {"type": "order_status", "store": store.slug, "order_id": str(order_id), "status": status}
    for subscription in list(PushSubscription.objects.filter(store=store, user=customer)):
        _send(subscription, payload)


def broadcast_new_arrival(store: Boutique, *, product_id: UUID, name: str, image_url: str) -> None:
    """Per-store broadcast when a new piece is announced."""
    payload = {
        "type": "new_arrival",
        "store": store.slug,
        "product_id": str(product_id),
        "name": name,
        "image_url": image_url,
    }
    for subscription in list(PushSubscription.objects.filter(store=store)):
        _send(subscription, payload)
