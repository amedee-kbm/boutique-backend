import typing as t
from uuid import UUID

from ninja_extra import api_controller, http_get, http_patch
from ninja_jwt.authentication import JWTAuth
from pydantic import AwareDatetime

from apps.boutiques.controllers.base import TenantScopedController
from apps.orders import selectors, services
from apps.orders.models import Order
from apps.orders.schemas import OrderListItemSchema, OrderSchema, OrderStatusUpdateSchema


@api_controller("/stores/{slug}/admin/orders", auth=JWTAuth(), tags=["Orders Admin"])
class OrdersAdminController(TenantScopedController):
    """The seller's Orders inbox for one boutique.

    Requires the ``work_orders`` capability (operational — owner and staff both).
    The inbox is poll-based: realtime is gone, so a client asks for orders newer
    than the last it saw via ``since``.
    """

    @http_get("", response=list[OrderListItemSchema])
    def inbox(self, slug: str, since: AwareDatetime | None = None, status: Order.Status | None = None) -> t.Any:
        """Every order at the store, newest first; filter by status or a since cursor."""
        membership = self.require_membership(slug, "work_orders")
        return selectors.inbox(membership.boutique, since=since, status=status)

    @http_get("/{order_id}", response=OrderSchema)
    def detail(self, slug: str, order_id: UUID) -> Order:
        """One order in full, or 404."""
        membership = self.require_membership(slug, "work_orders")
        return selectors.store_order(membership.boutique, order_id)

    @http_patch("/{order_id}", response=OrderSchema)
    def set_status(self, slug: str, order_id: UUID, payload: OrderStatusUpdateSchema) -> Order:
        """Move an order along: new → confirmed → fulfilled, or cancelled."""
        membership = self.require_membership(slug, "work_orders")
        return services.set_status(membership.boutique, order_id, payload.status)
