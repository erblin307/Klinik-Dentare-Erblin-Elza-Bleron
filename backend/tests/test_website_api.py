from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.appointments import booking
from apps.knowledge.models import KnowledgeCategory, KnowledgeEntry
from apps.scheduling.models import TimeOff
from apps.website import views

from .factories import (
    local_time,
    make_bookable_dentist,
    make_clinic,
    make_dentist,
    make_patient,
    make_service,
)


class WebsiteApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(
            slug="smile", name="Smile Studio", phone="+000 111", city="Prishtina", timezone="Europe/Tirane"
        )
        cls.checkup = make_service(cls.clinic, name="Check-up", price=Decimal("30.00"))
        cls.whitening = make_service(cls.clinic, name="Whitening", duration_minutes=60, price=None)
        make_service(cls.clinic, name="Retired", is_active=False)
        # Every day 09:00–13:00 and 14:00–18:00, so tests do not depend on the weekday.
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.checkup], weekdays=range(7))
        cls.dentist.specialty = "Prosthodontics"
        cls.dentist.save()
        cls.hidden_dentist = make_dentist(cls.clinic, is_bookable=False)
        KnowledgeEntry.objects.create(
            clinic=cls.clinic, title="Parking", content="Behind the building.", language="en",
            category=KnowledgeCategory.FAQ, is_published=True,
        )  # fmt: skip
        KnowledgeEntry.objects.create(
            clinic=cls.clinic, title="Parkimi", content="Pas ndërtesës.", language="sq",
            category=KnowledgeCategory.FAQ, is_published=True,
        )  # fmt: skip
        KnowledgeEntry.objects.create(clinic=cls.clinic, title="Draft", content="x", is_published=False)
        other = make_clinic(slug="other")
        make_service(other, name="Other service")

    def setUp(self):
        cache.clear()

    def get(self, name, slug="smile", **params):
        return self.client.get(reverse(f"website:{name}", args=[slug]), params)

    def test_clinic_details_with_opening_hours_and_closures(self):
        start = local_time(self.clinic, 2030, 6, 1, 0)
        TimeOff.objects.create(
            clinic=self.clinic, start_at=start, end_at=start + timedelta(days=1), reason="internal"
        )
        response = self.get("clinic")
        data = response.json()
        self.assertEqual(response["Cache-Control"], "public, max-age=300")
        self.assertEqual((data["name"], data["phone"], data["city"]), ("Smile Studio", "+000 111", "Prishtina"))
        self.assertEqual(data["opening_hours"][0], {"weekday": 0, "start": "09:00", "end": "18:00"})
        self.assertEqual(len(data["opening_hours"]), 7)
        self.assertNotIn("internal", response.content.decode())

    def test_services_are_active_ones_of_this_clinic(self):
        data = self.get("services").json()
        self.assertEqual(data["currency"], "EUR")
        self.assertEqual(
            data["services"],
            [
                {"id": self.checkup.pk, "name": "Check-up", "description": "", "duration_minutes": 30,
                 "price": "30.00", "dentist_ids": [self.dentist.pk]},
                {"id": self.whitening.pk, "name": "Whitening", "description": "", "duration_minutes": 60,
                 "price": None, "dentist_ids": []},
            ],
        )  # fmt: skip

    def test_dentists_are_bookable_ones_without_private_data(self):
        response = self.get("dentists")
        dentists = response.json()["dentists"]
        self.assertEqual([d["id"] for d in dentists], [self.dentist.pk])
        self.assertEqual(dentists[0]["specialty"], "Prosthodontics")
        self.assertEqual(dentists[0]["service_ids"], [self.checkup.pk])
        self.assertEqual(dentists[0]["working_hours"][:2], [
            {"weekday": 0, "start": "09:00", "end": "13:00"},
            {"weekday": 0, "start": "14:00", "end": "18:00"},
        ])  # fmt: skip
        self.assertEqual(set(dentists[0]), {"id", "name", "specialty", "bio", "service_ids", "working_hours"})

    def test_articles_are_published_ones_filtered_by_language(self):
        titles = [a["title"] for a in self.get("articles").json()["articles"]]
        self.assertEqual(sorted(titles), ["Parkimi", "Parking"])
        sq = self.get("articles", language="sq").json()["articles"]
        self.assertEqual([a["title"] for a in sq], ["Parkimi"])

    def test_availability_returns_real_free_slots(self):
        day = timezone.now().date() + timedelta(days=3)
        start = local_time(self.clinic, day.year, day.month, day.day, 10)
        booking.create_appointment(
            patient=make_patient(self.clinic), dentist=self.dentist, service=self.checkup, start_at=start
        )
        response = self.get("availability", service=self.checkup.pk, date=day.isoformat())
        self.assertEqual(response["Cache-Control"], "no-store")
        data = response.json()
        self.assertEqual(data["timezone"], "Europe/Tirane")
        starts = [slot["start"][11:16] for slot in data["slots"]]
        self.assertEqual(starts[:3], ["09:00", "09:30", "10:30"])  # 10:00 is booked
        self.assertNotIn("13:00", starts)  # lunch break
        self.assertEqual(data["slots"][0]["dentist"], str(self.dentist))

    def test_availability_validation(self):
        today = timezone.now().date().isoformat()
        cases = {
            ("invalid_date", 400): {"service": self.checkup.pk, "date": "tomorrow"},
            ("invalid_service", 400): {"date": today},
            ("invalid_days", 400): {"service": self.checkup.pk, "date": today, "days": 8},
            ("unknown_service", 404): {"service": 999999, "date": today},
        }
        for (code, status), params in cases.items():
            with self.subTest(code=code):
                response = self.get("availability", **params)
                self.assertEqual((response.status_code, response.json()["error"]), (status, code))
        past = self.get("availability", service=self.checkup.pk, date=date(2020, 1, 1).isoformat())
        self.assertEqual(past.json()["slots"], [])

    def test_service_of_another_clinic_is_not_found(self):
        foreign = make_service(make_clinic(slug="third"))
        response = self.get("availability", service=foreign.pk, date=timezone.now().date().isoformat())
        self.assertEqual(response.status_code, 404)

    def test_unknown_or_inactive_clinic_and_write_methods(self):
        make_clinic(slug="closed", is_active=False)
        for name in ["clinic", "services", "dentists", "articles", "availability"]:
            with self.subTest(name=name):
                self.assertEqual(self.get(name, slug="nope").status_code, 404)
                self.assertEqual(self.get(name, slug="closed").status_code, 404)
                self.assertEqual(self.client.post(reverse(f"website:{name}", args=["smile"])).status_code, 405)

    def test_availability_is_rate_limited(self):
        params = {"service": self.checkup.pk, "date": timezone.now().date().isoformat()}
        for _ in range(views.AVAILABILITY_REQUESTS_PER_MINUTE):
            self.assertEqual(self.get("availability", **params).status_code, 200)
        self.assertEqual(self.get("availability", **params).status_code, 429)
