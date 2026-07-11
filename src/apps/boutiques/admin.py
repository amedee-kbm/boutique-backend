from django.contrib import admin

from apps.boutiques.models import Boutique, Membership


@admin.register(Boutique)
class BoutiqueAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "boutique", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "boutique__slug")
