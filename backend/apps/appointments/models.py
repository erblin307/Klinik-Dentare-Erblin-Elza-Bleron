import secrets

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q
from django.utils.translation import gettext_lazy as _

from apps.core.constraints import SameClinicConstraint
from apps.core.models import ClinicScopedModel


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class AppointmentStatus(models.TextChoices):
    PENDING = "pending", _("Pending confirmation")
    CONFIRMED = "confirmed", _("Confirmed")
    CHECKED_IN = "checked_in", _("Checked in")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")
    NO_SHOW = "no_show", _("No-show")


class AppointmentSource(models.TextChoices):
    STAFF = "staff", _("Staff")
    PHONE = "phone", _("Phone")
    WEBSITE = "website", _("Website")
    CHATBOT = "chatbot", _("Chatbot")


# Appointments in these states free their time slot. Every other state,
# including any added later, blocks it.
SLOT_RELEASING_STATUSES = [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]

# The booked interval as a half-open range [start_at, end_at), so
# back-to-back appointments (10:00–10:30, 10:30–11:00) do not overlap.
BOOKED_INTERVAL = TsTzRange("start_at", "end_at", RangeBoundary())

# Booking references: 8 characters without look-alikes (0/O, 1/I), ~40 bits.
# They always contain a digit, so ordinary words are never mistaken for one.
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERENCE_LENGTH = 8


def generate_reference():
    while True:
        reference = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))
        if any(ch.isdigit() for ch in reference):
            return reference


# Names of the double-booking constraints (also used by the booking service).
DENTIST_OVERLAP_CONSTRAINT = "appointments_no_dentist_overlap"
PATIENT_OVERLAP_CONSTRAINT = "appointments_no_patient_overlap"


class Appointment(ClinicScopedModel):
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="appointments"
    )
    dentist = models.ForeignKey(
        "staff.Dentist", on_delete=models.PROTECT, related_name="appointments"
    )
    service = models.ForeignKey(
        "catalog.Service", on_delete=models.PROTECT, related_name="appointments"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.PENDING
    )
    source = models.CharField(
        max_length=20, choices=AppointmentSource.choices, default=AppointmentSource.STAFF
    )
    notes = models.TextField(blank=True, help_text="Internal notes for clinic staff.")
    reference = models.CharField(
        max_length=REFERENCE_LENGTH,
        default=generate_reference,
        editable=False,
        help_text="Secret code given to the patient; proves ownership of the booking.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reference"], name="appointments_appointment_reference_key"
            ),
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="appointments_appointment_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(status__in=AppointmentStatus.values),
                name="appointments_appointment_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(source__in=AppointmentSource.values),
                name="appointments_appointment_source_valid",
            ),
            # Double-booking prevention. Enforced by PostgreSQL (GiST
            # exclusion constraints), so concurrent bookings cannot race.
            ExclusionConstraint(
                name=DENTIST_OVERLAP_CONSTRAINT,
                expressions=[
                    ("dentist", RangeOperators.EQUAL),
                    (BOOKED_INTERVAL, RangeOperators.OVERLAPS),
                ],
                condition=~Q(status__in=SLOT_RELEASING_STATUSES),
                violation_error_message=_(
                    "The dentist already has an appointment at this time."
                ),
            ),
            ExclusionConstraint(
                name=PATIENT_OVERLAP_CONSTRAINT,
                expressions=[
                    ("patient", RangeOperators.EQUAL),
                    (BOOKED_INTERVAL, RangeOperators.OVERLAPS),
                ],
                condition=~Q(status__in=SLOT_RELEASING_STATUSES),
                violation_error_message=_(
                    "The patient already has an appointment at this time."
                ),
            ),
            SameClinicConstraint(
                field="patient", name="appointments_appointment_patient_same_clinic"
            ),
            SameClinicConstraint(
                field="dentist", name="appointments_appointment_dentist_same_clinic"
            ),
            SameClinicConstraint(
                field="service", name="appointments_appointment_service_same_clinic"
            ),
        ]
        indexes = [
            models.Index(
                fields=["clinic", "start_at"], name="appointments_clinic_start_idx"
            ),
        ]

    def __str__(self):
        return f"{self.start_at:%Y-%m-%d %H:%M} {self.patient} with {self.dentist}"
