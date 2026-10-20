from datetime import date, datetime, time, timedelta, timezone

from django.test import TestCase
from django.utils import timezone as django_timezone

from apps.appointments.booking import BookingErrorCode, get_available_slots
from apps.appointments.models import AppointmentStatus
from apps.scheduling.models import TimeOff, WorkingHours

from .factories import (
    local_time,
    make_appointment,
    make_bookable_dentist,
    make_clinic,
    make_patient,
    make_service,
)
from .utils import BookingAssertionsMixin

MONDAY = date(2030, 1, 7)
SATURDAY = date(2030, 1, 12)
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def local_starts(slots):
    return [slot.start.strftime("%H:%M") for slot in slots]


class AvailabilityTests(BookingAssertionsMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(timezone="Europe/Tirane")
        cls.checkup = make_service(cls.clinic, duration_minutes=30)
        cls.implant = make_service(cls.clinic, duration_minutes=60)
        # Monday–Friday 09:00–13:00 and 14:00–18:00 (lunch break 13–14).
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.checkup, cls.implant])
        cls.patient = make_patient(cls.clinic)

    def slots(self, service=None, day=MONDAY, **kwargs):
        kwargs.setdefault("now", NOW)
        return get_available_slots(self.dentist, service or self.checkup, day, **kwargs)

    def test_slots_follow_working_hours_and_skip_the_break(self):
        starts = local_starts(self.slots())
        self.assertEqual(starts[0], "09:00")
        self.assertEqual(starts[-1], "17:30")
        self.assertIn("12:30", starts)
        self.assertNotIn("12:45", starts)  # would end 13:15, inside the break
        self.assertFalse([s for s in starts if "13:00" <= s < "14:00"])
        self.assertEqual(len(starts), 30)

    def test_slot_length_follows_service_duration(self):
        slots = self.slots(service=self.implant)
        self.assertTrue(all(s.end - s.start == timedelta(hours=1) for s in slots))
        starts = local_starts(slots)
        self.assertIn("12:00", starts)
        self.assertNotIn("12:15", starts)
        self.assertEqual(starts[-1], "17:00")

    def test_step_controls_slot_spacing(self):
        starts = local_starts(self.slots(step_minutes=30))
        self.assertEqual(starts[:3], ["09:00", "09:30", "10:00"])
        self.assertEqual(len(starts), 16)

    def test_no_slots_on_days_without_working_hours(self):
        self.assertEqual(self.slots(day=SATURDAY), [])

    def test_active_appointments_block_overlapping_slots(self):
        make_appointment(
            dentist=self.dentist,
            patient=self.patient,
            service=self.checkup,
            start_at=local_time(self.clinic, 2030, 1, 7, 10),
            status=AppointmentStatus.CONFIRMED,
        )
        starts = local_starts(self.slots())
        for blocked in ["09:45", "10:00", "10:15"]:
            self.assertNotIn(blocked, starts)
        self.assertIn("09:30", starts)
        self.assertIn("10:30", starts)

    def test_cancelled_and_no_show_appointments_do_not_block(self):
        for status in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
            make_appointment(
                dentist=self.dentist,
                patient=make_patient(self.clinic),
                service=self.checkup,
                start_at=local_time(self.clinic, 2030, 1, 7, 10),
                status=status,
            )
        self.assertIn("10:00", local_starts(self.slots()))

    def test_dentist_time_off_blocks_slots(self):
        TimeOff.objects.create(
            clinic=self.clinic,
            dentist=self.dentist,
            start_at=local_time(self.clinic, 2030, 1, 7, 15),
            end_at=local_time(self.clinic, 2030, 1, 7, 16),
        )
        starts = local_starts(self.slots())
        self.assertFalse([s for s in starts if "14:45" <= s < "16:00"])
        self.assertIn("14:30", starts)
        self.assertIn("16:00", starts)

    def test_full_day_off_and_clinic_closure_block_the_whole_day(self):
        TimeOff.objects.create(  # dentist's day off on Monday
            clinic=self.clinic,
            dentist=self.dentist,
            start_at=local_time(self.clinic, 2030, 1, 7, 0),
            end_at=local_time(self.clinic, 2030, 1, 8, 0),
        )
        TimeOff.objects.create(  # clinic closed on Tuesday (no dentist)
            clinic=self.clinic,
            start_at=local_time(self.clinic, 2030, 1, 8, 0),
            end_at=local_time(self.clinic, 2030, 1, 9, 0),
        )
        self.assertEqual(self.slots(day=MONDAY), [])
        self.assertEqual(self.slots(day=date(2030, 1, 8)), [])
        self.assertEqual(len(self.slots(day=date(2030, 1, 9))), 30)

    def test_time_off_of_another_dentist_or_clinic_does_not_block(self):
        colleague = make_bookable_dentist(self.clinic)
        other_clinic = make_clinic()
        whole_day = {
            "start_at": local_time(self.clinic, 2030, 1, 7, 0),
            "end_at": local_time(self.clinic, 2030, 1, 8, 0),
        }
        TimeOff.objects.create(clinic=self.clinic, dentist=colleague, **whole_day)
        TimeOff.objects.create(clinic=other_clinic, **whole_day)
        self.assertEqual(len(self.slots()), 30)

    def test_past_slots_are_not_offered(self):
        now = local_time(self.clinic, 2030, 1, 7, 11, 5)
        self.assertEqual(local_starts(self.slots(now=now))[0], "11:15")

    def test_multi_day_range(self):
        slots = self.slots(day=MONDAY, end_date=date(2030, 1, 13))
        self.assertEqual(len(slots), 5 * 30)
        self.assertEqual({s.start.weekday() for s in slots}, {0, 1, 2, 3, 4})

    def test_adjacent_working_blocks_merge(self):
        dentist = make_bookable_dentist(
            self.clinic, services=[self.implant], weekdays=[0], blocks=[(9, 12), (12, 14)]
        )
        starts = local_starts(get_available_slots(dentist, self.implant, MONDAY, now=NOW))
        self.assertIn("11:30", starts)  # 11:30–12:30 spans both blocks
        self.assertEqual(starts[-1], "13:00")

    def test_invalid_ranges_are_rejected(self):
        with self.assertBookingError(BookingErrorCode.INVALID_RANGE):
            self.slots(day=MONDAY, end_date=MONDAY - timedelta(days=1))
        with self.assertBookingError(BookingErrorCode.INVALID_RANGE):
            self.slots(day=MONDAY, end_date=MONDAY + timedelta(days=31))

    def test_unbookable_dentist_and_unoffered_or_inactive_service(self):
        with self.assertBookingError(BookingErrorCode.SERVICE_NOT_OFFERED):
            self.slots(service=make_service(self.clinic))
        self.implant.is_active = False
        with self.assertBookingError(BookingErrorCode.SERVICE_UNAVAILABLE):
            self.slots(service=self.implant)
        self.dentist.is_bookable = False
        with self.assertBookingError(BookingErrorCode.DENTIST_UNAVAILABLE):
            self.slots()

    def test_service_of_another_clinic_is_rejected(self):
        with self.assertBookingError(BookingErrorCode.CLINIC_MISMATCH):
            self.slots(service=make_service(make_clinic()))


class TimezoneTests(TestCase):
    def first_slot_utc(self, clinic_tz, day):
        clinic = make_clinic(timezone=clinic_tz)
        service = make_service(clinic)
        dentist = make_bookable_dentist(clinic, services=[service], weekdays=range(7))
        slots = get_available_slots(dentist, service, day, now=NOW)
        return slots[0].start, slots[0].start.astimezone(timezone.utc)

    def test_slots_carry_the_clinic_time_zone(self):
        local, utc = self.first_slot_utc("Europe/Tirane", MONDAY)
        self.assertEqual(str(local.tzinfo), "Europe/Tirane")
        self.assertEqual(utc, datetime(2030, 1, 7, 8, 0, tzinfo=timezone.utc))  # CET, UTC+1

    def test_daylight_saving_change_keeps_local_working_hours(self):
        # Europe switches to summer time on Sunday 2030-03-31.
        _, before = self.first_slot_utc("Europe/Tirane", date(2030, 3, 25))
        _, after = self.first_slot_utc("Europe/Tirane", date(2030, 4, 1))
        self.assertEqual(before.time(), time(8, 0))  # 09:00 CET
        self.assertEqual(after.time(), time(7, 0))  # 09:00 CEST

    def test_result_does_not_depend_on_the_active_time_zone(self):
        expected = datetime(2030, 1, 7, 14, 0, tzinfo=timezone.utc)  # 09:00 EST
        with django_timezone.override("Asia/Tokyo"):
            _, utc = self.first_slot_utc("America/New_York", MONDAY)
        self.assertEqual(utc, expected)

    def test_dates_are_clinic_local_calendar_dates(self):
        # 09:00 on Monday in Auckland (UTC+13 in January) is Sunday 20:00 UTC.
        local, utc = self.first_slot_utc("Pacific/Auckland", MONDAY)
        self.assertEqual(local.date(), MONDAY)
        self.assertEqual(utc, datetime(2030, 1, 6, 20, 0, tzinfo=timezone.utc))


class WorkingHoursEdgeTests(TestCase):
    def test_dentist_without_working_hours_has_no_slots(self):
        clinic = make_clinic()
        service = make_service(clinic)
        dentist = make_bookable_dentist(clinic, services=[service], weekdays=[])
        self.assertFalse(WorkingHours.objects.filter(dentist=dentist).exists())
        self.assertEqual(get_available_slots(dentist, service, MONDAY, now=NOW), [])
