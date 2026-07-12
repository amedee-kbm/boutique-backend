from django.contrib import admin

from apps.push.models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "store", "created_at")
    list_filter = ("store",)
