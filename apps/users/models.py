import re

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator

from .managers import UserManager

class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=13, unique=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()
