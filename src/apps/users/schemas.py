# schemas.py
import re

from ninja import ModelSchema, Schema
from pydantic import EmailStr, field_validator

from apps.boutiques.models import Membership
from apps.boutiques.schemas import BoutiqueRefSchema, MembershipSchema
from apps.users.models import Address, User


def _clean_phone(v: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]", "", v)
    if cleaned.startswith("07"):
        cleaned = "+250" + cleaned[1:]
    if not re.match(r"^\+2507[2389]\d{7}$", cleaned):
        raise ValueError("Nimero Igomba kuba 07X XXX XXX cg +250 7XX XXX XXX")
    return cleaned


class RegisterSchema(Schema):
    name: str
    email: EmailStr
    phone_number: str
    password: str

    @field_validator("phone_number")
    def validate_phone(cls, v: str) -> str:
        """Normalise a Rwandan number to E.164, rejecting anything else."""
        return _clean_phone(v)


class PasswordResetRequestSchema(Schema):
    email: EmailStr


class PasswordResetConfirmSchema(Schema):
    uid: str
    token: str
    password: str


class CurrentUserSchema(ModelSchema):
    # Both are computed, not columns: `is_seller` is true iff `memberships` is
    # non-empty. The admin UI reads `memberships` to learn its tenant(s) and
    # whether to show OWNER-only controls (ADR-0013).
    is_seller: bool
    memberships: list[MembershipSchema]

    class Meta:
        model = User
        fields = ["id", "email", "phone_number", "name"]

    @staticmethod
    def resolve_memberships(obj: User) -> list[MembershipSchema]:
        """The user's boutique memberships, each as a store + role."""
        return [
            MembershipSchema(
                store=BoutiqueRefSchema(slug=m.boutique.slug, name=m.boutique.name),
                role=Membership.Role(m.role),
            )
            for m in obj.memberships.select_related("boutique")
        ]


class AuthResponseSchema(Schema):
    user: CurrentUserSchema
    access: str
    refresh: str


class AddressSchema(ModelSchema):
    class Meta:
        model = Address
        fields = ["id", "label", "contact_name", "phone", "address"]


class AddressCreateSchema(Schema):
    label: str = ""
    contact_name: str
    phone: str
    address: str
