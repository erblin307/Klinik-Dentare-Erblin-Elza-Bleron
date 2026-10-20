"""Validation of the personal details a visitor gives the chatbot."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

_PHONE_SEPARATORS = re.compile(r"[\s\-./()]")


def clean_phone(value):
    """``"+383 44-123 456"`` -> ``"+38344123456"``; ``None`` if not 7–15 digits."""
    compact = _PHONE_SEPARATORS.sub("", value)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    digits = compact[1:] if compact.startswith("+") else compact
    return compact if re.fullmatch(r"[0-9]{7,15}", digits) else None


def clean_name(value):
    value = " ".join(value.split())
    if not 1 <= len(value) <= 100 or not any(ch.isalpha() for ch in value):
        return None
    if not all(ch.isalpha() or ch in " '-." for ch in value):
        return None
    return value


def clean_email(value):
    value = value.strip()
    try:
        validate_email(value)
    except ValidationError:
        return None
    return value
