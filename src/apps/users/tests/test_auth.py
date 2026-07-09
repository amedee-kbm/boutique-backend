"""Tests for registration, login, session identity and the seller gate."""

import typing as t

import pytest
from django.core import mail
from django.test import Client

from apps.users.models import User
from conftest import STRONG_PASSWORD

pytestmark = pytest.mark.django_db

PostJson = t.Callable[..., t.Any]
Bearer = t.Callable[[User], dict[str, str]]


def _registration(**overrides: t.Any) -> dict[str, t.Any]:
    payload = {
        "name": "Aline",
        "email": "aline@example.com",
        "phone_number": "+250788112233",
        "password": STRONG_PASSWORD,
    }
    payload.update(overrides)
    return payload


# ─── Registration ────────────────────────────────────────────────────────────


def test_register_creates_user_and_returns_tokens(client: Client, post_json: PostJson) -> None:
    response = post_json(client, "/auth/register", _registration())

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["user"]["email"] == "aline@example.com"
    assert body["user"]["is_seller"] is False
    assert body["access"] and body["refresh"]

    user = User.objects.get(email="aline@example.com")
    # The password must be hashed, never stored as given.
    assert user.password != STRONG_PASSWORD
    assert user.check_password(STRONG_PASSWORD)


def test_register_normalises_local_phone_format(client: Client, post_json: PostJson) -> None:
    """`07…` is the way a Rwandan customer writes their number; store E.164."""
    response = post_json(client, "/auth/register", _registration(phone_number="0788 112 233"))

    assert response.status_code == 200, response.content
    assert User.objects.get(email="aline@example.com").phone_number == "+250788112233"


def test_register_rejects_a_phone_number_that_is_not_rwandan(client: Client, post_json: PostJson) -> None:
    response = post_json(client, "/auth/register", _registration(phone_number="+44 7700 900000"))

    assert response.status_code == 422
    assert not User.objects.exists()


def test_register_rejects_a_duplicate_email(client: Client, post_json: PostJson, customer: User) -> None:
    response = post_json(client, "/auth/register", _registration(email=customer.email))

    assert response.status_code == 409
    assert User.objects.count() == 1


def test_register_rejects_a_duplicate_phone_number(client: Client, post_json: PostJson, customer: User) -> None:
    """A second account may not claim a phone number already in use."""
    response = post_json(client, "/auth/register", _registration(phone_number=customer.phone_number))

    assert response.status_code == 409
    assert User.objects.count() == 1


def test_register_rejects_a_weak_password(client: Client, post_json: PostJson) -> None:
    response = post_json(client, "/auth/register", _registration(password="abc"))

    assert response.status_code == 400
    assert not User.objects.exists()


# ─── Login: this is where the credential is pinned ───────────────────────────


def test_login_takes_the_email_as_the_credential(client: Client, post_json: PostJson, customer: User) -> None:
    """USERNAME_FIELD is `email`.

    This test is the contract the frontend BFF must satisfy: /api/auth/login
    forwards its body straight to /auth/pair, so it has to post `email`.
    """
    response = post_json(client, "/auth/pair", {"email": customer.email, "password": STRONG_PASSWORD})

    assert response.status_code == 200, response.content
    assert set(response.json()) >= {"access", "refresh"}


def test_login_does_not_accept_a_phone_number(client: Client, post_json: PostJson, customer: User) -> None:
    """Guards against reintroducing phone-number login by accident.

    The original build plan specified phone login; the model chose email. If
    someone flips USERNAME_FIELD back without updating the frontend, this fails.

    400, not ninja's usual 422: ninja_jwt's controller validates the credential
    schema itself and rejects an unknown field with a bad-request.
    """
    response = post_json(client, "/auth/pair", {"phone_number": customer.phone_number, "password": STRONG_PASSWORD})

    assert response.status_code == 400


def test_login_rejects_a_wrong_password(client: Client, post_json: PostJson, customer: User) -> None:
    response = post_json(client, "/auth/pair", {"email": customer.email, "password": "not-the-password"})

    assert response.status_code == 401


def test_refresh_rotates_the_token_pair(client: Client, post_json: PostJson, customer: User) -> None:
    """ROTATE_REFRESH_TOKENS is on, so refreshing must mint a new refresh token."""
    pair = post_json(client, "/auth/pair", {"email": customer.email, "password": STRONG_PASSWORD}).json()

    response = post_json(client, "/auth/refresh", {"refresh": pair["refresh"]})

    assert response.status_code == 200, response.content
    assert response.json()["refresh"] != pair["refresh"]


# ─── Session identity ────────────────────────────────────────────────────────


def test_users_me_requires_a_token(client: Client) -> None:
    assert client.get("/api/v1/users/me").status_code == 401


def test_users_me_returns_the_authenticated_user(client: Client, customer: User, bearer: Bearer) -> None:
    response = client.get("/api/v1/users/me", headers=bearer(customer))

    assert response.status_code == 200
    assert response.json()["email"] == customer.email


def test_users_me_rejects_a_malformed_token(client: Client) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


# ─── The seller gate: the single most important authorization test ───────────


def test_admin_me_rejects_an_anonymous_request(client: Client) -> None:
    assert client.get("/api/v1/admin/me").status_code == 401


def test_admin_me_forbids_a_customer(client: Client, customer: User, bearer: Bearer) -> None:
    """A valid token for a non-seller is 403, not 401 and not 404.

    The distinction is load-bearing: 401 tells the frontend to re-authenticate,
    403 tells it the session is fine but the door is closed. Returning 401 here
    would send a signed-in customer into a login loop.
    """
    response = client.get("/api/v1/admin/me", headers=bearer(customer))

    assert response.status_code == 403


def test_admin_me_admits_a_seller(client: Client, seller: User, bearer: Bearer) -> None:
    response = client.get("/api/v1/admin/me", headers=bearer(seller))

    assert response.status_code == 200
    assert response.json()["is_seller"] is True


def test_create_superuser_is_a_seller(make_user: t.Callable[..., User]) -> None:
    """`make superuser` must produce an account that can reach the admin API."""
    user = User.objects.create_superuser(
        email="owner@example.com", password=STRONG_PASSWORD, phone_number="+250788000111", name="Owner"
    )

    assert user.is_seller and user.is_staff and user.is_superuser


# ─── Password reset ──────────────────────────────────────────────────────────


def test_reset_request_is_indistinguishable_for_an_unknown_email(
    client: Client, post_json: PostJson, customer: User
) -> None:
    """No account enumeration: the response must not reveal whether the email exists."""
    known = post_json(client, "/auth/password/reset-request", {"email": customer.email})
    unknown = post_json(client, "/auth/password/reset-request", {"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_reset_request_sends_mail_only_to_a_known_address(client: Client, post_json: PostJson, customer: User) -> None:
    post_json(client, "/auth/password/reset-request", {"email": "nobody@example.com"})
    assert len(mail.outbox) == 0

    post_json(client, "/auth/password/reset-request", {"email": customer.email})
    assert len(mail.outbox) == 1
    assert customer.email in mail.outbox[0].recipients()


def test_reset_confirm_sets_the_new_password(client: Client, post_json: PostJson, customer: User) -> None:
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(customer.pk))
    token = default_token_generator.make_token(customer)
    new_password = "another-quite-long-password-77"

    response = post_json(client, "/auth/password/reset-confirm", {"uid": uid, "token": token, "password": new_password})

    assert response.status_code == 200, response.content
    customer.refresh_from_db()
    assert customer.check_password(new_password)


def test_reset_confirm_rejects_a_tampered_token(client: Client, post_json: PostJson, customer: User) -> None:
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(customer.pk))

    response = post_json(
        client, "/auth/password/reset-confirm", {"uid": uid, "token": "made-up", "password": STRONG_PASSWORD}
    )

    assert response.status_code == 400
    customer.refresh_from_db()
    assert customer.check_password(STRONG_PASSWORD)
