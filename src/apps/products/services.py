"""Write-side catalog operations. Controllers validate and call these; models stay dumb."""

import typing as t
import uuid
from pathlib import PurePosixPath
from uuid import UUID

from django.core.files.storage import storages
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.text import slugify

from apps.boutiques.models import Boutique
from apps.products.models import Category, Product, ProductImage, VariantGroup, VariantOption
from apps.products.schemas import ProductCreateSchema, ProductUpdateSchema


def _unique_slug(taken: t.Callable[[str], bool], name: str) -> str:
    """A slug from ``name``, suffixed -2, -3, … until ``taken`` says it is free."""
    base = slugify(name) or "item"
    slug, n = base, 2
    while taken(slug):
        slug, n = f"{base}-{n}", n + 1
    return slug


def create_category(store: Boutique, *, name: str, position: int = 0) -> Category:
    """Create a category with a store-unique slug."""
    slug = _unique_slug(lambda s: Category.objects.filter(store=store, slug=s).exists(), name)
    return Category.objects.create(store=store, name=name, slug=slug, position=position)


@transaction.atomic
def create_product(store: Boutique, payload: ProductCreateSchema) -> Product:
    """Create a product with its images and variant axes in one transaction."""
    category = get_object_or_404(Category, store=store, slug=payload.category_slug)
    slug = _unique_slug(lambda s: Product.objects.filter(store=store, slug=s).exists(), payload.name)
    product = Product.objects.create(
        store=store,
        category=category,
        name=payload.name,
        slug=slug,
        description=payload.description,
        price=payload.price,
        is_featured=payload.is_featured,
        is_visible=payload.is_visible,
    )
    ProductImage.objects.bulk_create(
        [ProductImage(store=store, product=product, url=i.url, alt=i.alt, position=i.position) for i in payload.images]
    )
    for group_in in payload.variant_groups:
        group = VariantGroup.objects.create(
            store=store, product=product, name=group_in.name, position=group_in.position
        )
        VariantOption.objects.bulk_create(
            [
                VariantOption(store=store, group=group, value=o.value, hex=o.hex, position=o.position)
                for o in group_in.options
            ]
        )
    return product


def update_product(store: Boutique, product_id: UUID, payload: ProductUpdateSchema) -> Product:
    """Update a product's scalar fields. Only fields present in the payload change."""
    product = get_object_or_404(Product, store=store, id=product_id)
    data = payload.model_dump(exclude_unset=True)
    category_slug = data.pop("category_slug", None)
    if category_slug is not None:
        product.category = get_object_or_404(Category, store=store, slug=category_slug)
    for field, value in data.items():
        setattr(product, field, value)
    product.save()
    return product


def delete_product(store: Boutique, product_id: UUID) -> None:
    """Delete a product (cascading its images and variants)."""
    get_object_or_404(Product, store=store, id=product_id).delete()


def store_product_image(store: Boutique, file: UploadedFile) -> str:
    """Save an uploaded image under the store's R2 prefix, returning its public URL."""
    storage = storages["product_images"]
    suffix = PurePosixPath(file.name or "").suffix.lower() or ".jpg"
    key = f"stores/{store.slug}/products/{uuid.uuid4().hex}{suffix}"
    return storage.url(storage.save(key, file))
