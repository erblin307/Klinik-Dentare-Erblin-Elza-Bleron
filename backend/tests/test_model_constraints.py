from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from apps.accounts.models import User
from apps.catalog.models import Service
from apps.clinics.models import Clinic
from apps.knowledge.models import KnowledgeEntry
from apps.staff.models import Dentist, StaffMember, StaffRole

from .factories import make_clinic, make_patient, make_service, make_staff_member
from .utils import IntegrityTestCase


class ClinicTests(IntegrityTestCase):
    def test_slug_is_unique(self):
        make_clinic(slug="smile")
        with self.assertViolates("clinics_clinic_slug_key"):
            make_clinic(slug="smile")

    def test_timezone_must_be_a_valid_iana_zone(self):
        clinic = Clinic(name="Clinic", slug="clinic", timezone="Mars/Olympus_Mons")
        with self.assertRaises(ValidationError) as ctx:
            clinic.full_clean()
        self.assertIn("timezone", ctx.exception.message_dict)

    def test_clinic_with_data_cannot_be_deleted(self):
        clinic = make_clinic()
        make_patient(clinic)
        with self.assertRaises(ProtectedError):
            clinic.delete()


class ServiceTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()

    def test_duration_must_be_between_5_and_480_minutes(self):
        for minutes in [0, 4, 481]:
            with self.subTest(minutes=minutes):
                with self.assertViolates("catalog_service_duration_range"):
                    make_service(self.clinic, duration_minutes=minutes)

    def test_price_cannot_be_negative_but_may_be_empty(self):
        with self.assertViolates("catalog_service_price_non_negative"):
            make_service(self.clinic, price=Decimal("-1.00"))
        make_service(self.clinic, price=None)
        make_service(self.clinic, price=Decimal("0.00"))

    def test_name_is_unique_per_clinic_only(self):
        make_service(self.clinic, name="Whitening")
        with self.assertViolates("catalog_service_unique_name"):
            make_service(self.clinic, name="Whitening")
        make_service(make_clinic(), name="Whitening")
        self.assertEqual(Service.objects.filter(name="Whitening").count(), 2)


class StaffTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()

    def test_unknown_role_is_rejected(self):
        with self.assertViolates("staff_staffmember_role_valid"):
            make_staff_member(self.clinic, role="astronaut")

    def test_user_account_is_linked_at_most_once_per_clinic(self):
        user = User.objects.create_user(username="staff-user")
        make_staff_member(self.clinic, user=user)
        with self.assertViolates("staff_staffmember_unique_user"):
            make_staff_member(self.clinic, user=user)
        make_staff_member(make_clinic(), user=user)
        self.assertEqual(StaffMember.objects.filter(user=user).count(), 2)

    def test_staff_member_has_at_most_one_dentist_profile(self):
        staff_member = make_staff_member(self.clinic, role=StaffRole.DENTIST)
        Dentist.objects.create(clinic=self.clinic, staff_member=staff_member)
        with self.assertViolates("staff_dentist_staff_member_id_key"):
            Dentist.objects.create(clinic=self.clinic, staff_member=staff_member)

    def test_dentist_profile_requires_dentist_role(self):
        receptionist = make_staff_member(self.clinic, role=StaffRole.RECEPTIONIST)
        dentist = Dentist(clinic=self.clinic, staff_member=receptionist)
        with self.assertRaises(ValidationError) as ctx:
            dentist.full_clean()
        self.assertIn("staff_member", ctx.exception.message_dict)


class KnowledgeEntryTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()

    def entry(self, **fields):
        defaults = {"clinic": self.clinic, "title": "Opening hours", "content": "Mon–Fri 9–17."}
        return KnowledgeEntry.objects.create(**{**defaults, **fields})

    def test_title_is_unique_per_clinic_and_language(self):
        self.entry()
        with self.assertViolates("knowledge_knowledgeentry_unique_title"):
            self.entry()
        self.entry(language="en")
        self.entry(clinic=make_clinic())

    def test_unknown_category_is_rejected(self):
        with self.assertViolates("knowledge_knowledgeentry_category_valid"):
            self.entry(category="gossip")

    def test_entries_are_unpublished_by_default(self):
        self.assertFalse(self.entry().is_published)
