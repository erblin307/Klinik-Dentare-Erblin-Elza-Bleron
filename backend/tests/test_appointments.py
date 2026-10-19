from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from apps.appointments.models import Appointment, AppointmentStatus

from .factories import (
    MONDAY_9AM,
    make_appointment,
    make_clinic,
    make_dentist,
    make_patient,
    make_service,
)
from .utils import IntegrityTestCase

DENTIST_OVERLAP = "appointments_no_dentist_overlap"
PATIENT_OVERLAP = "appointments_no_patient_overlap"


class AppointmentOverlapTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.dentist = make_dentist(cls.clinic)
        cls.other_dentist = make_dentist(cls.clinic)
        cls.patient = make_patient(cls.clinic)
        cls.other_patient = make_patient(cls.clinic)
        cls.service = make_service(cls.clinic)
        # Existing booking: 09:00–09:30.
        cls.existing = make_appointment(
            dentist=cls.dentist,
            patient=cls.patient,
            service=cls.service,
            start_at=MONDAY_9AM,
            status=AppointmentStatus.CONFIRMED,
        )

    def book(self, *, start_offset, minutes=30, dentist=None, patient=None, **fields):
        return make_appointment(
            dentist=dentist or self.dentist,
            patient=patient or self.other_patient,
            service=self.service,
            start_at=MONDAY_9AM + timedelta(minutes=start_offset),
            minutes=minutes,
            **fields,
        )

    def test_dentist_cannot_be_double_booked_for_same_slot(self):
        with self.assertViolates(DENTIST_OVERLAP):
            self.book(start_offset=0)

    def test_partial_overlaps_are_rejected(self):
        for start_offset, minutes in [(-15, 30), (15, 30), (10, 10), (-30, 90)]:
            with self.subTest(start_offset=start_offset, minutes=minutes):
                with self.assertViolates(DENTIST_OVERLAP):
                    self.book(start_offset=start_offset, minutes=minutes)

    def test_back_to_back_appointments_are_allowed(self):
        self.book(start_offset=30)  # 09:30–10:00
        self.book(start_offset=-30, patient=make_patient(self.clinic))  # 08:30–09:00
        self.assertEqual(Appointment.objects.filter(dentist=self.dentist).count(), 3)

    def test_other_dentist_can_be_booked_at_same_time(self):
        self.book(start_offset=0, dentist=self.other_dentist)

    def test_patient_cannot_be_double_booked_with_another_dentist(self):
        with self.assertViolates(PATIENT_OVERLAP):
            self.book(start_offset=0, dentist=self.other_dentist, patient=self.patient)

    def test_cancelled_and_no_show_appointments_release_the_slot(self):
        for status in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
            with self.subTest(status=status):
                Appointment.objects.filter(pk=self.existing.pk).update(status=status)
                replacement = self.book(start_offset=0)
                replacement.delete()

    def test_reactivating_a_cancelled_appointment_into_a_taken_slot_is_rejected(self):
        Appointment.objects.filter(pk=self.existing.pk).update(
            status=AppointmentStatus.CANCELLED
        )
        self.book(start_offset=0, status=AppointmentStatus.CONFIRMED)
        with self.assertViolates(DENTIST_OVERLAP):
            Appointment.objects.filter(pk=self.existing.pk).update(
                status=AppointmentStatus.CONFIRMED
            )

    def test_moving_an_appointment_onto_a_taken_slot_is_rejected(self):
        later = self.book(start_offset=60)
        later.start_at, later.end_at = self.existing.start_at, self.existing.end_at
        with self.assertViolates(DENTIST_OVERLAP):
            later.save()

    def test_full_clean_reports_overlap_as_validation_error(self):
        appointment = Appointment(
            clinic=self.clinic,
            dentist=self.dentist,
            patient=self.other_patient,
            service=self.service,
            start_at=MONDAY_9AM + timedelta(minutes=15),
            end_at=MONDAY_9AM + timedelta(minutes=45),
        )
        with self.assertRaisesMessage(
            ValidationError, "The dentist already has an appointment at this time."
        ):
            appointment.full_clean()


class AppointmentIntegrityTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.dentist = make_dentist(cls.clinic)
        cls.patient = make_patient(cls.clinic)
        cls.service = make_service(cls.clinic)

    def test_end_must_be_after_start(self):
        for minutes in [0, -30]:
            with self.subTest(minutes=minutes):
                with self.assertViolates("appointments_appointment_end_after_start"):
                    make_appointment(
                        dentist=self.dentist,
                        patient=self.patient,
                        service=self.service,
                        start_at=MONDAY_9AM,
                        minutes=minutes,
                    )

    def test_unknown_status_and_source_are_rejected(self):
        appointment = make_appointment(
            dentist=self.dentist, patient=self.patient, service=self.service, start_at=MONDAY_9AM
        )
        rows = Appointment.objects.filter(pk=appointment.pk)
        with self.assertViolates("appointments_appointment_status_valid"):
            rows.update(status="lost")
        with self.assertViolates("appointments_appointment_source_valid"):
            rows.update(source="fax")

    def test_patients_dentists_and_services_with_appointments_cannot_be_deleted(self):
        make_appointment(
            dentist=self.dentist, patient=self.patient, service=self.service, start_at=MONDAY_9AM
        )
        for obj in [self.patient, self.dentist, self.service]:
            with self.subTest(model=type(obj).__name__):
                with self.assertRaises(ProtectedError):
                    obj.delete()
