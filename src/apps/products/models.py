import uuid

from django.db import models


class Category(models.Model):
    """A department within a boutique — flat, ordered for display."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="categories", db_column="store_id"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        ordering = ["position", "name"]
        constraints = [
            # Slugs are unique within a store, not globally: two boutiques may both
            # have a "dresses" category.
            models.UniqueConstraint(fields=["store", "slug"], name="uniq_category_store_slug"),
        ]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """A garment a boutique sells. Price is whole RWF — the currency has no minor unit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="products", db_column="store_id"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField(help_text="Whole RWF.")
    is_visible = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="uniq_product_store_slug"),
        ]

    def __str__(self) -> str:
        return self.name


class ProductImage(models.Model):
    """A photo of a product, served from its R2 public URL."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="product_images", db_column="store_id"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=500)
    alt = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_images"
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.product_id} #{self.position}"


class VariantGroup(models.Model):
    """A selection axis for a product — "Colour", "Size" — carrying its options."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="variant_groups", db_column="store_id"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variant_groups")
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "variant_groups"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="uniq_variant_group_product_name"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}: {self.name}"


class VariantOption(models.Model):
    """One value on an axis — "Beige" (with a swatch hex), "M".

    An option may point at one of the product's images so the storefront can
    swap the photo when a colour is chosen. The link is one-directional: the
    old schema's circular image<->option FK is deliberately not reproduced.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "boutiques.Boutique", on_delete=models.CASCADE, related_name="variant_options", db_column="store_id"
    )
    group = models.ForeignKey(VariantGroup, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=100)
    hex = models.CharField(max_length=7, blank=True, help_text="Swatch colour for a colour option, e.g. #E3D5B8.")
    image = models.ForeignKey(ProductImage, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "variant_options"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["group", "value"], name="uniq_variant_option_group_value"),
        ]

    def __str__(self) -> str:
        return self.value
