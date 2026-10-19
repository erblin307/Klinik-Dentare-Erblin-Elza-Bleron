from datetime import time, timedelta

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.appointments.models import Appointment
from apps.core.constraints import SameClinicConstraint
from apps.scheduling.models import TimeOff, Weekday, WorkingHours
from apps.staff.models import Dentist, DentistService, StaffRole

from .factories import (
    MONDAY_9AM,
    make_appointment,
    make_clinic,
    make_dentist,
    make_patient,
    make_service,
    make_staff_member,
)
from .utils import IntegrityTestCase

# Models that are not owned by a single clinic.
GLOBAL_MODELS = {"accounts.User", "clinics.Clinic"}


def clinic_scoped_models():
    return [
        model
        for model in apps.get_models()
        if model.__module__.startswith("apps.") and model._meta.label not in GLOBAL_MODELS
    ]


class TenantSchemaRulesTests(SimpleTestCase):
    """Guards that keep future models inside the clinic isolation rules."""

    def test_every_project_table_has_a_required_clinic_column(self):
        for model in clinic_scoped_models():
            with self.subTest(model=model._meta.label):
                field = model._meta.get_field("clinic")
                self.assertEqual(field.related_model._meta.label, "clinics.Clinic")
                self.assertFalse(field.null)

    def test_every_relation_between_clinic_scoped_models_is_same_clinic_constrained(self):
        scoped = set(clinic_scoped_models())
        for model in scoped:
            constrained = {
                c.field for c in model._meta.constraints if isinstance(c, SameClinicConstraint)
            }
            for field in model._meta.concrete_fields:
                if field.is_relation and field.related_model in scoped:
                    with self.subTest(field=f"{model._meta.label}.{field.name}"):
                        self.assertIn(field.name, constrained)


class CrossClinicReferenceTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.other = make_clinic()
        cls.dentist = make_dentist(cls.clinic)
        cls.patient = make_patient(cls.clinic)
        cls.service = make_service(cls.clinic)
        cls.foreign_dentist = make_dentist(cls.other)
        cls.foreign_patient = make_patient(cls.other)
        cls.foreign_service = make_service(cls.other)

    def appointment(self, **overrides):
        fields = {
            "dentist": self.dentist,
            "patient": self.patient,
            "service": self.service,
            "start_at": MONDAY_9AM,
            "clinic": self.clinic,
        }
        return make_appointment(**{**fields, **overrides})

    def test_appointment_rejects_patient_dentist_or_service_of_another_clinic(self):
        cases = {
            "patient": self.foreign_patient,
            "dentist": self.foreign_dentist,
            "service": self.foreign_service,
        }
        for field, foreign in cases.items():
            with self.subTest(field=field):
                with self.assertViolates(f"appointments_appointment_{field}_same_clinic"):
                    self.appointment(**{field: foreign})

    def test_dentist_profile_rejects_staff_member_of_another_clinic(self):
        staff_member = make_staff_member(self.other, role=StaffRole.DENTIST)
        with self.assertViolates("staff_dentist_staff_member_same_clinic"):
            Dentist.objects.create(clinic=self.clinic, staff_member=staff_member)

    def test_dentist_service_link_rejects_other_clinic(self):
        with self.assertViolates("staff_dentistservice_service_same_clinic"):
            DentistService.objects.create(
                clinic=self.clinic, dentist=self.dentist, service=self.foreign_service
            )
        with self.assertViolates("staff_dentistservice_dentist_same_clinic"):
            DentistService.objects.create(
                clinic=self.clinic, dentist=self.foreign_dentist, service=self.service
            )

    def test_schedules_and_time_off_reject_dentist_of_another_clinic(self):
        with self.assertViolates("scheduling_workinghours_dentist_same_clinic"):
            WorkingHours.objects.create(
                clinic=self.clinic,
                dentist=self.foreign_dentist,
                weekday=Weekday.MONDAY,
                start_time=time(9),
                end_time=time(13),
            )
        with self.assertViolates("scheduling_timeoff_dentist_same_clinic"):
            TimeOff.objects.create(
                clinic=self.clinic,
                dentist=self.foreign_dentist,
                start_at=MONDAY_9AM,
                end_at=MONDAY_9AM + timedelta(days=1),
            )

    def test_linked_records_cannot_be_moved_to_another_clinic(self):
        self.appointment()
        with self.assertViolates("appointments_appointment_dentist_same_clinic"):
            Dentist.objects.filter(pk=self.dentist.pk).update(clinic=self.other)

    def test_full_clean_reports_cross_clinic_reference_on_the_field(self):
        appointment = Appointment(
            clinic=self.clinic,
            dentist=self.foreign_dentist,
            patient=self.patient,
            service=self.service,
            start_at=MONDAY_9AM,
            end_at=MONDAY_9AM + timedelta(minutes=30),
        )
        with self.assertRaises(ValidationError) as ctx:
            appointment.full_clean()
        self.assertEqual(
            ctx.exception.message_dict,
            {"dentist": ["The selected record belongs to a different clinic."]},
        )
