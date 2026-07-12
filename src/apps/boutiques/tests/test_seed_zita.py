"""Tests for the seed_zita management command."""

import json
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.boutiques.models import Boutique, Membership
from apps.products.models import Product, ProductImage, VariantGroup, VariantOption

pytestmark = pytest.mark.django_db

MEMORY_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "product_images": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
        "OPTIONS": {"base_url": "http://testserver/media/"},
    },
}

CAT = str(uuid.uuid4())
PROD = str(uuid.uuid4())
GROUP = str(uuid.uuid4())
OPTION = str(uuid.uuid4())
IMAGE = str(uuid.uuid4())


def write_export(tmp_path: Path) -> str:
    export = {
        "tables": {
            "categories": [{"id": CAT, "name": "Dresses", "slug": "dresses"}],
            "products": [
                {
                    "id": PROD,
                    "name": "Satin Gown",
                    "slug": "satin-gown",
                    "description": "A gown.",
                    "price": 35000,
                    "category_id": CAT,
                    "visible": True,
                    "featured": True,
                }
            ],
            "product_variant_groups": [{"id": GROUP, "product_id": PROD, "name": "Colour", "position": 0}],
            "product_variant_options": [
                {"id": OPTION, "group_id": GROUP, "value": "Beige", "position": 0, "hex": "#E3D5B8"}
            ],
            "product_images": [
                {
                    "id": IMAGE,
                    "product_id": PROD,
                    "url": f"https://supabase.example/storage/v1/object/public/product-images/{PROD}/1.jpg",
                    "alt": "front",
                    "position": 0,
                }
            ],
        }
    }
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.boutiques.management.commands.seed_zita.fetch_bytes", lambda url: b"\xff\xd8jpegbytes")


@override_settings(STORAGES=MEMORY_STORAGES)
def test_seed_builds_the_store_and_catalog(tmp_path: Path) -> None:
    call_command("seed_zita", file=write_export(tmp_path))

    boutique = Boutique.objects.get(slug="zita")
    assert boutique.name == "Zita Boutique"

    product = Product.objects.get(id=PROD)
    assert product.store_id == boutique.id  # stamped with the tenant
    assert product.price == 35000
    assert product.category_id == uuid.UUID(CAT)
    assert product.is_featured is True

    option = VariantOption.objects.get(id=OPTION)
    assert option.hex == "#E3D5B8"
    assert VariantGroup.objects.get(id=GROUP).name == "Colour"

    image = ProductImage.objects.get(id=IMAGE)
    assert image.url == f"http://testserver/media/stores/zita/products/{PROD}/1.jpg"  # re-keyed to R2 layout


@override_settings(STORAGES=MEMORY_STORAGES)
def test_seed_is_idempotent(tmp_path: Path) -> None:
    path = write_export(tmp_path)
    call_command("seed_zita", file=path)
    call_command("seed_zita", file=path)

    assert Boutique.objects.count() == 1
    assert Product.objects.count() == 1
    assert ProductImage.objects.count() == 1


@override_settings(STORAGES=MEMORY_STORAGES)
def test_seed_attaches_an_owner(tmp_path: Path) -> None:
    call_command(
        "seed_zita", file=write_export(tmp_path), owner_email="owner@zita.example", owner_phone="+250788000111"
    )

    membership = Membership.objects.get(boutique__slug="zita")
    assert membership.role == Membership.Role.OWNER
    assert membership.user.email == "owner@zita.example"
    assert membership.user.is_seller is True


def test_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    call_command("seed_zita", file=write_export(tmp_path), dry_run=True)

    assert not Boutique.objects.exists()
    assert not Product.objects.exists()
    assert "products: 1" in capsys.readouterr().out
