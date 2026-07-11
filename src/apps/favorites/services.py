"""Add and remove favorites for the signed-in customer."""

from uuid import UUID

from django.shortcuts import get_object_or_404

from apps.boutiques.models import Boutique
from apps.favorites.models import Favorite
from apps.products.models import Product
from apps.users.models import User


def add_favorite(store: Boutique, customer: User, product_id: UUID) -> Favorite:
    """Favorite a visible product. Idempotent — favoriting twice is one row."""
    product = get_object_or_404(Product, store=store, id=product_id, is_visible=True)
    favorite, _ = Favorite.objects.get_or_create(customer=customer, store=store, product=product)
    return favorite


def remove_favorite(store: Boutique, customer: User, product_id: UUID) -> None:
    """Unfavorite a product. Idempotent — a no-op if it was not favorited."""
    Favorite.objects.filter(customer=customer, store=store, product_id=product_id).delete()
