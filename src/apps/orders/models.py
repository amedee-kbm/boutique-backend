import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    """A no-pay, cash-on-delivery order — a lead with item snapshots attached.

    No money moves through the app. The order carries the contact details the
    seller needs to reach the customer and arrange payment and delivery offline.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.PROTECT, related_name="orders", db_column="store_id"
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)

    # Contact snapshot, taken at order time so the lead stands on its own.
    contact_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    note = models.TextField(blank=True)

    total = models.PositiveIntegerField(default=0, help_text="Whole RWF, priced by the server at order time.")
    idempotency_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        constraints = [
            # A customer's double-submit of the same key returns their first order,
            # never a second — and never another customer's.
            models.UniqueConstraint(fields=["store", "customer", "idempotency_key"], name="uniq_order_idempotency"),
        ]

    def __str__(self) -> str:
        return f"{self.contact_name} · {self.status}"


class OrderItem(models.Model):
    """A line on an order, fully snapshotted so it renders after the catalog moves on."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="order_items", db_column="store_id"
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, related_name="+")
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField(help_text="Whole RWF, snapshotted from the product at order time.")
    name_snapshot = models.CharField(max_length=255)
    image_url_snapshot = models.URLField(max_length=500, blank=True)
    # Chosen axis values, e.g. {"Colour": "Red", "Size": "M"}.
    options = models.JSONField(default=dict)

    class Meta:
        db_table = "order_items"

    def __str__(self) -> str:
        return f"{self.quantity}× {self.name_snapshot}"
