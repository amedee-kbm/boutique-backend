import typing as t

from django.http import HttpRequest
from ninja_extra import api_controller, http_get
from ninja_jwt.authentication import JWTAuth

from api.v1.permissions import IsSeller
from apps.users.schemas import CurrentUserSchema


@api_controller(
    "/admin",
    auth=JWTAuth(),
    permissions=[IsSeller],
    tags=["Admin"],
)
class AdminController:
    """Seller-only surface.

    JWTAuth authenticates (401 on a missing or bad token); IsSeller authorizes
    (403 for a valid non-seller). Future product, order and chat admin endpoints
    live here and inherit the same gate.

    GET /admin/me doubles as the frontend's admin gate — a 200 means "this
    session belongs to a seller".
    """

    @http_get("/me", response=CurrentUserSchema)
    def me(self, request: HttpRequest) -> t.Any:
        """The signed-in seller. A 200 here is the frontend's admin gate."""
        # ninja attaches `auth` to the request at runtime; it is not on HttpRequest.
        return getattr(request, "auth")
