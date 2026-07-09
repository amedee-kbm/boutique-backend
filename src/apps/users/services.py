from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from ninja.errors import HttpError
from ninja_jwt.tokens import RefreshToken

from apps.users.models import User
from apps.users.tasks import send_password_reset_email

DUPLICATE_IDENTITY = "Email or phone number already registered"


def _taken(email: str, phone_number: str) -> bool:
    return User.objects.filter(Q(email__iexact=email) | Q(phone_number=phone_number)).exists()


def create_user(*, name: str, email: str, phone_number: str, password: str) -> User:
    """Register a customer.

    The uniqueness check is advisory — two concurrent registrations can both
    pass it — so the IntegrityError from the database constraint is caught and
    reported the same way. The constraint is the real gate.

    Raises:
        HttpError: 409 if the email or phone is taken, 400 if the password is weak.
    """
    if _taken(email, phone_number):
        raise HttpError(409, DUPLICATE_IDENTITY)

    try:
        validate_password(password, User(email=email, phone_number=phone_number, name=name))
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages)) from e

    try:
        with transaction.atomic():
            return User.objects.create_user(
                email=email,
                password=password,
                name=name,
                phone_number=phone_number,
                is_active=True,
            )
    except IntegrityError as e:
        raise HttpError(409, DUPLICATE_IDENTITY) from e


def tokens_for_user(user: User) -> dict[str, str]:
    """Mint an access/refresh pair. The caller decides where they are stored."""
    refresh = RefreshToken.for_user(user)
    # ninja_jwt types for_user() as the base Token, which has no access_token.
    return {"access": str(refresh.access_token), "refresh": str(refresh)}  # type: ignore[attr-defined]


def send_password_reset(email: str) -> None:
    """Enqueue a reset mail, but only for an address that exists.

    The endpoint answers identically either way, so returning early here is what
    keeps the API from confirming which addresses have accounts.
    """
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return
    send_password_reset_email.delay(str(user.pk))


def confirm_password_reset(*, uid: str, token: str, password: str) -> User:
    """Set a new password from a signed reset link.

    Raises:
        HttpError: 400 if the link is malformed, expired, already used, or the
            new password fails validation.
    """
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        raise HttpError(400, "Invalid reset link") from e

    if not default_token_generator.check_token(user, token):
        raise HttpError(400, "Reset link is invalid or has expired")

    try:
        validate_password(password, user)
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages)) from e

    user.set_password(password)
    user.save(update_fields=["password"])
    return user
