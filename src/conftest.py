import json
import typing as t

import pytest
from django.test import Client

from apps.boutiques.models import Boutique, Membership
from apps.users.models import User

API = "/api/v1"

# Long enough and odd enough to clear Django's password validators. Short or
# common passwords are used deliberately in the tests that assert rejection.
STRONG_PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def post_json() -> t.Callable[..., t.Any]:
    def _post(client: Client, path: str, payload: dict[str, t.Any], **kwargs: t.Any) -> t.Any:
        return client.post(
            f"{API}{path}",
            data=json.dumps(payload),
            content_type="application/json",
            **kwargs,
        )

    return _post


@pytest.fixture
def make_user() -> t.Callable[..., User]:
    def _make(
        email: str = "customer@example.com",
        phone_number: str = "+250788123456",
        name: str = "Customer",
        password: str = STRONG_PASSWORD,
    ) -> User:
        return User.objects.create_user(
            email=email,
            password=password,
            name=name,
            phone_number=phone_number,
        )

    return _make


@pytest.fixture
def boutique() -> Boutique:
    return Boutique.objects.create(slug="zita", name="Zita Boutique")


@pytest.fixture
def customer(make_user: t.Callable[..., User]) -> User:
    return make_user()


@pytest.fixture
def seller(make_user: t.Callable[..., User], boutique: Boutique) -> User:
    """A seller is a boutique member. This one owns `boutique`."""
    user = make_user(email="seller@example.com", phone_number="+250788999888", name="Seller")
    Membership.objects.create(user=user, boutique=boutique, role=Membership.Role.OWNER)
    return user


@pytest.fixture
def staff(make_user: t.Callable[..., User], boutique: Boutique) -> User:
    """A staff member of `boutique` — operational access, no governance."""
    user = make_user(email="staff@example.com", phone_number="+250788777666", name="Staff")
    Membership.objects.create(user=user, boutique=boutique, role=Membership.Role.STAFF)
    return user


@pytest.fixture
def bearer(post_json: t.Callable[..., t.Any], client: Client) -> t.Callable[[User], dict[str, str]]:
    """Exchange a user's credentials for a real access token via /auth/pair.

    Minting the token by calling the endpoint rather than constructing one
    directly means these tests exercise the login path on every run.
    """

    def _bearer(user: User) -> dict[str, str]:
        response = post_json(client, "/auth/pair", {"email": user.email, "password": STRONG_PASSWORD})
        assert response.status_code == 200, response.content
        return {"Authorization": f"Bearer {response.json()['access']}"}

    return _bearer
