from datetime import date, datetime, timedelta, timezone
from unittest import mock

from django.db import transaction
from django.test import TestCase

from apps.appointments import booking
from apps.appointments.booking import (
    BookingErrorCode,
    cancel_appointment,
    change_status,
    create_appointment,
    get_available_slots,
    reschedule_appointment,
)
from apps.appointments.models import Appointment, AppointmentSource, AppointmentStatus
from apps.scheduling.models import TimeOff

from .factories import (
    local_time,
    make_appointment,
    make_bookable_dentist,
    make_clinic,
    make_patient,
    make_service,
)
from .utils import BookingAssertionsMixin

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


class BookingTestCase(BookingAssertionsMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(timezone="Europe/Tirane")
        cls.service = make_service(cls.clinic, duration_minutes=30)
        # Monday–Friday 09:00–13:00 and 14:00–18:00 clinic time.
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.service])
        cls.colleague = make_bookable_dentist(cls.clinic, services=[cls.service])
        cls.patient = make_patient(cls.clinic)
        cls.other_patient = make_patient(cls.clinic)

    def at(self, hour, minute=0, day=7):
        """Clinic time on Monday 2030-01-07 (or another January 2030 day)."""
        return local_time(self.clinic, 2030, 1, day, hour, minute)

    def book(self, start_at, *, patient=None, dentist=None, now=NOW, **kwargs):
        return create_appointment(
            patient=patient or self.patient,
            dentist=dentist or self.dentist,
            service=kwargs.pop("service", self.service),
            start_at=start_at,
            now=now,
            **kwargs,
        )


class CreateAppointmentTests(BookingTestCase):
    def test_valid_booking_is_confirmed_with_the_service_duration(self):
        appointment = self.book(self.at(10), source=AppointmentSource.CHATBOT)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(appointment.end_at - appointment.start_at, timedelta(minutes=30))
        self.assertEqual(appointment.clinic, self.clinic)
        self.assertEqual(appointment.source, AppointmentSource.CHATBOT)

    def test_every_offered_slot_can_be_booked(self):
        slots = get_available_slots(self.dentist, self.service, date(2030, 1, 7), now=NOW)
        patients = [make_patient(self.clinic) for _ in slots]
        for slot, patient in zip(slots[::2], patients):  # every other slot: no overlaps
            self.book(slot.start, patient=patient)

    def test_rejects_times_outside_working_hours(self):
        cases = {
            "before opening": self.at(8, 30),
            "in the lunch break": self.at(13),
            "running into the break": self.at(12, 45),
            "running past closing": self.at(17, 45),
            "on a Saturday": self.at(10, day=12),
        }
        for label, start in cases.items():
            with self.subTest(label), self.assertBookingError(BookingErrorCode.OUTSIDE_WORKING_HOURS):
                self.book(start)

    def test_rejects_dentist_time_off_and_clinic_closures(self):
        TimeOff.objects.create(
            clinic=self.clinic, dentist=self.dentist, start_at=self.at(10), end_at=self.at(11)
        )
        TimeOff.objects.create(clinic=self.clinic, start_at=self.at(0, day=8), end_at=self.at(0, day=9))
        with self.assertBookingError(BookingErrorCode.TIME_OFF):
            self.book(self.at(10, 45))
        with self.assertBookingError(BookingErrorCode.TIME_OFF):
            self.book(self.at(10, day=8))
        self.book(self.at(10), dentist=self.colleague)  # colleague is not away

    def test_rejects_past_and_naive_times(self):
        with self.assertBookingError(BookingErrorCode.IN_THE_PAST):
            self.book(self.at(10), now=self.at(10, 1))
        with self.assertBookingError(BookingErrorCode.INVALID_TIME):
            self.book(datetime(2030, 1, 7, 10, 0))

    def test_rejects_scheduling_conflicts(self):
        self.book(self.at(10))
        with self.assertBookingError(BookingErrorCode.SLOT_TAKEN):
            self.book(self.at(10, 15), patient=self.other_patient)
        with self.assertBookingError(BookingErrorCode.PATIENT_BUSY):
            self.book(self.at(10, 15), dentist=self.colleague)
        self.book(self.at(10, 30), patient=self.other_patient)  # back-to-back is fine

    def test_rejects_unavailable_participants(self):
        unoffered = make_service(self.clinic)
        with self.assertBookingError(BookingErrorCode.SERVICE_NOT_OFFERED):
            self.book(self.at(10), service=unoffered)
        inactive_patient = make_patient(self.clinic, is_active=False)
        with self.assertBookingError(BookingErrorCode.PATIENT_INACTIVE):
            self.book(self.at(10), patient=inactive_patient)
        self.clinic.is_active = False
        self.clinic.save()
        with self.assertBookingError(BookingErrorCode.CLINIC_INACTIVE):
            self.book(self.at(10))

    def test_rejects_participants_of_another_clinic(self):
        foreign_patient = make_patient(make_clinic())
        with self.assertBookingError(BookingErrorCode.CLINIC_MISMATCH):
            self.book(self.at(10), patient=foreign_patient)
        self.assertFalse(Appointment.objects.exists())

    def test_database_constraints_catch_conflicts_the_pre_check_missed(self):
        # Simulates a concurrent booking committed after our pre-check ran.
        self.book(self.at(10))
        with mock.patch.object(booking, "_conflict", return_value=None):
            with self.assertBookingError(BookingErrorCode.SLOT_TAKEN):
                self.book(self.at(10), patient=self.other_patient)
            with self.assertBookingError(BookingErrorCode.PATIENT_BUSY):
                self.book(self.at(10), dentist=self.colleague)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_a_failed_booking_leaves_the_callers_transaction_usable(self):
        self.book(self.at(10))
        with transaction.atomic(), mock.patch.object(booking, "_conflict", return_value=None):
            with self.assertBookingError(BookingErrorCode.SLOT_TAKEN):
                self.book(self.at(10), patient=self.other_patient)
            self.book(self.at(11), patient=self.other_patient)
        self.assertEqual(Appointment.objects.count(), 2)


class CancellationTests(BookingTestCase):
    def test_cancelling_frees_the_slot(self):
        appointment = self.book(self.at(10))
        cancelled = cancel_appointment(appointment, now=NOW)
        self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED)
        self.book(self.at(10), patient=self.other_patient)
        slots = get_available_slots(self.dentist, self.service, date(2030, 1, 7), now=NOW)
        self.assertNotIn(self.at(10), [slot.start for slot in slots])

    def test_cannot_cancel_twice_after_start_or_when_final(self):
        appointment = self.book(self.at(10))
        with self.assertBookingError(BookingErrorCode.INVALID_STATUS_CHANGE):
            cancel_appointment(appointment, now=self.at(10))
        cancel_appointment(appointment, now=NOW)
        with self.assertBookingError(BookingErrorCode.INVALID_STATUS_CHANGE):
            cancel_appointment(appointment, now=NOW)
        completed = self.book(self.at(11))
        Appointment.objects.filter(pk=completed.pk).update(status=AppointmentStatus.COMPLETED)
        with self.assertBookingError(BookingErrorCode.INVALID_STATUS_CHANGE):
            cancel_appointment(completed, now=NOW)


class StatusChangeTests(BookingTestCase):
    def test_attendance_flow(self):
        appointment = self.book(self.at(10))
        appointment = change_status(appointment, AppointmentStatus.CHECKED_IN, now=self.at(9, 55))
        appointment = change_status(appointment, AppointmentStatus.COMPLETED, now=self.at(10, 30))
        self.assertEqual(appointment.status, AppointmentStatus.COMPLETED)

    def test_no_show_only_after_start(self):
        appointment = self.book(self.at(10))
        with self.assertBookingError(BookingErrorCode.INVALID_STATUS_CHANGE):
            change_status(appointment, AppointmentStatus.NO_SHOW, now=self.at(9))
        change_status(appointment, AppointmentStatus.NO_SHOW, now=self.at(10, 15))

    def test_final_statuses_cannot_be_reopened(self):
        appointment = cancel_appointment(self.book(self.at(10)), now=NOW)
        with self.assertBookingError(BookingErrorCode.INVALID_STATUS_CHANGE):
            change_status(appointment, AppointmentStatus.CONFIRMED, now=NOW)


class RescheduleTests(BookingTestCase):
    def test_moves_the_appointment_and_frees_the_old_slot(self):
        appointment = self.book(self.at(10))
        moved = reschedule_appointment(appointment, start_at=self.at(15), now=NOW)
        self.assertEqual(moved.pk, appointment.pk)
        self.assertEqual((moved.start_at, moved.end_at), (self.at(15), self.at(15, 30)))
        self.assertEqual(moved.status, AppointmentStatus.CONFIRMED)
        self.book(self.at(10), patient=self.other_patient)

    def test_may_overlap_its_own_current_time(self):
        appointment = self.book(self.at(10))
        moved = reschedule_appointment(appointment, start_at=self.at(10, 15), now=NOW)
        self.assertEqual(moved.start_at, self.at(10, 15))

    def test_keeps_a_custom_duration(self):
        appointment = self.book(self.at(10))
        Appointment.objects.filter(pk=appointment.pk).update(end_at=self.at(10, 45))
        moved = reschedule_appointment(appointment, start_at=self.at(15), now=NOW)
        self.assertEqual(moved.end_at, self.at(15, 45))

    def test_rejects_conflicts_unavailable_hours_and_time_off(self):
        appointment = self.book(self.at(10))
        self.book(self.at(11), patient=self.other_patient)
        TimeOff.objects.create(
            clinic=self.clinic, dentist=self.dentist, start_at=self.at(15), end_at=self.at(16)
        )
        cases = {
            BookingErrorCode.SLOT_TAKEN: self.at(11, 15),
            BookingErrorCode.OUTSIDE_WORKING_HOURS: self.at(13, 15),
            BookingErrorCode.TIME_OFF: self.at(15, 30),
            BookingErrorCode.IN_THE_PAST: datetime(2029, 12, 31, 9, tzinfo=timezone.utc),
        }
        for code, start in cases.items():
            with self.subTest(code=code), self.assertBookingError(code):
                reschedule_appointment(appointment, start_at=start, now=NOW)
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, self.at(10))

    def test_can_move_to_another_dentist_of_the_clinic(self):
        appointment = self.book(self.at(10))
        moved = reschedule_appointment(
            appointment, start_at=self.at(10), dentist=self.colleague, now=NOW
        )
        self.assertEqual(moved.dentist, self.colleague)
        other_service = make_service(self.clinic)
        non_performer = make_bookable_dentist(self.clinic, services=[other_service])
        with self.assertBookingError(BookingErrorCode.SERVICE_NOT_OFFERED):
            reschedule_appointment(appointment, start_at=self.at(10), dentist=non_performer, now=NOW)
        foreign = make_bookable_dentist(make_clinic(), services=[])
        with self.assertBookingError(BookingErrorCode.CLINIC_MISMATCH):
            reschedule_appointment(appointment, start_at=self.at(10), dentist=foreign, now=NOW)

    def test_cancelled_or_started_appointments_cannot_be_rescheduled(self):
        appointment = self.book(self.at(10))
        with self.assertBookingError(BookingErrorCode.NOT_RESCHEDULABLE):
            reschedule_appointment(appointment, start_at=self.at(15), now=self.at(10, 5))
        cancel_appointment(appointment, now=NOW)
        with self.assertBookingError(BookingErrorCode.NOT_RESCHEDULABLE):
            reschedule_appointment(appointment, start_at=self.at(15), now=NOW)

    def test_old_pending_bookings_are_confirmed_when_moved(self):
        appointment = make_appointment(
            dentist=self.dentist, patient=self.patient, service=self.service, start_at=self.at(10)
        )
        self.assertEqual(appointment.status, AppointmentStatus.PENDING)
        moved = reschedule_appointment(appointment, start_at=self.at(11), now=NOW)
        self.assertEqual(moved.status, AppointmentStatus.CONFIRMED)
