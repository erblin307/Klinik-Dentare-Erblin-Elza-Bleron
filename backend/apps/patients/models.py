from django.db import models

from apps.core.models import ClinicScopedModel


class Patient(ClinicScopedModel):
    """
    A patient of one clinic.

    Contains personal data: collect only what the clinic needs, never log it,
    and never copy it into AI knowledge entries.
    """

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True, help_text="Internal notes for clinic staff.")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Target key for SameClinicConstraint foreign keys.
            models.UniqueConstraint(
                fields=["clinic", "id"], name="patients_patient_clinic_key"
            ),
        ]
        indexes = [
            models.Index(
                fields=["clinic", "last_name", "first_name"],
                name="patients_patient_name_idx",
            ),
            models.Index(fields=["clinic", "phone"], name="patients_patient_phone_idx"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
