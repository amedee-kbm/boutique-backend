from uuid import UUID

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.orders.models import Order, OrderItem


class OrderItemInSchema(Schema):
    product_id: UUID
    option_ids: list[UUID] = []
    quantity: int = Field(ge=1)


class OrderCreateSchema(Schema):
    idempotency_key: str
    contact_name: str
    phone: str
    delivery_address: str
    note: str = ""
    items: list[OrderItemInSchema]


class OrderLineSchema(Schema):
    product_id: UUID | None
    name: str
    unit_price: int
    quantity: int
    options: dict[str, str]
    image_url: str
    line_total: int

    @staticmethod
    def resolve_name(obj: OrderItem) -> str:
        """The product name as it stood when ordered."""
        return obj.name_snapshot

    @staticmethod
    def resolve_image_url(obj: OrderItem) -> str:
        """The image URL snapshotted at order time."""
        return obj.image_url_snapshot

    @staticmethod
    def resolve_line_total(obj: OrderItem) -> int:
        """Unit price times quantity."""
        return obj.unit_price * obj.quantity


class OrderSchema(Schema):
    """A full order, as the customer and the seller both see it."""

    id: UUID
    status: Order.Status
    contact_name: str
    phone: str
    delivery_address: str
    note: str
    total: int
    created_at: AwareDatetime
    items: list[OrderLineSchema]


class OrderListItemSchema(Schema):
    """An order as a row in the seller inbox or the customer's history."""

    id: UUID
    status: Order.Status
    contact_name: str
    total: int
    item_count: int
    created_at: AwareDatetime


class OrderStatusUpdateSchema(Schema):
    status: Order.Status
