"""Tests for boutique tenancy: memberships, the seller signal, and store scoping."""

import typing as t

import pytest
from django.db import IntegrityError
from django.test import Client

from apps.boutiques.models import Boutique, Membership
from apps.boutiques.permissions import has_permission
from apps.users.models import User

pytestmark = pytest.mark.django_db

Bearer = t.Callable[[User], dict[str, str]]

ADMIN_ME = "/api/v1/stores/zita/admin/me"
MEMBERS = "/api/v1/stores/zita/admin/members"


# ─── The seller signal is computed from membership ───────────────────────────


def test_a_user_without_a_membership_is_not_a_seller(customer: User) -> None:
    assert customer.is_seller is False


def test_a_member_is_a_seller(seller: User) -> None:
    assert seller.is_seller is True


def test_staff_is_also_a_seller(staff: User) -> None:
    assert staff.is_seller is True


# ─── The membership constraint ───────────────────────────────────────────────


def test_a_user_holds_at_most_one_membership_per_boutique(seller: User, boutique: Boutique) -> None:
    """The unique constraint is the real gate; a second standing is rejected."""
    with pytest.raises(IntegrityError):
        Membership.objects.create(user=seller, boutique=boutique, role=Membership.Role.STAFF)


# ─── The authorization choke-point (pure, no database) ───────────────────────


def test_operational_capabilities_are_open_to_any_member() -> None:
    staff = Membership(role=Membership.Role.STAFF)
    assert has_permission(staff, "work_orders") is True
    assert has_permission(staff, "manage_catalog") is True


def test_governance_capabilities_are_owner_only() -> None:
    assert has_permission(Membership(role=Membership.Role.STAFF), "manage_members") is False
    assert has_permission(Membership(role=Membership.Role.OWNER), "manage_members") is True


# ─── /me carries the memberships the admin UI routes on ──────────────────────


def test_me_reports_memberships_for_a_seller(client: Client, seller: User, bearer: Bearer) -> None:
    body = client.get("/api/v1/users/me", headers=bearer(seller)).json()
    assert body["is_seller"] is True
    assert body["memberships"] == [{"store": {"slug": "zita", "name": "Zita Boutique"}, "role": "owner"}]


def test_me_has_no_memberships_for_a_customer(client: Client, customer: User, bearer: Bearer) -> None:
    body = client.get("/api/v1/users/me", headers=bearer(customer)).json()
    assert body["is_seller"] is False
    assert body["memberships"] == []


# ─── The store-scoped admin gate: 401 / 404 / 403 / 200 ──────────────────────


def test_store_admin_me_rejects_an_anonymous_request(client: Client) -> None:
    assert client.get(ADMIN_ME).status_code == 401


def test_store_admin_me_is_404_for_an_unknown_store(client: Client, seller: User, bearer: Bearer) -> None:
    assert client.get("/api/v1/stores/nope/admin/me", headers=bearer(seller)).status_code == 404


def test_store_admin_me_forbids_a_non_member(
    client: Client, boutique: Boutique, customer: User, bearer: Bearer
) -> None:
    """A valid token whose user is not a member of this store is 403 — not 401, not 404.

    401 would loop a signed-in seller through login; 404 would deny the store even
    exists. The session is fine; this door is closed. The store must exist for this
    to be a 403 rather than a 404, so `boutique` is in scope.
    """
    assert client.get(ADMIN_ME, headers=bearer(customer)).status_code == 403


def test_store_admin_me_admits_a_member(client: Client, staff: User, bearer: Bearer) -> None:
    response = client.get(ADMIN_ME, headers=bearer(staff))
    assert response.status_code == 200
    assert response.json() == {"store": {"slug": "zita", "name": "Zita Boutique"}, "role": "staff"}


def test_a_members_scope_does_not_leak_across_stores(client: Client, seller: User, bearer: Bearer) -> None:
    """An owner of one boutique is a stranger at another."""
    Boutique.objects.create(slug="other", name="Other Shop")
    assert client.get("/api/v1/stores/other/admin/me", headers=bearer(seller)).status_code == 403


# ─── Managing members is owner-only ──────────────────────────────────────────


def test_members_list_is_forbidden_to_staff(client: Client, staff: User, bearer: Bearer) -> None:
    assert client.get(MEMBERS, headers=bearer(staff)).status_code == 403


def test_members_list_is_visible_to_the_owner(client: Client, seller: User, staff: User, bearer: Bearer) -> None:
    response = client.get(MEMBERS, headers=bearer(seller))
    assert response.status_code == 200
    body = response.json()
    assert {m["email"] for m in body} == {"seller@example.com", "staff@example.com"}
    assert {m["role"] for m in body} == {"owner", "staff"}
