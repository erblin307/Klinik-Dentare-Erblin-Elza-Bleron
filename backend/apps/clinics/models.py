from django.db import models

from apps.core.models import TimeStampedModel

from .validators import validate_timezone


class Clinic(TimeStampedModel):
    """A dental clinic: the tenant that owns all clinic-scoped data."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=80, unique=True, help_text="Stable URL identifier of the clinic."
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(
        max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 code, e.g. AL or XK."
    )
    timezone = models.CharField(
        max_length=64,
        validators=[validate_timezone],
        help_text="IANA time zone, e.g. Europe/Tirane. Working hours use this zone.",
    )
    currency = models.CharField(
        max_length=3, default="EUR", help_text="ISO 4217 code used for service prices."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
