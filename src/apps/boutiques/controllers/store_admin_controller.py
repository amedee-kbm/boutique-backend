import typing as t

from ninja_extra import api_controller, http_get
from ninja_jwt.authentication import JWTAuth

from apps.boutiques import selectors, services
from apps.boutiques.controllers.base import TenantScopedController
from apps.boutiques.models import Membership
from apps.boutiques.schemas import BoutiqueRefSchema, MemberSchema, MembershipSchema, StoreCustomerSchema


@api_controller("/stores/{slug}/admin", auth=JWTAuth(), tags=["Store Admin"])
class StoreAdminController(TenantScopedController):
    """Boutique-scoped seller surface.

    JWTAuth authenticates (401); ``require_membership`` scopes to the ``{slug}``
    tenant (404 for no such store, 403 for a non-member or an under-privileged
    one). Catalog, orders and chat admin land under this same prefix and inherit
    the scoping.
    """

    @http_get("/me", response=MembershipSchema)
    def me(self, slug: str) -> MembershipSchema:
        """The caller's standing at this boutique — the store-scoped admin gate."""
        membership = self.require_membership(slug)
        return MembershipSchema(
            store=BoutiqueRefSchema(slug=membership.boutique.slug, name=membership.boutique.name),
            role=Membership.Role(membership.role),
        )

    @http_get("/members", response=list[MemberSchema])
    def members(self, slug: str) -> t.Any:
        """The boutique's members. OWNER only — managing members is governance."""
        membership = self.require_membership(slug, "manage_members")
        return services.members_of(membership.boutique)

    @http_get("/customers", response=list[StoreCustomerSchema])
    def customers(self, slug: str) -> t.Any:
        """Customers with an order or favorite in this store — never the global user table."""
        membership = self.require_membership(slug, "work_orders")
        return selectors.store_customers(membership.boutique)
