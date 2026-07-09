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
    """Seller-only surface. JWTAuth authenticates (401 if no/bad token); IsSeller
    authorizes (403 for a valid non-seller). Future product/order/chat admin
    endpoints live here and inherit the same gate.

    GET /admin/me doubles as the frontend admin gate — a 200 means "this session
    is a seller".
    """

    @http_get("/me", response=CurrentUserSchema)
    def me(self, request):
        return request.auth
