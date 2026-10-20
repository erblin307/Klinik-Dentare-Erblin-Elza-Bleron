from datetime import time, timedelta

from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.knowledge.models import KnowledgeEntry
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

CORE_MODELS = {
    "accounts.User",
    "clinics.Clinic",
    "staff.StaffMember",
    "staff.Dentist",
    "catalog.Service",
    "scheduling.WorkingHours",
    "scheduling.TimeOff",
    "patients.Patient",
    "appointments.Appointment",
    "knowledge.KnowledgeEntry",
}


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # One object per registered model, so every change page can be rendered.
        cls.superuser = User.objects.create_superuser(username="admin", password="unused")
        Group.objects.create(name="Reception")
        cls.clinic = make_clinic()
        dentist = make_dentist(cls.clinic)
        make_appointment(
            dentist=dentist,
            patient=make_patient(cls.clinic),
            service=make_service(cls.clinic),
            start_at=MONDAY_9AM,
        )
        WorkingHours.objects.create(
            clinic=cls.clinic,
            dentist=dentist,
            weekday=Weekday.MONDAY,
            start_time=time(9),
            end_time=time(17),
        )
        TimeOff.objects.create(
            clinic=cls.clinic, start_at=MONDAY_9AM, end_at=MONDAY_9AM + timedelta(days=1)
        )
        KnowledgeEntry.objects.create(clinic=cls.clinic, title="Parking", content="Free.")

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_core_models_are_registered(self):
        registered = {model._meta.label for model in admin.site._registry}
        self.assertLessEqual(CORE_MODELS, registered)

    def test_changelist_add_and_change_pages_render(self):
        for model in admin.site._registry:
            opts = model._meta
            prefix = f"admin:{opts.app_label}_{opts.model_name}"
            urls = {
                "changelist": reverse(f"{prefix}_changelist"),
                "add": reverse(f"{prefix}_add"),
                "change": reverse(f"{prefix}_change", args=[model.objects.first().pk]),
            }
            for view, url in urls.items():
                with self.subTest(model=opts.label, view=view):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def dentist_form(self, staff_member, service):
        return {
            "clinic": self.clinic.pk,
            "staff_member": staff_member.pk,
            "is_bookable": "on",
            "service_links-TOTAL_FORMS": "1",
            "service_links-INITIAL_FORMS": "0",
            "service_links-0-service": service.pk,
            "working_hours-TOTAL_FORMS": "1",
            "working_hours-INITIAL_FORMS": "0",
            "working_hours-0-weekday": "0",
            "working_hours-0-start_time": "09:00",
            "working_hours-0-end_time": "13:00",
        }

    def test_dentist_inlines_inherit_the_dentist_clinic(self):
        staff_member = make_staff_member(self.clinic, role=StaffRole.DENTIST)
        service = make_service(self.clinic)
        response = self.client.post(
            reverse("admin:staff_dentist_add"), self.dentist_form(staff_member, service)
        )
        self.assertEqual(response.status_code, 302)
        link = DentistService.objects.get(dentist__staff_member=staff_member)
        self.assertEqual(link.clinic, self.clinic)
        hours = WorkingHours.objects.get(dentist__staff_member=staff_member)
        self.assertEqual((hours.clinic, hours.start_time), (self.clinic, time(9)))

    def test_dentist_service_inline_rejects_other_clinic_service_with_form_error(self):
        staff_member = make_staff_member(self.clinic, role=StaffRole.DENTIST)
        foreign_service = make_service(make_clinic())
        response = self.client.post(
            reverse("admin:staff_dentist_add"), self.dentist_form(staff_member, foreign_service)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The selected record belongs to a different clinic.")
        self.assertFalse(Dentist.objects.filter(staff_member=staff_member).exists())
