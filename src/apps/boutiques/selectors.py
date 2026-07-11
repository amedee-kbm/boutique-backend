"""Read-side queries for the boutique admin surface."""

from django.db.models import Count, Q, QuerySet

from apps.boutiques.models import Boutique
from apps.users.models import User


def store_customers(store: Boutique) -> QuerySet[User]:
    """Customers with activity in this store — the only customers an admin may see.

    An admin never reads the global user table. Only users who placed an order or
    favorited a product *at this store* appear, each with their per-store counts
    (ADR-0013). Global existence, per-store visibility.
    """
    return (
        User.objects.filter(Q(orders__store=store) | Q(favorites__store=store))
        .annotate(
            order_count=Count("orders", filter=Q(orders__store=store), distinct=True),
            favorite_count=Count("favorites", filter=Q(favorites__store=store), distinct=True),
        )
        .distinct()
        .order_by("name")
    )
