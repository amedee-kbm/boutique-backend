import uuid

from django.conf import settings
from django.db import models


class Favorite(models.Model):
    """A customer keeping a product across sessions. Account-gated; scoped to a store."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="favorites", db_column="store_id"
    )
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["customer", "store", "product"], name="uniq_favorite"),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id} ♥ {self.product_id}"
