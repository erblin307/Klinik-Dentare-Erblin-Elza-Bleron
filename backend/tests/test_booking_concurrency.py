"""
Concurrent bookings with real PostgreSQL transactions: each thread uses its
own database connection, so these tests use TransactionTestCase.
"""

import threading
import time

from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from apps.appointments.booking import BookingError, BookingErrorCode, create_appointment
from apps.appointments.models import Appointment

from .factories import local_time, make_bookable_dentist, make_clinic, make_patient, make_service

TIMEOUT = 10


def outcome(result):
    """"booked", a BookingErrorCode, or the unexpected exception itself."""
    if isinstance(result, Appointment):
        return "booked"
    return result.code if isinstance(result, BookingError) else result


def run_in_thread(target, results, key):
    def runner():
        try:
            results[key] = target()
        except Exception as exc:  # collected and asserted by the test
            results[key] = exc
        finally:
            connections.close_all()

    thread = threading.Thread(target=runner)
    thread.start()
    return thread


class ConcurrentBookingTests(TransactionTestCase):
    def setUp(self):
        self.clinic = make_clinic(timezone="Europe/Tirane")
        self.service = make_service(self.clinic)
        self.dentist = make_bookable_dentist(self.clinic, services=[self.service])
        self.colleague = make_bookable_dentist(self.clinic, services=[self.service])
        self.slot = local_time(self.clinic, 2030, 1, 7, 10)

    def book(self, patient, dentist=None):
        return create_appointment(
            patient=patient, dentist=dentist or self.dentist, service=self.service, start_at=self.slot
        )

    def wait_for_lock_wait(self):
        """Wait until some session of this database is blocked on a lock."""
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
                if cursor.fetchone()[0]:
                    return
            time.sleep(0.02)
        self.fail("The second booking never waited on the first one.")

    def test_uncommitted_booking_blocks_a_racing_one_which_then_fails(self):
        first_inserted, release_first = threading.Event(), threading.Event()
        results = {}

        def first():
            with transaction.atomic():
                appointment = self.book(make_patient(self.clinic))
                first_inserted.set()
                release_first.wait(TIMEOUT)  # keep the transaction open
            return appointment

        def second():
            first_inserted.wait(TIMEOUT)
            # The pre-check cannot see the uncommitted row, so this reaches
            # the INSERT, which PostgreSQL blocks until the first commits.
            return self.book(make_patient(self.clinic))

        threads = [run_in_thread(first, results, "first"), run_in_thread(second, results, "second")]
        first_inserted.wait(TIMEOUT)
        self.wait_for_lock_wait()
        release_first.set()
        for thread in threads:
            thread.join(TIMEOUT)

        self.assertEqual(outcome(results["first"]), "booked")
        self.assertEqual(outcome(results["second"]), BookingErrorCode.SLOT_TAKEN)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_only_one_of_many_simultaneous_requests_gets_the_slot(self):
        patients = [make_patient(self.clinic) for _ in range(6)]
        barrier = threading.Barrier(len(patients))
        results = {}

        def attempt(patient):
            def target():
                barrier.wait(TIMEOUT)
                return self.book(patient)

            return target

        threads = [run_in_thread(attempt(p), results, p.pk) for p in patients]
        for thread in threads:
            thread.join(TIMEOUT)

        outcomes = sorted(map(outcome, results.values()))
        self.assertEqual(outcomes, ["booked"] + [BookingErrorCode.SLOT_TAKEN] * (len(patients) - 1))
        self.assertEqual(Appointment.objects.count(), 1)

    def test_same_patient_cannot_be_booked_twice_at_once_with_different_dentists(self):
        patient = make_patient(self.clinic)
        barrier = threading.Barrier(2)
        results = {}

        def attempt(dentist):
            def target():
                barrier.wait(TIMEOUT)
                return self.book(patient, dentist=dentist)

            return target

        threads = [
            run_in_thread(attempt(self.dentist), results, "a"),
            run_in_thread(attempt(self.colleague), results, "b"),
        ]
        for thread in threads:
            thread.join(TIMEOUT)

        outcomes = sorted(map(outcome, results.values()))
        self.assertEqual(outcomes, ["booked", BookingErrorCode.PATIENT_BUSY])
        self.assertEqual(Appointment.objects.count(), 1)
