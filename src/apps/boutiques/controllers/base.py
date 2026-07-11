import typing as t

from django.shortcuts import get_object_or_404
from ninja_extra import ControllerBase
from ninja_extra.exceptions import PermissionDenied

from apps.boutiques.models import Boutique, Membership
from apps.boutiques.permissions import Capability, has_permission
from apps.users.models import User


class TenantScopedController(ControllerBase):
    """Base for boutique-scoped seller endpoints under ``/stores/{slug}/``.

    Resolves the ``{slug}`` path segment to a boutique and the caller to a
    membership at that boutique, in one place. The status codes are deliberate
    and match the two-status rule and ADR-0013:

        401  no valid token           (JWTAuth answers this before the handler)
        404  no boutique by that slug
        403  a valid token whose user is not a member of this boutique, or is a
             member but lacks the capability the route requires

    Not-a-member and lacks-capability collapse to the same 403 on purpose: a
    stranger and an under-privileged staffer learn exactly the same thing.
    """

    def _user(self) -> User:
        # JWTAuth puts the authenticated User on request.auth; request.user is
        # AnonymousUser without a session. Mirror the existing controllers.
        # `context` is only None outside a request, which a route handler is not.
        request = self.context.request  # type: ignore[union-attr]
        return t.cast(User, getattr(request, "auth", None))

    def require_membership(self, slug: str, capability: Capability | None = None) -> Membership:
        """Return the caller's membership at ``slug``, or raise 404/403.

        Pass ``capability`` to gate on it; omit it to require only that the caller
        is a member (any role).
        """
        boutique = get_object_or_404(Boutique, slug=slug)
        membership = Membership.objects.select_related("boutique").filter(user=self._user(), boutique=boutique).first()
        if membership is None:
            raise PermissionDenied("You do not have access to this boutique.")
        if capability is not None and not has_permission(membership, capability):
            raise PermissionDenied("You do not have access to this boutique.")
        return membership
