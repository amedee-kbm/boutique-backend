import typing as t
from uuid import UUID

from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from apps.users import services
from apps.users.models import Address, User
from apps.users.schemas import AddressCreateSchema, AddressSchema


@api_controller("/account/addresses", auth=JWTAuth(), tags=["Account"])
class AddressesController(ControllerBase):
    """A customer's saved delivery addresses, for order prefill.

    Global to the account, not per-store: the same addresses prefill an order at
    any boutique.
    """

    def _user(self) -> User:
        return t.cast(User, getattr(self.context.request, "auth", None))  # type: ignore[union-attr]

    @http_get("", response=list[AddressSchema])
    def my_addresses(self) -> t.Any:
        """The signed-in customer's saved addresses."""
        return self._user().addresses.all()

    @http_post("", response={201: AddressSchema})
    def add(self, payload: AddressCreateSchema) -> Status[Address]:
        """Save a delivery address."""
        address = services.add_address(
            self._user(),
            label=payload.label,
            contact_name=payload.contact_name,
            phone=payload.phone,
            address=payload.address,
        )
        return Status(201, address)

    @http_delete("/{address_id}", response={204: None})
    def remove(self, address_id: UUID) -> Status[None]:
        """Delete one of the customer's saved addresses."""
        services.delete_address(self._user(), address_id)
        return Status(204, None)
