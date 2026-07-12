import uuid

from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """One browser's web-push registration for a store.

    The single background-push pipe a PWA can have. It carries the customer (for
    targeted order-status pushes) and the store (for per-store new-arrivals
    broadcasts). The endpoint is the browser's push URL; p256dh/auth are the
    keys pywebpush encrypts the payload with.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="push_subscriptions", db_column="store_id"
    )
    endpoint = models.URLField(max_length=500)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "push_subscriptions"
        constraints = [
            # One registration per browser endpoint per store; re-subscribing
            # refreshes the keys rather than piling up rows.
            models.UniqueConstraint(fields=["store", "endpoint"], name="uniq_push_subscription"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.store_id}"
