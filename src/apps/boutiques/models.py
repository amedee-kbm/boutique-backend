import uuid

from django.conf import settings
from django.db import models


class Boutique(models.Model):
    """A tenant. Its primary key is the ``store_id`` every domain table carries."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=255, unique=True)  # public, appears in the API path
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "boutiques"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """A person's standing at a boutique. Holding one makes a user a seller."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=8, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships"
        ordering = ["-created_at"]
        constraints = [
            # One standing per person per boutique. A user may hold memberships at
            # several boutiques; the request slug decides which one is in scope.
            models.UniqueConstraint(fields=["user", "boutique"], name="uniq_membership_user_boutique"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.boutique_id} ({self.role})"

    @property
    def is_owner(self) -> bool:
        """Whether this membership carries the OWNER role."""
        return self.role == self.Role.OWNER
