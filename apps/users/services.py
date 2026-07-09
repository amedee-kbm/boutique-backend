from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from ninja.errors import HttpError
from ninja_jwt.tokens import RefreshToken

from apps.users.tasks import send_password_reset_email

User = get_user_model()

def _taken(email: str, phone_number: str) -> bool:
    return User.objects.filter(
        Q(email__iexact=email) | Q(phone_number=phone_number)
    ).exists()

def create_user(*, name: str, email: str, phone_number: str, password: str):
    if _taken(email, phone_number):
        raise HttpError(409, "Email or phone number already registered")
    
    try:
        validate_password(password, User(email=email, phone_number=phone_number, name=name))
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages))
    
    try:
        with transaction.atomic():
            return User.objects.create_user(
                email=email,
                password=password,
                name=name,
                phone_number=phone_number,
                is_active=True,
            )  # type: ignore
    except IntegrityError:
        raise HttpError(409, "Email or phone number already registered")
  

def tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}  # type: ignore


def send_password_reset(email: str) -> None:
    # Only enqueue when the address exists; the endpoint returns the same 200
    # either way, so this doesn't leak which emails have accounts.
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return
    send_password_reset_email.delay(str(user.pk)) # type: ignore


def confirm_password_reset(*, uid: str, token: str, password: str):
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        raise HttpError(400, "Invalid reset link")

    if not default_token_generator.check_token(user, token):
        raise HttpError(400, "Reset link is invalid or has expired")

    try:
        validate_password(password, user)
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages))

    user.set_password(password)
    user.save(update_fields=["password"])
    return user