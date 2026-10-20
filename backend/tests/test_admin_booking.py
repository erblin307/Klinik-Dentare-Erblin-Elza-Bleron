from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.appointments import booking
from apps.appointments.models import Appointment, AppointmentStatus
from apps.staff.models import StaffRole

from .factories import (
    local_time,
    make_bookable_dentist,
    make_clinic,
    make_patient,
    make_service,
    make_staff_member,
)


class AdminBookingTests(TestCase):
    """Booking through the admin as a receptionist working in clinic time (Tirane)."""

    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(timezone="Europe/Tirane")
        cls.service = make_service(cls.clinic, duration_minutes=30)
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.service])
        cls.patient = make_patient(cls.clinic)
        cls.user = User.objects.create_user(username="reception", password="unused", is_staff=True)
        make_staff_member(cls.clinic, role=StaffRole.RECEPTIONIST, user=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def at(self, hour, minute=0):
        return local_time(self.clinic, 2030, 1, 7, hour, minute)

    def add(self, time_text, **overrides):
        data = {
            "patient": self.patient.pk,
            "dentist": self.dentist.pk,
            "service": self.service.pk,
            "start_at_0": "2030-01-07",
            "start_at_1": time_text,
            "source": "phone",
            "notes": "",
            **overrides,
        }
        return self.client.post(reverse("admin:appointments_appointment_add"), data)

    def change(self, appointment, **overrides):
        local_start = appointment.start_at.astimezone(self.at(0).tzinfo)
        data = {
            "dentist": appointment.dentist_id,
            "start_at_0": local_start.strftime("%Y-%m-%d"),
            "start_at_1": local_start.strftime("%H:%M"),
            "status": appointment.status,
            "notes": appointment.notes,
            **overrides,
        }
        url = reverse("admin:appointments_appointment_change", args=[appointment.pk])
        return self.client.post(url, data)

    def booked(self):
        return booking.create_appointment(
            patient=self.patient, dentist=self.dentist, service=self.service, start_at=self.at(10)
        )

    def test_adding_books_a_confirmed_appointment_in_clinic_time(self):
        response = self.add("10:00")
        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.start_at, self.at(10))  # 09:00 UTC
        self.assertEqual(appointment.end_at, self.at(10, 30))
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(appointment.clinic, self.clinic)

    def test_booking_rules_are_reported_as_form_errors(self):
        self.assertContains(self.add("13:15"), "outside the dentist&#x27;s working hours")
        self.booked()
        self.assertContains(self.add("10:15"), "already has an appointment")
        self.assertEqual(Appointment.objects.count(), 1)

    def test_a_slot_lost_to_a_concurrent_booking_is_reported_not_crashed(self):
        self.booked()
        other = make_patient(self.clinic)
        with mock.patch.object(booking, "_conflict", return_value=None):
            response = self.add("10:00", patient=other.pk)
        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("The dentist already has an appointment at this time.", messages)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_changing_the_time_reschedules(self):
        appointment = self.booked()
        self.assertEqual(self.change(appointment, start_at_1="15:00").status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual((appointment.start_at, appointment.end_at), (self.at(15), self.at(15, 30)))
        self.assertContains(self.change(appointment, start_at_1="13:30"), "working hours")

    def test_status_choices_only_offer_allowed_transitions(self):
        appointment = self.booked()
        url = reverse("admin:appointments_appointment_change", args=[appointment.pk])
        choices = dict(self.client.get(url).context["adminform"].form.fields["status"].choices)
        self.assertEqual(
            set(choices),
            {"confirmed", "checked_in", "cancelled", "no_show"},
        )

    def test_status_change_and_reschedule_need_separate_steps(self):
        appointment = self.booked()
        response = self.change(appointment, start_at_1="15:00", status="cancelled")
        self.assertContains(response, "separate steps")

    def test_cancelling_from_the_form_and_the_list_action(self):
        appointment = self.booked()
        self.assertEqual(self.change(appointment, status="cancelled").status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CANCELLED)

        second = booking.create_appointment(
            patient=self.patient, dentist=self.dentist, service=self.service, start_at=self.at(11)
        )
        self.client.post(
            reverse("admin:appointments_appointment_changelist"),
            {"action": "cancel_selected", "_selected_action": [appointment.pk, second.pk]},
        )
        second.refresh_from_db()
        self.assertEqual(second.status, AppointmentStatus.CANCELLED)

    def test_appointments_of_other_clinics_cannot_be_cancelled_by_action(self):
        other_clinic = make_clinic()
        other_service = make_service(other_clinic)
        foreign = booking.create_appointment(
            patient=make_patient(other_clinic),
            dentist=make_bookable_dentist(other_clinic, services=[other_service]),
            service=other_service,
            start_at=local_time(other_clinic, 2030, 1, 7, 10),
        )
        self.client.post(
            reverse("admin:appointments_appointment_changelist"),
            {"action": "cancel_selected", "_selected_action": [foreign.pk]},
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, AppointmentStatus.CONFIRMED)
