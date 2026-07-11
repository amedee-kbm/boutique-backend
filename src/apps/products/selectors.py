"""Read-side queries for the catalog. No writes happen here."""

import typing as t
from dataclasses import dataclass
from uuid import UUID

from django.db.models import Count, Max, Min, Q, QuerySet
from django.shortcuts import get_object_or_404

from apps.boutiques.models import Boutique
from apps.products.models import Category, Product, ProductImage, VariantOption

# The two axes the storefront facets on. Group names are seeded from these.
COLOUR = "Colour"
SIZE = "Size"

_SORTS: dict[str, tuple[str, ...]] = {
    "newest": ("-created_at",),
    "price_asc": ("price", "-created_at"),
    "price_desc": ("-price", "-created_at"),
    "featured": ("-is_featured", "-created_at"),
}


# Frozen dataclasses, not NamedTuples: a `count` field would shadow tuple.count.
@dataclass(frozen=True)
class CategoryCard:
    id: UUID
    name: str
    slug: str
    product_count: int
    cover_image_url: str | None


@dataclass(frozen=True)
class FacetValue:
    value: str
    count: int
    hex: str | None


@dataclass(frozen=True)
class CategoryFacet:
    slug: str
    name: str
    count: int


@dataclass(frozen=True)
class Facets:
    count: int
    price_min: int | None
    price_max: int | None
    categories: list[CategoryFacet]
    colours: list[FacetValue]
    sizes: list[FacetValue]


def _filtered(
    store: Boutique,
    *,
    category: str | None = None,
    colours: t.Sequence[str] = (),
    sizes: t.Sequence[str] = (),
    price_min: int | None = None,
    price_max: int | None = None,
    q: str | None = None,
) -> QuerySet[Product]:
    """Visible products for a store narrowed by the storefront's filters.

    Facets combine as OR within an axis (`colours=[Beige, Red]`) and AND across
    axes (that set *and* `sizes=[M]`): the colour and size filters are separate
    joins, so both must be satisfied.
    """
    qs = Product.objects.filter(store=store, is_visible=True)
    if category:
        qs = qs.filter(category__slug=category)
    if colours:
        qs = qs.filter(variant_groups__name__iexact=COLOUR, variant_groups__options__value__in=list(colours))
    if sizes:
        qs = qs.filter(variant_groups__name__iexact=SIZE, variant_groups__options__value__in=list(sizes))
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return qs.distinct()


def list_products(store: Boutique, *, sort: str = "newest", **filters: t.Any) -> QuerySet[Product]:
    """Filtered, sorted products for the storefront grid."""
    qs = _filtered(store, **filters).select_related("category").prefetch_related("images")
    return qs.order_by(*_SORTS.get(sort, _SORTS["newest"]))


def get_product(store: Boutique, slug: str) -> Product:
    """A single visible product with everything the detail page renders, or 404."""
    qs = (
        Product.objects.filter(store=store, is_visible=True)
        .select_related("category")
        .prefetch_related("images", "variant_groups__options", "variant_groups__options__image")
    )
    return get_object_or_404(qs, slug=slug)


def categories_index(store: Boutique) -> list[CategoryCard]:
    """Categories with a visible-product count and a representative cover image."""
    cards: list[CategoryCard] = []
    categories = Category.objects.filter(store=store).annotate(
        n=Count("products", filter=Q(products__is_visible=True), distinct=True)
    )
    for category in categories:
        cover = (
            ProductImage.objects.filter(store=store, product__category=category, product__is_visible=True)
            .order_by("-product__is_featured", "-product__created_at", "position")
            .values_list("url", flat=True)
            .first()
        )
        cards.append(
            CategoryCard(
                id=category.id,
                name=category.name,
                slug=category.slug,
                product_count=category.n,
                cover_image_url=cover,
            )
        )
    return cards


def product_facets(store: Boutique, **filters: t.Any) -> Facets:
    """Counts for the "Show N results" meta and the filter rail, over the current filters."""
    # Materialise ids first: the Neon pooler orphans a server-side cursor at
    # COMMIT, and everything below reuses this set (engineering-notes.md).
    ids = list(_filtered(store, **filters).values_list("id", flat=True))
    span = Product.objects.filter(id__in=ids).aggregate(lo=Min("price"), hi=Max("price"))

    cat_rows = (
        Category.objects.filter(store=store)
        .annotate(n=Count("products", filter=Q(products__in=ids), distinct=True))
        .filter(n__gt=0)
        .order_by("position", "name")
        .values_list("slug", "name", "n")
    )
    colour_rows = (
        VariantOption.objects.filter(store=store, group__name__iexact=COLOUR, group__product__in=ids)
        .values("value", "hex")
        .annotate(n=Count("group__product", distinct=True))
        .order_by("value")
    )
    size_rows = (
        VariantOption.objects.filter(store=store, group__name__iexact=SIZE, group__product__in=ids)
        .values("value")
        .annotate(n=Count("group__product", distinct=True))
        .order_by("value")
    )
    return Facets(
        count=len(ids),
        price_min=span["lo"],
        price_max=span["hi"],
        categories=[CategoryFacet(slug=s, name=n, count=c) for s, n, c in cat_rows],
        colours=[FacetValue(value=r["value"], count=r["n"], hex=r["hex"] or None) for r in colour_rows],
        sizes=[FacetValue(value=r["value"], count=r["n"], hex=None) for r in size_rows],
    )
