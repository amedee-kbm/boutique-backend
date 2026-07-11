"""Tests for a customer's saved delivery addresses."""

import json
import typing as t

import pytest
from django.test import Client

from apps.users.models import Address, User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]
MakeUser = t.Callable[..., User]

ADDRESSES = "/api/v1/account/addresses"

PAYLOAD = {"label": "Home", "contact_name": "Aline", "phone": "+250788112233", "address": "Kigali, KG 11 Ave"}


def test_addresses_require_authentication(client: Client) -> None:
    assert client.get(ADDRESSES).status_code == 401


def test_add_then_list_an_address(client: Client, customer: User, bearer: Bearer) -> None:
    added = client.post(ADDRESSES, json.dumps(PAYLOAD), "application/json", headers=bearer(customer))
    assert added.status_code == 201
    assert added.json()["label"] == "Home"

    listed = client.get(ADDRESSES, headers=bearer(customer)).json()
    assert [a["address"] for a in listed] == ["Kigali, KG 11 Ave"]


def test_addresses_are_per_account(client: Client, customer: User, make_user: MakeUser, bearer: Bearer) -> None:
    client.post(ADDRESSES, json.dumps(PAYLOAD), "application/json", headers=bearer(customer))
    stranger = make_user(email="c2@example.com", phone_number="+250788222333", name="C2")
    assert client.get(ADDRESSES, headers=bearer(stranger)).json() == []


def test_delete_only_touches_your_own_address(
    client: Client, customer: User, make_user: MakeUser, bearer: Bearer
) -> None:
    stranger = make_user(email="c2@example.com", phone_number="+250788222333", name="C2")
    theirs = Address.objects.create(user=stranger, contact_name="X", phone="+250788000000", address="Elsewhere")

    # Deleting someone else's id is a no-op 204, not a delete.
    assert client.delete(f"{ADDRESSES}/{theirs.id}", headers=bearer(customer)).status_code == 204
    assert Address.objects.filter(id=theirs.id).exists()
