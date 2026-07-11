from django.contrib import admin

from apps.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):  # type: ignore[type-arg]
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("contact_name", "store", "status", "total", "created_at")
    list_filter = ("store", "status")
    search_fields = ("contact_name", "phone")
    inlines = [OrderItemInline]
