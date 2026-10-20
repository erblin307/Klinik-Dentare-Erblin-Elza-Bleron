"""Minimal builders for test data. All data is fictitious."""

import itertools
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from apps.appointments.models import Appointment
from apps.catalog.models import Service
from apps.clinics.models import Clinic
from apps.patients.models import Patient
from apps.scheduling.models import WorkingHours
from apps.staff.models import Dentist, DentistService, StaffMember, StaffRole

_sequence = itertools.count(1)

# A fixed Monday in the future, so tests never depend on the current date.
MONDAY_9AM = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)


def make_clinic(**fields):
    n = next(_sequence)
    defaults = {"name": f"Test Clinic {n}", "slug": f"test-clinic-{n}", "timezone": "Europe/Tirane"}
    return Clinic.objects.create(**{**defaults, **fields})


def make_staff_member(clinic, **fields):
    n = next(_sequence)
    defaults = {"first_name": "Staff", "last_name": f"Member {n}", "role": StaffRole.RECEPTIONIST}
    return StaffMember.objects.create(clinic=clinic, **{**defaults, **fields})


def make_dentist(clinic, **fields):
    staff_member = make_staff_member(clinic, role=StaffRole.DENTIST)
    return Dentist.objects.create(clinic=clinic, staff_member=staff_member, **fields)


def make_service(clinic, **fields):
    n = next(_sequence)
    defaults = {"name": f"Service {n}", "duration_minutes": 30}
    return Service.objects.create(clinic=clinic, **{**defaults, **fields})


def make_patient(clinic, **fields):
    n = next(_sequence)
    defaults = {"first_name": "Test", "last_name": f"Patient {n}"}
    return Patient.objects.create(clinic=clinic, **{**defaults, **fields})


def make_appointment(*, dentist, patient, service, start_at, minutes=30, **fields):
    fields.setdefault("clinic", dentist.clinic)
    return Appointment.objects.create(
        dentist=dentist,
        patient=patient,
        service=service,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=minutes),
        **fields,
    )


def local_time(clinic, year, month, day, hour, minute=0):
    """An aware datetime given as wall-clock time in the clinic's time zone."""
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(clinic.timezone))


def make_bookable_dentist(clinic, *, services=(), weekdays=range(5), blocks=((9, 13), (14, 18))):
    """A dentist working the given blocks (default 09–13 and 14–18, i.e. a lunch
    break) on the given weekdays (default Monday–Friday), offering ``services``."""
    dentist = make_dentist(clinic)
    for weekday in weekdays:
        for start_hour, end_hour in blocks:
            WorkingHours.objects.create(
                clinic=clinic,
                dentist=dentist,
                weekday=weekday,
                start_time=time(start_hour),
                end_time=time(end_hour),
            )
    for service in services:
        DentistService.objects.create(clinic=clinic, dentist=dentist, service=service)
    return dentist
