"""Order placement and status changes. Pricing is server-authoritative."""

from uuid import UUID

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError

from apps.boutiques.models import Boutique
from apps.orders.models import Order, OrderItem
from apps.orders.schemas import OrderCreateSchema, OrderItemInSchema
from apps.products.models import Product, VariantOption
from apps.push import services as push_services
from apps.users.models import User


def _resolve_options(product: Product, option_ids: list[UUID]) -> dict[str, str]:
    """Map the chosen option ids to a {group name: value} snapshot, rejecting strays.

    Every id must name an option on one of *this* product's axes; an id from
    another product is a 400, not silently dropped.
    """
    if not option_ids:
        return {}
    options = list(VariantOption.objects.filter(id__in=set(option_ids), group__product=product).select_related("group"))
    if len(options) != len(set(option_ids)):
        raise HttpError(400, "An option does not belong to this product.")
    return {option.group.name: option.value for option in options}


def _add_line(order: Order, store: Boutique, item: OrderItemInSchema) -> int:
    """Snapshot one bag item onto the order and return its line total."""
    product = get_object_or_404(Product, store=store, id=item.product_id, is_visible=True)
    cover = product.images.first()
    OrderItem.objects.create(
        store=store,
        order=order,
        product=product,
        quantity=item.quantity,
        unit_price=product.price,  # server prices from the product; the client never sends a price
        name_snapshot=product.name,
        image_url_snapshot=cover.url if cover else "",
        options=_resolve_options(product, item.option_ids),
    )
    return product.price * item.quantity


def _existing_order(store: Boutique, customer: User, key: str) -> Order | None:
    return Order.objects.filter(store=store, customer=customer, idempotency_key=key).first()


def place_order(store: Boutique, customer: User, payload: OrderCreateSchema) -> tuple[Order, bool]:
    """Place an order, or return the existing one for a repeated idempotency key.

    Returns (order, created). A replay of a key this customer already used at
    this store returns their first order untouched — never a duplicate. The
    fast-path check races against a concurrent double-submit, so the unique
    constraint is the real gate: if two requests slip past the check together,
    the loser's INSERT raises IntegrityError and we return the winner's order
    rather than 500. The order and its lines commit as one savepoint.
    """
    existing = _existing_order(store, customer, payload.idempotency_key)
    if existing is not None:
        return existing, False

    if not payload.items:
        raise HttpError(400, "An order needs at least one item.")

    try:
        with transaction.atomic():
            order = Order.objects.create(
                store=store,
                customer=customer,
                idempotency_key=payload.idempotency_key,
                contact_name=payload.contact_name,
                phone=payload.phone,
                delivery_address=payload.delivery_address,
                note=payload.note,
            )
            order.total = sum(_add_line(order, store, item) for item in payload.items)
            order.save(update_fields=["total"])
    except IntegrityError:
        return Order.objects.get(store=store, customer=customer, idempotency_key=payload.idempotency_key), False
    return order, True


def set_status(store: Boutique, order_id: UUID, status: Order.Status) -> Order:
    """Move an order to a new status. Any of the four states is reachable."""
    order = get_object_or_404(Order, store=store, id=order_id)
    order.status = status
    order.save(update_fields=["status", "updated_at"])
    push_services.notify_order_status(store, order.customer, order_id=order.id, status=order.status)
    return order
