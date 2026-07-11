import typing as t

from django.shortcuts import get_object_or_404
from ninja_extra import ControllerBase, api_controller, http_get
from ninja_extra.permissions import AllowAny

from apps.boutiques.models import Boutique
from apps.products import selectors
from apps.products.schemas import (
    CategoryCardSchema,
    FacetsSchema,
    PagedProductsSchema,
    ProductDetailSchema,
)

_MAX_PAGE = 60


def _multi(value: str | None) -> list[str]:
    """Split a comma-separated facet param (`colour=Beige,Red`) into values."""
    return [part.strip() for part in value.split(",") if part.strip()] if value else []


@api_controller("/stores/{slug}/catalog", tags=["Catalog"], auth=None, permissions=[AllowAny])
class StorefrontController(ControllerBase):
    """The public storefront read surface for one boutique.

    No authentication: anyone may browse. Every route is scoped to the `{slug}`
    tenant, so a boutique that does not exist is a 404 and nothing leaks across
    stores.
    """

    def _store(self, slug: str) -> Boutique:
        return get_object_or_404(Boutique, slug=slug)

    @http_get("/products", response=PagedProductsSchema)
    def products(
        self,
        slug: str,
        category: str | None = None,
        colour: str | None = None,
        size: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        q: str | None = None,
        sort: str = "newest",
        limit: int = 24,
        offset: int = 0,
    ) -> dict[str, t.Any]:
        """The product grid: filtered, sorted, paginated, visible-only."""
        store = self._store(slug)
        limit = max(1, min(limit, _MAX_PAGE))
        offset = max(0, offset)
        qs = selectors.list_products(
            store,
            sort=sort,
            category=category,
            colours=_multi(colour),
            sizes=_multi(size),
            price_min=price_min,
            price_max=price_max,
            q=q,
        )
        count = qs.count()
        return {"items": list(qs[offset : offset + limit]), "count": count, "limit": limit, "offset": offset}

    @http_get("/facets", response=FacetsSchema)
    def facets(
        self,
        slug: str,
        category: str | None = None,
        colour: str | None = None,
        size: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        q: str | None = None,
    ) -> selectors.Facets:
        """Counts for the "Show N results" meta and the filter rail."""
        store = self._store(slug)
        return selectors.product_facets(
            store,
            category=category,
            colours=_multi(colour),
            sizes=_multi(size),
            price_min=price_min,
            price_max=price_max,
            q=q,
        )

    @http_get("/categories", response=list[CategoryCardSchema])
    def categories(self, slug: str) -> t.Any:
        """The category index, each with a product count and a cover image."""
        return selectors.categories_index(self._store(slug))

    @http_get("/products/{product_slug}", response=ProductDetailSchema)
    def product(self, slug: str, product_slug: str) -> t.Any:
        """A single product's full detail, or 404 if it is missing or hidden."""
        return selectors.get_product(self._store(slug), product_slug)
