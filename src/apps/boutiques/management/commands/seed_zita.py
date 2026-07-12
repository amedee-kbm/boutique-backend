"""Seed the Zita boutique (store #1) and its catalog from the Supabase export.

The export is single-tenant: it has no store, only rows. This command synthesizes
Zita, stamps its store_id onto every category / product / variant, and re-keys the
product images out of Supabase Storage into R2 under stores/{slug}/products/….

Idempotent and re-runnable: catalog rows keep their original ids (update_or_create),
and an image already present in R2 is not fetched or uploaded again.
"""

import json
import typing as t
from pathlib import Path
from urllib.request import urlopen

from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages
from django.core.management.base import BaseCommand, CommandParser

from apps.boutiques.models import Boutique, Membership
from apps.products.models import Category, Product, ProductImage, VariantGroup, VariantOption
from apps.users.models import User

DEFAULT_EXPORT = "data/supabase-export.json"

# Tables the storefront needs. Chat, push, and the single legacy order are not
# carried; unreferenced storage orphans are ignored (only the 67 product images
# below are copied).
_COUNTED = ("categories", "products", "product_variant_groups", "product_variant_options", "product_images")


def fetch_bytes(url: str) -> bytes:
    """Download a public object. Isolated so tests can patch the network away."""
    with urlopen(url, timeout=30) as response:  # nosec B310 - trusted https export URLs
        return t.cast(bytes, response.read())


class Command(BaseCommand):
    help = "Seed the Zita boutique (store #1) and its catalog from the Supabase export."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command's flags."""
        parser.add_argument("--file", default=DEFAULT_EXPORT)
        parser.add_argument("--slug", default="zita")
        parser.add_argument("--name", default="Zita Boutique")
        parser.add_argument("--owner-email", default="", help="Create/attach an OWNER for the store.")
        parser.add_argument("--owner-phone", default="")
        parser.add_argument("--dry-run", action="store_true", help="Report scope; touch nothing.")

    def handle(self, *args: t.Any, **options: t.Any) -> None:
        """Synthesize the store, stamp the catalog with its id, and re-key images to R2."""
        tables = json.loads(Path(options["file"]).read_text(encoding="utf-8"))["tables"]

        if options["dry_run"]:
            self.stdout.write("Would seed:")
            for name in _COUNTED:
                self.stdout.write(f"  {name}: {len(tables[name])}")
            return

        slug: str = options["slug"]
        storage = storages["product_images"]
        boutique, _ = Boutique.objects.update_or_create(slug=slug, defaults={"name": options["name"]})

        self._owner(boutique, options["owner_email"], options["owner_phone"])
        self._categories(boutique, tables["categories"])
        self._products(boutique, tables["products"])
        self._variants(boutique, tables["product_variant_groups"], tables["product_variant_options"])
        self._images(boutique, slug, storage, tables["product_images"])

        self.stdout.write(self.style.SUCCESS(f"Seeded {boutique.name}: {len(tables['products'])} products."))

    def _owner(self, boutique: Boutique, email: str, phone: str) -> None:
        if not email:
            return
        user, created = User.objects.get_or_create(
            email=email, defaults={"name": "Zita Owner", "phone_number": phone or "+250000000000"}
        )
        if created:
            user.set_unusable_password()  # the owner sets a real one via password reset
            user.save(update_fields=["password"])
        Membership.objects.get_or_create(user=user, boutique=boutique, defaults={"role": Membership.Role.OWNER})

    def _categories(self, boutique: Boutique, rows: list[dict[str, t.Any]]) -> None:
        for position, row in enumerate(rows):
            Category.objects.update_or_create(
                id=row["id"],
                defaults={"store": boutique, "name": row["name"], "slug": row["slug"], "position": position},
            )

    def _products(self, boutique: Boutique, rows: list[dict[str, t.Any]]) -> None:
        for row in rows:
            Product.objects.update_or_create(
                id=row["id"],
                defaults={
                    "store": boutique,
                    "category_id": row["category_id"],
                    "name": row["name"],
                    "slug": row["slug"],
                    "description": row.get("description") or "",
                    "price": row["price"],
                    "is_visible": row["visible"],
                    "is_featured": row["featured"],
                },
            )

    def _variants(self, boutique: Boutique, groups: list[dict[str, t.Any]], options: list[dict[str, t.Any]]) -> None:
        for group in groups:
            VariantGroup.objects.update_or_create(
                id=group["id"],
                defaults={
                    "store": boutique,
                    "product_id": group["product_id"],
                    "name": group["name"],
                    "position": group["position"],
                },
            )
        for option in options:
            VariantOption.objects.update_or_create(
                id=option["id"],
                defaults={
                    "store": boutique,
                    "group_id": option["group_id"],
                    "value": option["value"],
                    "hex": option.get("hex") or "",
                    "position": option["position"],
                },
            )

    def _images(self, boutique: Boutique, slug: str, storage: Storage, rows: list[dict[str, t.Any]]) -> None:
        for row in rows:
            source = row["url"]
            filename = source.rsplit("/", 1)[-1]
            key = f"stores/{slug}/products/{row['product_id']}/{filename}"
            if not storage.exists(key):
                storage.save(key, ContentFile(fetch_bytes(source)))
            ProductImage.objects.update_or_create(
                id=row["id"],
                defaults={
                    "store": boutique,
                    "product_id": row["product_id"],
                    "url": storage.url(key),
                    "alt": row.get("alt") or "",
                    "position": row["position"],
                },
            )
