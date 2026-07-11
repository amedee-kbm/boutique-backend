from uuid import UUID

from ninja import ModelSchema, Schema

from apps.products.models import ProductImage, VariantGroup, VariantOption


class CategoryRefSchema(Schema):
    """A category as it rides along on a product."""

    slug: str
    name: str


class CategoryCardSchema(Schema):
    """A category on the index, with its visible-product count and cover image."""

    id: UUID
    name: str
    slug: str
    product_count: int
    cover_image_url: str | None


class ProductImageSchema(ModelSchema):
    class Meta:
        model = ProductImage
        fields = ["id", "url", "alt", "position"]


class VariantOptionSchema(ModelSchema):
    image_url: str | None

    class Meta:
        model = VariantOption
        fields = ["id", "value", "hex", "position"]

    @staticmethod
    def resolve_image_url(obj: VariantOption) -> str | None:
        """The product image to show when this option is chosen, if any."""
        return obj.image.url if obj.image else None


class VariantGroupSchema(ModelSchema):
    options: list[VariantOptionSchema]

    class Meta:
        model = VariantGroup
        fields = ["id", "name", "position"]


class ProductCardSchema(Schema):
    """A product as the grid shows it: enough to render a tile, no variants."""

    id: UUID
    name: str
    slug: str
    price: int
    is_featured: bool
    category: CategoryRefSchema
    cover_image_url: str | None

    @staticmethod
    def resolve_cover_image_url(obj: object) -> str | None:
        """The first image, from the prefetched set."""
        images = list(getattr(obj, "images").all())
        return images[0].url if images else None


class ProductDetailSchema(Schema):
    """A product's full page: images and selection axes included."""

    id: UUID
    name: str
    slug: str
    description: str
    price: int
    is_featured: bool
    category: CategoryRefSchema
    images: list[ProductImageSchema]
    variant_groups: list[VariantGroupSchema]


class PagedProductsSchema(Schema):
    items: list[ProductCardSchema]
    count: int
    limit: int
    offset: int


class FacetValueSchema(Schema):
    value: str
    count: int
    hex: str | None


class CategoryFacetSchema(Schema):
    slug: str
    name: str
    count: int


class FacetsSchema(Schema):
    count: int
    price_min: int | None
    price_max: int | None
    categories: list[CategoryFacetSchema]
    colours: list[FacetValueSchema]
    sizes: list[FacetValueSchema]
