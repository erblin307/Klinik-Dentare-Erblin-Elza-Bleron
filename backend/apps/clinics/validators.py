from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(
            _("“%(value)s” is not a valid IANA time zone."),
            code="invalid_timezone",
            params={"value": value},
        )
