import typing as t

from django.http import HttpRequest
from ninja_extra import api_controller, http_get
from ninja_jwt.authentication import JWTAuth

from apps.users.schemas import CurrentUserSchema


@api_controller(
    "/users",
    auth=JWTAuth(),
    tags=["Users"],
)
class UserController:
    @http_get("/me", response=CurrentUserSchema)
    def me(self, request: HttpRequest) -> t.Any:
        """The signed-in customer. JWTAuth put the User on request.auth."""
        # ninja attaches `auth` to the request at runtime; it is not on HttpRequest.
        return getattr(request, "auth")
