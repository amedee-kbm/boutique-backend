from django.http import HttpRequest

from ninja_extra.permissions import BasePermission


class IsSeller(BasePermission):
    """Authorization gate for seller-only endpoints.

    Runs after JWTAuth like in this example:
            @api_controller(
            "/admin",
            auth=JWTAuth(),
            permissions=[IsSeller],
            tags=["Admin"],
            )

    So a bad/absent token is already a 401;
    a valid token for a non-seller fails here as a 403. 
    This Mirrors ninja_extra's IsAdminUser, but checks for ``is_seller`` flag instead of ``is_staff``.
    """

    message = "You must be a seller to access this resource."

    def has_permission(self, request: HttpRequest, controller) -> bool:
        # Notes on getting the user:
        # request.user = Django's Session/Cookie auth (Defaults to AnonymousUser)
        # request.auth = Django Ninja's Token/JWT auth (Whatever auth=JWTAuth() returns. Maybe AbstractBaseUser as in the source code below?)
        #def jwt_authenticate(self, request: HttpRequest, token: str) -> AbstractBaseUser:
        #    request.user = AnonymousUser()
        #    validated_token = self.get_validated_token(token)
        #    user = self.get_user(validated_token)
        #    request.user = user
        #    return user
        # We always get the User object regardless of the auth method used
        user = getattr(request, "auth", None) or getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_seller", False))
