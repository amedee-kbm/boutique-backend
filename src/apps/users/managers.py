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
        """Create the seller account.

        `is_seller` is set here on purpose: the only superuser this project has
        is the shop owner, and the admin API gates on `is_seller`, not on
        `is_staff`. A superuser who could not reach /admin/me would be useless.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_seller", True)

        return self.create_user(email, password, **extra_fields)
