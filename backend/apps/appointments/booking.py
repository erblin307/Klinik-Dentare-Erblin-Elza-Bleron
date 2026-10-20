"""
Booking engine: availability search and the appointment lifecycle.

This module is the only place that creates, moves or changes the status of
appointments. It has no dependency on Django Admin or HTTP, so the admin, a
future API and the future chatbot all share the same rules:

* a booking must fit inside the dentist's working hours (gaps between two
  working-hour blocks are breaks), outside time off and clinic closures, and
  must not overlap another active appointment of the dentist or the patient;
* the dentist must be bookable and perform the service; everything must
  belong to the same, active clinic;
* valid bookings are confirmed immediately.

Overlaps are checked here for friendly errors, but the guarantee comes from
PostgreSQL's exclusion constraints: when two requests race for one slot, the
database rejects the second and it is reported as ``SLOT_TAKEN``.

Times are stored in UTC. Working hours are wall-clock times in the clinic's
time zone, converted per calendar date (so daylight-saving changes are
handled); returned slots carry the clinic's time zone.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.scheduling.models import TimeOff, WorkingHours
from apps.staff.models import DentistService

from .models import (
    DENTIST_OVERLAP_CONSTRAINT,
    PATIENT_OVERLAP_CONSTRAINT,
    REFERENCE_ALPHABET,
    REFERENCE_LENGTH,
    SLOT_RELEASING_STATUSES,
    Appointment,
    AppointmentSource,
    AppointmentStatus,
)

DEFAULT_SLOT_STEP_MINUTES = 15
MAX_SEARCH_DAYS = 31

# Allowed status changes. Cancelled, no-show and completed are final: a new
# booking is made instead, so it goes through the availability checks again.
STATUS_TRANSITIONS = {
    AppointmentStatus.PENDING: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CHECKED_IN: {AppointmentStatus.COMPLETED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}
RESCHEDULABLE_STATUSES = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}


class BookingErrorCode(str, Enum):
    CLINIC_INACTIVE = "clinic_inactive"
    CLINIC_MISMATCH = "clinic_mismatch"
    DENTIST_UNAVAILABLE = "dentist_unavailable"
    SERVICE_UNAVAILABLE = "service_unavailable"
    SERVICE_NOT_OFFERED = "service_not_offered"
    PATIENT_INACTIVE = "patient_inactive"
    INVALID_TIME = "invalid_time"
    INVALID_RANGE = "invalid_range"
    IN_THE_PAST = "in_the_past"
    OUTSIDE_WORKING_HOURS = "outside_working_hours"
    TIME_OFF = "time_off"
    SLOT_TAKEN = "slot_taken"
    PATIENT_BUSY = "patient_busy"
    INVALID_STATUS_CHANGE = "invalid_status_change"
    NOT_RESCHEDULABLE = "not_reschedulable"


# Messages are shown to staff and (later) patients: no personal data in them.
ERROR_MESSAGES = {
    BookingErrorCode.CLINIC_INACTIVE: _("The clinic is not accepting bookings."),
    BookingErrorCode.CLINIC_MISMATCH: _(
        "The patient, dentist and service must belong to the same clinic."
    ),
    BookingErrorCode.DENTIST_UNAVAILABLE: _("The dentist is not accepting bookings."),
    BookingErrorCode.SERVICE_UNAVAILABLE: _("The service is not available."),
    BookingErrorCode.SERVICE_NOT_OFFERED: _("The dentist does not perform this service."),
    BookingErrorCode.PATIENT_INACTIVE: _("The patient record is inactive."),
    BookingErrorCode.INVALID_TIME: _("The time must include a time zone."),
    BookingErrorCode.INVALID_RANGE: _("The date range is invalid or too long."),
    BookingErrorCode.IN_THE_PAST: _("The time is in the past."),
    BookingErrorCode.OUTSIDE_WORKING_HOURS: _(
        "The time is outside the dentist's working hours."
    ),
    BookingErrorCode.TIME_OFF: _("The dentist is away or the clinic is closed at this time."),
    BookingErrorCode.SLOT_TAKEN: _("The dentist already has an appointment at this time."),
    BookingErrorCode.PATIENT_BUSY: _("The patient already has an appointment at this time."),
    BookingErrorCode.INVALID_STATUS_CHANGE: _("This status change is not allowed."),
    BookingErrorCode.NOT_RESCHEDULABLE: _("This appointment can no longer be rescheduled."),
}

_CONSTRAINT_ERRORS = {
    DENTIST_OVERLAP_CONSTRAINT: BookingErrorCode.SLOT_TAKEN,
    PATIENT_OVERLAP_CONSTRAINT: BookingErrorCode.PATIENT_BUSY,
}
_DEADLOCK_SQLSTATE = "40P01"
_SAVE_ATTEMPTS = 3


class BookingError(ValidationError):
    """A request that breaks a booking rule; ``code`` is a ``BookingErrorCode``."""

    def __init__(self, code, message=None):
        super().__init__(message or ERROR_MESSAGES[code], code=code)


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_available_slots(
    dentist, service, start_date, end_date=None, *, step_minutes=DEFAULT_SLOT_STEP_MINUTES, now=None
):
    """
    Return the bookable slots for ``service`` with ``dentist`` on the clinic-
    local dates ``start_date``..``end_date`` (inclusive; default: one day).

    Slots are ``service.duration_minutes`` long and start every
    ``step_minutes`` from the beginning of each working period. Their
    datetimes are in the clinic's time zone. Only the dentist's availability
    is considered; the patient's other appointments are checked on booking.
    """
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive.")
    end_date = end_date or start_date
    if end_date < start_date or (end_date - start_date).days >= MAX_SEARCH_DAYS:
        raise BookingError(BookingErrorCode.INVALID_RANGE)
    _validate_participants(dentist=dentist, service=service)

    now = now or timezone.now()
    tz = _clinic_timezone(dentist)
    working = _working_periods(dentist, tz, start_date, end_date)
    if not working:
        return []
    range_start, range_end = working[0][0], working[-1][1]
    busy = [
        *_time_off(dentist, range_start, range_end).values_list("start_at", "end_at"),
        *_active_appointments(range_start, range_end)
        .filter(dentist=dentist)
        .values_list("start_at", "end_at"),
    ]

    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=step_minutes)
    slots = []
    for period_start, period_end in working:
        start = period_start
        while start + duration <= period_end:
            end = start + duration
            if start >= now and not any(b_start < end and b_end > start for b_start, b_end in busy):
                slots.append(Slot(start.astimezone(tz), end.astimezone(tz)))
            start += step
    return slots


def validate_new_appointment(*, patient, dentist, service, start_at, now=None):
    """Raise ``BookingError`` unless the appointment can be booked."""
    _validate_participants(dentist=dentist, service=service, patient=patient)
    _validate_time(
        dentist=dentist,
        patient=patient,
        start_at=start_at,
        end_at=_end_for_service(service, start_at),
        now=now or timezone.now(),
    )


def create_appointment(
    *, patient, dentist, service, start_at, source=AppointmentSource.STAFF, notes="", now=None
):
    """Book and confirm an appointment. Raises ``BookingError`` if not possible."""
    validate_new_appointment(
        patient=patient, dentist=dentist, service=service, start_at=start_at, now=now
    )
    appointment = Appointment(
        clinic_id=dentist.clinic_id,
        patient=patient,
        dentist=dentist,
        service=service,
        start_at=start_at,
        end_at=_end_for_service(service, start_at),
        status=AppointmentStatus.CONFIRMED,
        source=source,
        notes=notes,
    )
    _save(appointment)
    return appointment


def validate_reschedule(appointment, *, start_at, dentist=None, now=None):
    """Raise ``BookingError`` unless ``appointment`` can be moved as requested."""
    now = now or timezone.now()
    if appointment.status not in RESCHEDULABLE_STATUSES or appointment.start_at <= now:
        raise BookingError(BookingErrorCode.NOT_RESCHEDULABLE)
    dentist = dentist or appointment.dentist
    _validate_participants(dentist=dentist, service=appointment.service, patient=appointment.patient)
    _validate_time(
        dentist=dentist,
        patient=appointment.patient,
        start_at=start_at,
        end_at=_end_for_move(appointment, start_at),
        now=now,
        exclude_pk=appointment.pk,
    )


def reschedule_appointment(appointment, *, start_at, dentist=None, now=None):
    """
    Move an appointment to ``start_at`` (optionally to another dentist of the
    same clinic), keeping its duration. Returns the updated appointment.
    """
    with transaction.atomic():
        current = _lock(appointment)
        validate_reschedule(current, start_at=start_at, dentist=dentist, now=now)
        current.end_at = _end_for_move(current, start_at)
        current.start_at = start_at
        current.dentist = dentist or current.dentist
        current.status = AppointmentStatus.CONFIRMED
        _save(current, update_fields=["dentist", "start_at", "end_at", "status", "updated_at"])
    return current


def allowed_statuses(appointment):
    """The statuses ``appointment`` may be changed to."""
    return STATUS_TRANSITIONS[appointment.status]


def validate_status_change(appointment, status, *, now=None):
    """Raise ``BookingError`` unless ``appointment`` may change to ``status``."""
    now = now or timezone.now()
    if status not in allowed_statuses(appointment):
        raise BookingError(BookingErrorCode.INVALID_STATUS_CHANGE)
    if status == AppointmentStatus.CANCELLED and appointment.start_at <= now:
        raise BookingError(
            BookingErrorCode.INVALID_STATUS_CHANGE,
            _("An appointment that has started can no longer be cancelled."),
        )
    if status == AppointmentStatus.NO_SHOW and appointment.start_at > now:
        raise BookingError(
            BookingErrorCode.INVALID_STATUS_CHANGE,
            _("An appointment can only be marked as no-show after it has started."),
        )


def change_status(appointment, status, *, now=None):
    """Apply a status transition (see ``STATUS_TRANSITIONS``). Returns the updated appointment."""
    with transaction.atomic():
        current = _lock(appointment)
        validate_status_change(current, status, now=now)
        current.status = status
        _save(current, update_fields=["status", "updated_at"])
    return current


def cancel_appointment(appointment, *, now=None):
    """Cancel an appointment that has not started yet; its slot becomes free."""
    return change_status(appointment, AppointmentStatus.CANCELLED, now=now)


def normalize_reference(text):
    """``"abcd-efgh"`` -> ``"ABCDEFGH"``; ``None`` if it cannot be a booking reference."""
    candidate = "".join(ch for ch in str(text).upper() if ch not in " -")
    if len(candidate) == REFERENCE_LENGTH and all(ch in REFERENCE_ALPHABET for ch in candidate):
        return candidate
    return None


def find_appointment(clinic, reference):
    """The clinic's appointment with this booking reference, or ``None``."""
    reference = normalize_reference(reference)
    if reference is None:
        return None
    return (
        Appointment.objects.select_related("service", "dentist__staff_member", "patient")
        .filter(clinic=clinic, reference=reference)
        .first()
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_participants(*, dentist, service, patient=None):
    if service.clinic_id != dentist.clinic_id or (
        patient is not None and patient.clinic_id != dentist.clinic_id
    ):
        raise BookingError(BookingErrorCode.CLINIC_MISMATCH)
    if not dentist.clinic.is_active:
        raise BookingError(BookingErrorCode.CLINIC_INACTIVE)
    if not (dentist.is_bookable and dentist.staff_member.is_active):
        raise BookingError(BookingErrorCode.DENTIST_UNAVAILABLE)
    if not service.is_active:
        raise BookingError(BookingErrorCode.SERVICE_UNAVAILABLE)
    if not DentistService.objects.filter(dentist=dentist, service=service).exists():
        raise BookingError(BookingErrorCode.SERVICE_NOT_OFFERED)
    if patient is not None and not patient.is_active:
        raise BookingError(BookingErrorCode.PATIENT_INACTIVE)


def _validate_time(*, dentist, patient, start_at, end_at, now, exclude_pk=None):
    if timezone.is_naive(start_at):
        raise BookingError(BookingErrorCode.INVALID_TIME)
    if start_at < now:
        raise BookingError(BookingErrorCode.IN_THE_PAST)

    tz = _clinic_timezone(dentist)
    first_day = start_at.astimezone(tz).date()
    last_day = end_at.astimezone(tz).date()
    working = _working_periods(dentist, tz, first_day, last_day)
    if not any(p_start <= start_at and end_at <= p_end for p_start, p_end in working):
        raise BookingError(BookingErrorCode.OUTSIDE_WORKING_HOURS)
    if _time_off(dentist, start_at, end_at).exists():
        raise BookingError(BookingErrorCode.TIME_OFF)
    code = _conflict(dentist=dentist, patient=patient, start_at=start_at, end_at=end_at, exclude_pk=exclude_pk)
    if code:
        raise BookingError(code)


def _conflict(*, dentist, patient, start_at, end_at, exclude_pk):
    """Overlap pre-check for clear errors; the database constraint is authoritative."""
    others = _active_appointments(start_at, end_at).exclude(pk=exclude_pk)
    if others.filter(dentist=dentist).exists():
        return BookingErrorCode.SLOT_TAKEN
    if others.filter(patient=patient).exists():
        return BookingErrorCode.PATIENT_BUSY
    return None


def _clinic_timezone(dentist):
    return ZoneInfo(dentist.clinic.timezone)


def _working_periods(dentist, tz, first_day, last_day):
    """
    The dentist's working periods on the given local dates as sorted, merged
    UTC intervals. Adjacent blocks (09:00–12:00, 12:00–17:00) merge into one.
    """
    blocks = {}
    for weekday, start_time, end_time in WorkingHours.objects.filter(dentist=dentist).values_list(
        "weekday", "start_time", "end_time"
    ):
        blocks.setdefault(weekday, []).append((start_time, end_time))

    periods = []
    day = first_day
    while day <= last_day:
        for start_time, end_time in blocks.get(day.weekday(), []):
            periods.append((_to_utc(day, start_time, tz), _to_utc(day, end_time, tz)))
        day += timedelta(days=1)

    merged = []
    for start, end in sorted(periods):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _to_utc(day, wall_time, tz):
    return datetime.combine(day, wall_time, tzinfo=tz).astimezone(dt_timezone.utc)


def _time_off(dentist, start_at, end_at):
    """Time off of the dentist, or clinic-wide closures, overlapping [start_at, end_at)."""
    return TimeOff.objects.filter(
        Q(dentist=dentist) | Q(dentist__isnull=True),
        clinic_id=dentist.clinic_id,
        start_at__lt=end_at,
        end_at__gt=start_at,
    )


def _active_appointments(start_at, end_at):
    """Appointments that occupy time overlapping [start_at, end_at)."""
    return Appointment.objects.filter(start_at__lt=end_at, end_at__gt=start_at).exclude(
        status__in=SLOT_RELEASING_STATUSES
    )


def _end_for_service(service, start_at):
    return start_at + timedelta(minutes=service.duration_minutes)


def _end_for_move(appointment, start_at):
    return start_at + (appointment.end_at - appointment.start_at)


def _lock(appointment):
    """Re-read the appointment with a row lock, so concurrent changes queue up."""
    return (
        Appointment.objects.select_for_update(of=("self",))
        .select_related("clinic", "patient", "service", "dentist__clinic", "dentist__staff_member")
        .get(pk=appointment.pk)
    )


def _save(appointment, **save_kwargs):
    """
    Save in a savepoint and translate double-booking violations to BookingError.

    Two transactions writing conflicting appointments at the same moment can
    wait for each other inside PostgreSQL's exclusion-constraint check; the
    deadlock detector then aborts one of them. Retrying lets that one wait for
    the other transaction and get the real outcome (usually SLOT_TAKEN).
    """
    for attempt in range(1, _SAVE_ATTEMPTS + 1):
        try:
            with transaction.atomic():
                appointment.save(**save_kwargs)
            return
        except OperationalError as exc:
            if getattr(exc.__cause__, "sqlstate", None) != _DEADLOCK_SQLSTATE:
                raise
            if attempt == _SAVE_ATTEMPTS:
                raise
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
            if constraint not in _CONSTRAINT_ERRORS:
                raise
            raise BookingError(_CONSTRAINT_ERRORS[constraint]) from exc
