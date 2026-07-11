from django.contrib import admin

from apps.products.models import Category, Product, ProductImage, VariantGroup, VariantOption


class ProductImageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = ProductImage
    extra = 0


class VariantGroupInline(admin.TabularInline):  # type: ignore[type-arg]
    model = VariantGroup
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "store", "position")
    list_filter = ("store",)
    search_fields = ("name", "slug")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "store", "category", "price", "is_visible", "is_featured")
    list_filter = ("store", "category", "is_visible", "is_featured")
    search_fields = ("name", "slug")
    inlines = [ProductImageInline, VariantGroupInline]


@admin.register(VariantOption)
class VariantOptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("value", "group", "hex", "position")
    search_fields = ("value",)
