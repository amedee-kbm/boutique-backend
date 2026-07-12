from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Status
from ninja_extra import api_controller, http_post
from ninja_jwt.authentication import JWTAuth

from apps.boutiques.controllers.base import TenantScopedController
from apps.products.models import Product
from apps.push import services


@api_controller("/stores/{slug}/admin/push", auth=JWTAuth(), tags=["Push Admin"])
class PushAdminController(TenantScopedController):
    """The seller's outbound-push surface: announce a new arrival to the store."""

    @http_post("/announce/{product_id}", response={202: dict})
    def announce(self, slug: str, product_id: UUID) -> Status[dict[str, str]]:
        """Broadcast a new-arrival push for a visible product to the store's subscribers."""
        membership = self.require_membership(slug, "manage_catalog")
        product = get_object_or_404(Product, store=membership.boutique, id=product_id, is_visible=True)
        cover = product.images.first()
        services.broadcast_new_arrival(
            membership.boutique,
            product_id=product.id,
            name=product.name,
            image_url=cover.url if cover else "",
        )
        return Status(202, {"detail": "Announced."})
