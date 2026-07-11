import typing as t
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from apps.boutiques.models import Boutique
from apps.orders import selectors, services
from apps.orders.models import Order
from apps.orders.schemas import OrderCreateSchema, OrderListItemSchema, OrderSchema
from apps.users.models import User


@api_controller("/stores/{slug}/orders", auth=JWTAuth(), tags=["Orders"])
class OrdersController(ControllerBase):
    """The customer's own orders at one boutique.

    Authenticated, but not membership-scoped: any signed-in customer may order
    from any store and see only their own orders there. Placing an order is the
    one write; there is no guest order endpoint.
    """

    def _store(self, slug: str) -> Boutique:
        return get_object_or_404(Boutique, slug=slug)

    def _customer(self) -> User:
        return t.cast(User, getattr(self.context.request, "auth", None))  # type: ignore[union-attr]

    @http_post("", response={200: OrderSchema, 201: OrderSchema})
    def place(self, slug: str, payload: OrderCreateSchema) -> Status[Order]:
        """Place an order. A repeated idempotency key returns the first order (200)."""
        order, created = services.place_order(self._store(slug), self._customer(), payload)
        return Status(201 if created else 200, order)

    @http_get("", response=list[OrderListItemSchema])
    def my_orders(self, slug: str) -> t.Any:
        """The customer's order history at this store, newest first."""
        return selectors.customer_orders(self._store(slug), self._customer())

    @http_get("/{order_id}", response=OrderSchema)
    def detail(self, slug: str, order_id: UUID) -> Order:
        """One of the customer's own orders, or 404."""
        return selectors.customer_order(self._store(slug), self._customer(), order_id)
