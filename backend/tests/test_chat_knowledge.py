from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.chatbot.knowledge import build_context, relevant_entries, search_terms
from apps.knowledge.models import KnowledgeCategory, KnowledgeEntry
from apps.scheduling.models import TimeOff

from .factories import (
    local_time,
    make_appointment,
    make_bookable_dentist,
    make_clinic,
    make_dentist,
    make_patient,
    make_service,
)

TODAY = date(2030, 1, 1)


class KnowledgeContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(
            name="Smile Studio", phone="+000 111 222", city="Prishtina", currency="EUR"
        )
        cls.whitening = make_service(
            cls.clinic, name="Whitening", duration_minutes=60, price=Decimal("150.00"),
            description="Professional in-office whitening.",
        )  # fmt: skip
        cls.consultation = make_service(cls.clinic, name="Consultation", price=None)
        make_service(cls.clinic, name="Retired Treatment", is_active=False)
        cls.dentist = make_bookable_dentist(
            cls.clinic, services=[cls.whitening], weekdays=[0], blocks=[(9, 13), (14, 18)]
        )
        cls.dentist.specialty = "Aesthetic dentistry"
        cls.dentist.save()
        make_dentist(cls.clinic, is_bookable=False)  # not public
        KnowledgeEntry.objects.create(
            clinic=cls.clinic,
            title="Cancellation policy",
            content="Please cancel at least 24 hours in advance.",
            category=KnowledgeCategory.POLICIES,
            language="en",
            is_published=True,
        )
        KnowledgeEntry.objects.create(
            clinic=cls.clinic, title="Draft parking info", content="Secret draft.", language="en"
        )
        other = make_clinic(name="Other Clinic")
        make_service(other, name="Other Clinic Implant")
        KnowledgeEntry.objects.create(
            clinic=other, title="Other policy", content="Not ours.", is_published=True
        )

    def context(self, query="hello", language="en"):
        return build_context(self.clinic, query=query, language=language, today=TODAY)

    def test_contains_clinic_details_services_prices_dentists_and_hours(self):
        context = self.context()
        for expected in [
            "Smile Studio",
            "+000 111 222",
            "Prishtina",
            "Whitening: 60 min, 150.00 EUR.",
            "Professional in-office whitening.",
            "Consultation: 30 min, price after consultation.",
            f"{self.dentist} (Aesthetic dentistry)",
            "Monday 09:00–13:00, 14:00–18:00",
            f"Performed by: {self.dentist}",
            "Cancellation policy",
            "24 hours in advance",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, context)

    def test_excludes_unpublished_inactive_hidden_and_other_clinics_data(self):
        context = self.context()
        for hidden in ["Retired Treatment", "Secret draft", "Other Clinic", "Not ours"]:
            with self.subTest(hidden=hidden):
                self.assertNotIn(hidden, context)
        self.assertEqual(context.count("Working hours:"), 1)  # only the bookable dentist

    def test_never_contains_patient_or_appointment_data(self):
        patient = make_patient(self.clinic, first_name="Zyrafete", last_name="Uniqueperson", phone="+999")
        make_appointment(
            dentist=self.dentist, patient=patient, service=self.whitening,
            start_at=local_time(self.clinic, 2030, 1, 7, 10), notes="Allergic to penicillin",
        )  # fmt: skip
        context = self.context(query="Zyrafete Uniqueperson appointment")
        for private in ["Zyrafete", "Uniqueperson", "+999", "penicillin"]:
            self.assertNotIn(private, context)

    def test_clinic_closures_are_listed_in_clinic_time_without_internal_reason(self):
        TimeOff.objects.create(
            clinic=self.clinic,
            start_at=local_time(self.clinic, 2030, 1, 15, 0),
            end_at=local_time(self.clinic, 2030, 1, 16, 0),
            reason="Staff party",
        )
        TimeOff.objects.create(  # an individual absence stays internal
            clinic=self.clinic,
            dentist=self.dentist,
            start_at=local_time(self.clinic, 2030, 1, 20, 0),
            end_at=local_time(self.clinic, 2030, 1, 21, 0),
        )
        context = self.context()
        self.assertIn("closed from 2030-01-15 00:00 to 2030-01-16 00:00", context)
        self.assertNotIn("Staff party", context)
        self.assertNotIn("2030-01-20", context)


class EntryRetrievalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()

        def entry(title, content, language, category=KnowledgeCategory.FAQ):
            return KnowledgeEntry.objects.create(
                clinic=cls.clinic, title=title, content=content, language=language,
                category=category, is_published=True,
            )  # fmt: skip

        cls.parking = entry("Parking", "Free parking behind the building.", "en")
        cls.payment = entry("Payment", "We accept cards and cash.", "en", KnowledgeCategory.PRICING)
        cls.payment_sq = entry("Pagesa", "Pranojmë karta dhe para në dorë.", "sq", KnowledgeCategory.PRICING)
        cls.cancel_sq = entry("Anulimi i termineve", "Anulimi i terminit bëhet 24 orë më parë.", "sq")

    def titles(self, query, language="en"):
        return [e.title for e in relevant_entries(self.clinic, query, language)]

    def test_most_relevant_entry_comes_first(self):
        self.assertEqual(self.titles("Where can I park my car? parking")[0], "Parking")
        self.assertEqual(self.titles("Do you accept cards?")[0], "Payment")

    def test_prefix_matching_handles_inflected_albanian(self):
        self.assertEqual(self.titles("Si mund ta anuloj terminin?", "sq")[0], "Anulimi i termineve")

    def test_entries_in_the_users_language_are_preferred_when_equally_relevant(self):
        titles = self.titles("hello", language="sq")
        self.assertLess(titles.index("Pagesa"), titles.index("Payment"))

    def test_search_terms_are_letters_only(self):
        self.assertEqual(search_terms("x'; DROP TABLE patients; -- & | ! :*"), ["drop", "table", "patien"])
        self.assertEqual(search_terms("1234 ?? ::"), [])
        self.assertTrue(relevant_entries(self.clinic, "'; DROP TABLE x; --", "en"))
