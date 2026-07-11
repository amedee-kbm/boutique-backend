from uuid import UUID

from ninja import Schema

from apps.boutiques.models import Membership
from apps.users.models import User


class BoutiqueRefSchema(Schema):
    """A boutique as it rides along in another payload — the tenant, named."""

    slug: str
    name: str


class MembershipSchema(Schema):
    """The caller's own standing at a boutique, as /me and the admin gate report it."""

    store: BoutiqueRefSchema
    role: Membership.Role


class MemberSchema(Schema):
    """A member of a boutique, as the owner's member list shows them.

    An owner may only see people who belong to their own store; this schema is
    never assembled from the global user table (ADR-0013).
    """

    user_id: UUID
    name: str
    email: str
    role: Membership.Role

    @staticmethod
    def resolve_user_id(obj: Membership) -> UUID:
        """The member's user id."""
        return obj.user_id

    @staticmethod
    def resolve_name(obj: Membership) -> str:
        """The member's display name."""
        return obj.user.name

    @staticmethod
    def resolve_email(obj: Membership) -> str:
        """The member's email."""
        return obj.user.email


class StoreCustomerSchema(Schema):
    """A customer as an admin sees them: identity plus their activity in this store."""

    id: UUID
    name: str
    email: str
    phone: str
    order_count: int
    favorite_count: int

    @staticmethod
    def resolve_phone(obj: User) -> str:
        """The customer's phone number."""
        return obj.phone_number
