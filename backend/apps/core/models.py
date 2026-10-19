"""Abstract base models shared by all apps. This module creates no tables."""

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ClinicScopedModel(TimeStampedModel):
    """
    Base class for every table holding data that belongs to one clinic.

    The ``clinic`` column is the tenant key. Relations between clinic-scoped
    models must be declared with ``SameClinicConstraint`` so the database
    rejects rows that point at another clinic's data.
    """

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT)

    class Meta:
        abstract = True
