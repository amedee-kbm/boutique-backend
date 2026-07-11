import typing as t

from django.contrib.auth.base_user import BaseUserManager

if t.TYPE_CHECKING:
    from apps.users.models import User


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None = None, **extra_fields: t.Any) -> "User":
        """Create a customer. Email is the login credential, so it is required."""
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: t.Any) -> "User":
        """Create a Django platform administrator.

        This is not a seller. Under multi-tenancy `is_seller` is computed from
        boutique membership (ADR-0013), so a superuser reaches the *Django admin*
        but reaches a store's API only once it holds a membership there. The seed
        gives Zita's owner one; a bare superuser has none.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)
