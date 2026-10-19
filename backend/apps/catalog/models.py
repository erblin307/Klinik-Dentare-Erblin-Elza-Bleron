from django.db import models
from django.db.models import Q

from apps.core.models import ClinicScopedModel


class Service(ClinicScopedModel):
    """A treatment or service a clinic offers, e.g. "Check-up" or "Whitening"."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        help_text="Default appointment length in minutes (5–480)."
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="In the clinic's currency. Leave empty if priced after consultation.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Target key for SameClinicConstraint foreign keys.
            models.UniqueConstraint(
                fields=["clinic", "id"], name="catalog_service_clinic_key"
            ),
            models.UniqueConstraint(
                fields=["clinic", "name"], name="catalog_service_unique_name"
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=5, duration_minutes__lte=480),
                name="catalog_service_duration_range",
            ),
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="catalog_service_price_non_negative",
            ),
        ]

    def __str__(self):
        return self.name
