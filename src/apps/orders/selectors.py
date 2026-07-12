"""Read-side order queries for the customer's history and the seller inbox."""

from uuid import UUID

from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from pydantic import AwareDatetime

from apps.boutiques.models import Boutique
from apps.orders.models import Order
from apps.users.models import User


def customer_orders(store: Boutique, customer: User) -> QuerySet[Order]:
    """A customer's own orders at one store, newest first."""
    return Order.objects.filter(store=store, customer=customer).annotate(item_count=Count("items"))


def customer_order(store: Boutique, customer: User, order_id: UUID) -> Order:
    """One of the customer's own orders, with its lines, or 404."""
    qs = Order.objects.filter(store=store, customer=customer).prefetch_related("items")
    return get_object_or_404(qs, id=order_id)


def inbox(
    store: Boutique,
    *,
    since: AwareDatetime | None = None,
    since_id: UUID | None = None,
    status: Order.Status | None = None,
) -> QuerySet[Order]:
    """The seller inbox: every order at the store, newest first.

    ``since`` (a created_at cursor) keeps polling cheap — a client asks only for
    orders after the last it saw. Pass ``since_id`` (the last order's id) too and
    the cursor breaks timestamp ties on it, so an order sharing the boundary
    order's created_at is not silently skipped.
    """
    qs = Order.objects.filter(store=store).select_related("customer").annotate(item_count=Count("items"))
    if status is not None:
        qs = qs.filter(status=status)
    if since is not None:
        if since_id is not None:
            qs = qs.filter(Q(created_at__gt=since) | Q(created_at=since, id__gt=since_id))
        else:
            qs = qs.filter(created_at__gt=since)
    return qs


def store_order(store: Boutique, order_id: UUID) -> Order:
    """One order at the store (seller view), with its lines, or 404."""
    return get_object_or_404(Order.objects.filter(store=store).prefetch_related("items"), id=order_id)
