# schemas.py
import re
from ninja import Schema
from pydantic import field_validator

def _clean_phone(v: str) -> str:
    cleaned = re.sub(r'[\s\-\(\)]', '', v)
    if cleaned.startswith('07'):
        cleaned = '+250' + cleaned[1:]
    if not re.match(r'^\+2507[2389]\d{7}$', cleaned):
        raise ValueError("Nimero Igomba kuba 07X XXX XXX cg +250 7XX XXX XXX")
    return cleaned

class UserCreateSchema(Schema):
    name: str
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _clean_phone(v)

class LoginSchema(Schema):
    phone_number: str
    password: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _clean_phone(v)


