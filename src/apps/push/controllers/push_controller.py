import typing as t

from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_get, http_post
from ninja_extra.permissions import AllowAny
from ninja_jwt.authentication import JWTAuth

from apps.boutiques.models import Boutique
from apps.push import services
from apps.push.schemas import SubscribeSchema, UnsubscribeSchema, VapidKeySchema
from apps.users.models import User


@api_controller("/stores/{slug}/push", auth=JWTAuth(), tags=["Push"])
class PushController(ControllerBase):
    """The customer's web-push registration for one boutique's background pushes."""

    def _store(self, slug: str) -> Boutique:
        return get_object_or_404(Boutique, slug=slug)

    def _user(self) -> User:
        return t.cast(User, getattr(self.context.request, "auth", None))  # type: ignore[union-attr]

    @http_get("/key", auth=None, permissions=[AllowAny], response=VapidKeySchema)
    def key(self, slug: str) -> VapidKeySchema:
        """The VAPID public key the browser needs to build a subscription. Public."""
        return VapidKeySchema(vapid_public_key=settings.VAPID_PUBLIC_KEY)

    @http_post("/subscribe", response={201: dict})
    def subscribe(self, slug: str, payload: SubscribeSchema) -> Status[dict[str, str]]:
        """Register (or refresh) this browser's subscription."""
        services.subscribe(
            self._store(slug),
            self._user(),
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        return Status(201, {"detail": "Subscribed."})

    @http_post("/unsubscribe", response={204: None})
    def unsubscribe(self, slug: str, payload: UnsubscribeSchema) -> Status[None]:
        """Drop this browser's subscription."""
        services.unsubscribe(self._store(slug), self._user(), payload.endpoint)
        return Status(204, None)
