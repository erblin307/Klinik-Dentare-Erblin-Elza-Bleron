from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Service
from apps.staff.middleware import ClinicTimezoneMiddleware
from apps.staff.models import StaffRole

from .factories import (
    local_time,
    make_appointment,
    make_bookable_dentist,
    make_clinic,
    make_patient,
    make_service,
    make_staff_member,
)


def make_staff_user(username, *memberships):
    """A staff login with (clinic, role) memberships."""
    user = User.objects.create_user(username=username, password="unused", is_staff=True)
    for clinic, role in memberships:
        make_staff_member(clinic, role=role, user=user)
    return user


class ClinicAdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic_a = make_clinic(name="Alpha Dental", timezone="Europe/Tirane")
        cls.clinic_b = make_clinic(name="Bravo Dental", timezone="America/New_York")
        cls.patient_a = make_patient(cls.clinic_a, last_name="Alphapatient")
        cls.patient_b = make_patient(cls.clinic_b, last_name="Bravopatient")
        cls.service_a = make_service(cls.clinic_a)
        cls.service_b = make_service(cls.clinic_b)
        cls.appointment_a = make_appointment(
            dentist=make_bookable_dentist(cls.clinic_a),
            patient=cls.patient_a,
            service=cls.service_a,
            start_at=local_time(cls.clinic_a, 2030, 1, 7, 10),
        )
        cls.appointment_b = make_appointment(
            dentist=make_bookable_dentist(cls.clinic_b),
            patient=cls.patient_b,
            service=cls.service_b,
            start_at=local_time(cls.clinic_b, 2030, 1, 7, 10),
        )
        cls.receptionist = make_staff_user("reception-a", (cls.clinic_a, StaffRole.RECEPTIONIST))
        cls.manager = make_staff_user("manager-a", (cls.clinic_a, StaffRole.MANAGER))
        cls.mixed = make_staff_user(
            "mixed", (cls.clinic_a, StaffRole.RECEPTIONIST), (cls.clinic_b, StaffRole.DENTIST)
        )

    def get(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def test_staff_only_see_their_clinics_records(self):
        response = self.get(self.receptionist, reverse("admin:patients_patient_changelist"))
        self.assertContains(response, "Alphapatient")
        self.assertNotContains(response, "Bravopatient")
        self.assertNotContains(response, "Bravo Dental")  # not even in the list filter
        response = self.get(self.receptionist, reverse("admin:appointments_appointment_changelist"))
        self.assertContains(response, "Alphapatient")
        self.assertNotContains(response, "Bravopatient")

    def test_other_clinics_records_cannot_be_opened(self):
        for url in [
            reverse("admin:patients_patient_change", args=[self.patient_b.pk]),
            reverse("admin:appointments_appointment_change", args=[self.appointment_b.pk]),
            reverse("admin:clinics_clinic_change", args=[self.clinic_b.pk]),
        ]:
            with self.subTest(url=url):
                response = self.get(self.receptionist, url)
                self.assertRedirects(response, reverse("admin:index"))

    def test_receptionist_role_permissions(self):
        expected = {
            reverse("admin:patients_patient_add"): 200,
            reverse("admin:appointments_appointment_add"): 200,
            reverse("admin:scheduling_timeoff_add"): 200,
            reverse("admin:catalog_service_changelist"): 200,
            reverse("admin:catalog_service_add"): 403,
            reverse("admin:scheduling_workinghours_add"): 403,
            reverse("admin:knowledge_knowledgeentry_changelist"): 403,
            reverse("admin:accounts_user_changelist"): 403,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.get(self.receptionist, url).status_code, status)

    def test_manager_role_permissions(self):
        expected = {
            reverse("admin:catalog_service_add"): 200,
            reverse("admin:staff_dentist_add"): 200,
            reverse("admin:knowledge_knowledgeentry_add"): 200,
            reverse("admin:clinics_clinic_change", args=[self.clinic_a.pk]): 200,
            reverse("admin:clinics_clinic_add"): 403,
            reverse("admin:accounts_user_changelist"): 403,
        }
        for url, status in expected.items():
            with self.subTest(url=url):
                self.assertEqual(self.get(self.manager, url).status_code, status)

    def test_records_can_only_be_added_to_own_clinic(self):
        self.client.force_login(self.manager)
        url = reverse("admin:catalog_service_add")
        data = {"name": "Whitening", "duration_minutes": 60, "is_active": "on"}
        response = self.client.post(url, {**data, "clinic": self.clinic_b.pk})
        self.assertContains(response, "Select a valid choice")
        response = self.client.post(url, {**data, "clinic": self.clinic_a.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Service.objects.get(name="Whitening").clinic, self.clinic_a)

    def test_records_can_only_be_added_where_the_role_allows_it(self):
        # Receptionist in A (may add patients), dentist in B (may only view them).
        self.client.force_login(self.mixed)
        url = reverse("admin:patients_patient_add")
        data = {"first_name": "New", "last_name": "Patient", "is_active": "on"}
        response = self.client.post(url, {**data, "clinic": self.clinic_b.pk})
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(self.client.post(url, {**data, "clinic": self.clinic_a.pk}).status_code, 302)

    def test_autocomplete_only_offers_own_clinic_records(self):
        response = self.get(
            self.receptionist,
            reverse("admin:autocomplete")
            + "?app_label=appointments&model_name=appointment&field_name=patient&term=patient",
        )
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids, {self.patient_a.pk})

    def test_permissions_follow_the_role_in_the_objects_clinic(self):
        perm = "appointments.change_appointment"
        self.assertTrue(self.mixed.has_perm(perm, self.appointment_a))  # receptionist in A
        self.assertTrue(self.mixed.has_perm(perm, self.appointment_b))  # dentist in B may update status
        self.assertTrue(self.mixed.has_perm("patients.change_patient", self.patient_a))
        self.assertFalse(self.mixed.has_perm("patients.change_patient", self.patient_b))
        self.assertTrue(self.mixed.has_perm("patients.view_patient", self.patient_b))
        response = self.get(
            self.mixed, reverse("admin:patients_patient_change", args=[self.patient_b.pk])
        )
        self.assertFalse(response.context["has_change_permission"])

    def test_inactive_membership_or_inactive_clinic_grants_nothing(self):
        user = make_staff_user("former", (self.clinic_a, StaffRole.MANAGER))
        user.staff_memberships.update(is_active=False)
        self.assertFalse(user.has_perm("patients.view_patient"))
        self.assertEqual(self.get(user, reverse("admin:patients_patient_changelist")).status_code, 403)

        user = make_staff_user("closed-clinic", (make_clinic(is_active=False), StaffRole.MANAGER))
        self.assertFalse(user.has_perm("patients.view_patient"))

    def test_staff_cannot_link_login_accounts_or_change_clinic_identity(self):
        self.client.force_login(self.manager)
        staff_member = self.manager.staff_memberships.get()
        response = self.client.get(reverse("admin:staff_staffmember_change", args=[staff_member.pk]))
        self.assertNotIn("user", response.context["adminform"].form.fields)
        response = self.client.get(reverse("admin:clinics_clinic_change", args=[self.clinic_a.pk]))
        self.assertNotIn("slug", response.context["adminform"].form.fields)


class ClinicTimezoneMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tirane = make_clinic(timezone="Europe/Tirane")
        cls.new_york = make_clinic(timezone="America/New_York")

    def active_zone_for(self, user):
        request = RequestFactory().get("/admin/")
        request.user = user
        middleware = ClinicTimezoneMiddleware(
            lambda request: HttpResponse(timezone.get_current_timezone_name())
        )
        return middleware(request).content.decode()

    def test_staff_of_one_clinic_work_in_its_time_zone(self):
        user = make_staff_user("tirane", (self.tirane, StaffRole.RECEPTIONIST))
        self.assertEqual(self.active_zone_for(user), "Europe/Tirane")

    def test_superusers_and_multi_zone_staff_use_the_default_zone(self):
        superuser = User.objects.create_superuser(username="root", password="unused")
        mixed = make_staff_user(
            "mixed", (self.tirane, StaffRole.MANAGER), (self.new_york, StaffRole.MANAGER)
        )
        self.assertEqual(self.active_zone_for(superuser), "UTC")
        self.assertEqual(self.active_zone_for(mixed), "UTC")
