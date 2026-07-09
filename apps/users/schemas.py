# schemas.py
import re

from ninja import ModelSchema, Schema
from pydantic import EmailStr, field_validator

from apps.users.models import User


def _clean_phone(v: str) -> str:
    cleaned = re.sub(r'[\s\-\(\)]', '', v)
    if cleaned.startswith('07'):
        cleaned = '+250' + cleaned[1:]
    if not re.match(r'^\+2507[2389]\d{7}$', cleaned):
        raise ValueError("Nimero Igomba kuba 07X XXX XXX cg +250 7XX XXX XXX")
    return cleaned


class RegisterSchema(Schema):
    name: str
    email: EmailStr
    phone_number: str
    password: str

    @field_validator("phone_number")
    def validate_phone(cls, v: str) -> str:
        return _clean_phone(v)


class PasswordResetRequestSchema(Schema):
    email: EmailStr


class PasswordResetConfirmSchema(Schema):
    uid: str
    token: str
    password: str


class CurrentUserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "phone_number", "name", "is_seller"]


class AuthResponseSchema(Schema):
    user: CurrentUserSchema
    access: str
    refresh: str
