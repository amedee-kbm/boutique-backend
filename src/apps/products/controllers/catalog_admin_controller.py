from uuid import UUID

from ninja import File, Status
from ninja.files import UploadedFile
from ninja_extra import api_controller, http_delete, http_patch, http_post
from ninja_jwt.authentication import JWTAuth

from apps.boutiques.controllers.base import TenantScopedController
from apps.products import services
from apps.products.models import Category, Product
from apps.products.schemas import (
    CategoryCreateSchema,
    CategoryRefSchema,
    ImageUploadSchema,
    ProductCreateSchema,
    ProductDetailSchema,
    ProductUpdateSchema,
)


@api_controller("/stores/{slug}/admin/catalog", auth=JWTAuth(), tags=["Catalog Admin"])
class CatalogAdminController(TenantScopedController):
    """The seller's catalog surface for one boutique.

    Every route requires the ``manage_catalog`` capability at ``{slug}``:
    JWTAuth answers 401, the tenant resolution answers 404/403, and the store on
    each object is the caller's own — a product id from another boutique is a 404.
    """

    @http_post("/categories", response={201: CategoryRefSchema})
    def create_category(self, slug: str, payload: CategoryCreateSchema) -> Status[Category]:
        """Create a category."""
        membership = self.require_membership(slug, "manage_catalog")
        return Status(201, services.create_category(membership.boutique, name=payload.name, position=payload.position))

    @http_post("/products", response={201: ProductDetailSchema})
    def create_product(self, slug: str, payload: ProductCreateSchema) -> Status[Product]:
        """Create a product with its images and variant axes, atomically."""
        membership = self.require_membership(slug, "manage_catalog")
        return Status(201, services.create_product(membership.boutique, payload))

    @http_patch("/products/{product_id}", response=ProductDetailSchema)
    def update_product(self, slug: str, product_id: UUID, payload: ProductUpdateSchema) -> Product:
        """Change a product's scalar fields."""
        membership = self.require_membership(slug, "manage_catalog")
        return services.update_product(membership.boutique, product_id, payload)

    @http_delete("/products/{product_id}", response={204: None})
    def delete_product(self, slug: str, product_id: UUID) -> Status[None]:
        """Delete a product and everything hanging off it."""
        membership = self.require_membership(slug, "manage_catalog")
        services.delete_product(membership.boutique, product_id)
        return Status(204, None)

    @http_post("/images", response={201: ImageUploadSchema})
    def upload_image(self, slug: str, file: File[UploadedFile]) -> Status[dict[str, str]]:
        """Upload one image to R2 and return its public URL for a later product-create."""
        membership = self.require_membership(slug, "manage_catalog")
        return Status(201, {"url": services.store_product_image(membership.boutique, file)})
