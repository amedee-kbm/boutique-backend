from django.contrib import admin

from apps.favorites.models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("customer", "product", "store", "created_at")
    list_filter = ("store",)
