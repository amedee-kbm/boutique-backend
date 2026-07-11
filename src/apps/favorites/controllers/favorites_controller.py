import typing as t
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from apps.boutiques.models import Boutique
from apps.favorites import selectors, services
from apps.products.models import Product
from apps.products.schemas import ProductCardSchema
from apps.users.models import User


@api_controller("/stores/{slug}/favorites", auth=JWTAuth(), tags=["Favorites"])
class FavoritesController(ControllerBase):
    """The signed-in customer's favorites at one boutique.

    Account-gated (JWTAuth) and never membership-scoped: a customer favorites at
    any store and sees only their own list there. A favorite is (customer, store,
    product).
    """

    def _store(self, slug: str) -> Boutique:
        return get_object_or_404(Boutique, slug=slug)

    def _customer(self) -> User:
        return t.cast(User, getattr(self.context.request, "auth", None))  # type: ignore[union-attr]

    @http_get("", response=list[ProductCardSchema])
    def my_favorites(self, slug: str) -> t.Any:
        """The customer's favorited products at this store."""
        return selectors.favorite_products(self._store(slug), self._customer())

    @http_post("/{product_id}", response={201: ProductCardSchema})
    def add(self, slug: str, product_id: UUID) -> Status[Product]:
        """Favorite a product. Idempotent."""
        favorite = services.add_favorite(self._store(slug), self._customer(), product_id)
        return Status(201, favorite.product)

    @http_delete("/{product_id}", response={204: None})
    def remove(self, slug: str, product_id: UUID) -> Status[None]:
        """Unfavorite a product. Idempotent."""
        services.remove_favorite(self._store(slug), self._customer(), product_id)
        return Status(204, None)
