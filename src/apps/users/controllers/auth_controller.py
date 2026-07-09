from ninja_extra import ControllerBase, api_controller, http_post
from ninja_extra.permissions import AllowAny

from ninja_jwt.controller import TokenBlackListController, TokenObtainPairController

from apps.users import services
from apps.users.schemas import (
    AuthResponseSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RegisterSchema,
)


@api_controller("/auth", tags=["Auth"], permissions=[AllowAny], auth=None)
class AuthController(
    ControllerBase,
    TokenObtainPairController,
    TokenBlackListController,
):
    """
    Authentication Controller handling JWT management and user lifecycle actions.

    Inherited JWT Endpoints (provided by ninja_jwt controllers):
        - POST /auth/pair          Obtain {access, refresh} tokens using email + password (Login).
        - POST /auth/refresh       Rotate tokens: issues a new access/refresh pair and blacklists 
                                   the old refresh token to prevent replay attacks.
        - POST /auth/blacklist     Explicitly revoke a refresh token (Logout).

    Custom Lifecycle Endpoints:
        - POST /auth/register                  Create a new user and return user data + initial tokens.
        - POST /auth/password/reset-request    Trigger a password reset email (returns 200 ambigous response).
        - POST /auth/password/reset-confirm    Set a new password using uid and token.

    Note:
        - Currently, authentication uses the user's email (defined as USERNAME_FIELD in the custom User model).
          Django's ModelBackend and ninja_jwt handle this mapping natively.
        - Security Best Practice: Tokens returned in JSON bodies should be intercepted by a 
          Frontend/BFF layer and stored in secure, HttpOnly, SameSite cookies.
    """

    @http_post("/register", response=AuthResponseSchema, auth=None)
    def register(self, payload: RegisterSchema):
        """Register a new user and automatically authenticate them."""
        user = services.create_user(
            name=payload.name,
            email=payload.email,
            phone_number=payload.phone_number,
            password=payload.password,
        )
        return AuthResponseSchema(user=user, **services.tokens_for_user(user))

    @http_post("/password/reset-request", response={200: dict}, auth=None)
    def reset_request(self, payload: PasswordResetRequestSchema):
        """Initiate password reset. Uses a generic response to prevent account enumeration."""
        services.send_password_reset(payload.email)
        return {"detail": "If that email has an account, a reset link is on its way."}

    @http_post("/password/reset-confirm", response={200: dict}, auth=None)
    def reset_confirm(self, payload: PasswordResetConfirmSchema):
        """Confirm password reset using the token sent via email."""
        services.confirm_password_reset(
            uid=payload.uid,
            token=payload.token,
            password=payload.password,
        )
        return {"detail": "Password updated. You can now sign in."}