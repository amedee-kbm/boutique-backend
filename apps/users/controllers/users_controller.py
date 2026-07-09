from ninja_extra import api_controller
from ninja_extra import http_get

from ninja_jwt.authentication import JWTAuth

from apps.users.schemas import CurrentUserSchema


@api_controller(
    "/users",
    auth=JWTAuth(),
    tags=["Users"],
)
class UserController:

    @http_get("/me", response=CurrentUserSchema)
    def me(self, request):
        return request.auth
