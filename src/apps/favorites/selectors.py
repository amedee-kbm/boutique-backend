"""Read-side favorite queries."""

from django.db.models import QuerySet

from apps.boutiques.models import Boutique
from apps.products.models import Product
from apps.users.models import User


def favorite_products(store: Boutique, customer: User) -> QuerySet[Product]:
    """The visible products a customer has favorited at a store, newest first.

    Returned as products (not Favorite rows) so the storefront renders them with
    the same card it uses everywhere.
    """
    return (
        Product.objects.filter(favorites__customer=customer, favorites__store=store, is_visible=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("-favorites__created_at")
    )
