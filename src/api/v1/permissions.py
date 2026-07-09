import typing as t

from django.http import HttpRequest
from ninja_extra.permissions import BasePermission


class IsSeller(BasePermission):
    """Authorization gate for seller-only endpoints.

    Mirrors ninja_extra's ``IsAdminUser`` but keys off ``is_seller`` rather than
    ``is_staff``: the shop owner is a seller, and staff-ness is a Django admin
    concern that has nothing to do with the storefront API.

    Runs *after* authentication::

        @api_controller("/admin", auth=JWTAuth(), permissions=[IsSeller], tags=["Admin"])

    so a missing or invalid token is already a 401 by the time this is reached.
    What this decides is the 403: a valid session belonging to a customer. The
    distinction matters to the frontend — 401 means re-authenticate, 403 means
    the session is fine and the door is closed. Conflating them loops a
    signed-in customer through the login screen forever.
    """

    message = "You must be a seller to access this resource."

    def has_permission(self, request: HttpRequest, controller: t.Any) -> bool:
        """True when the request carries an authenticated seller."""
        # `request.auth` is what JWTAuth returned (the User); `request.user` is
        # what Django's session middleware set (AnonymousUser when unauthenticated).
        # Checking both means this works under either authentication scheme.
        user = getattr(request, "auth", None) or getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_seller", False))
