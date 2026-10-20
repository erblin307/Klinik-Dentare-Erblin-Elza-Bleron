from datetime import datetime

from django.test import TestCase

from apps.appointments import booking
from apps.appointments.models import Appointment, AppointmentSource, AppointmentStatus
from apps.chatbot.engine import MAX_REFERENCE_ATTEMPTS, ChatEngine, format_reference
from apps.chatbot.models import ChatConversation, ChatRole
from apps.patients.models import Patient

from .chat_support import FakeLLM, UnavailableLLM
from .factories import (
    local_time,
    make_bookable_dentist,
    make_clinic,
    make_patient,
    make_service,
)

MONDAY = "2030-01-07"
SATURDAY = "2030-01-12"
DETAILS = {"first_name": "Arta", "last_name": "Krasniqi", "phone": "+000 44 123 456"}


class ChatEngineTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(name="Smile Studio", phone="+000 111 222", timezone="Europe/Tirane")
        cls.service = make_service(cls.clinic, name="Check-up", duration_minutes=30)
        # Monday–Friday 09:00–13:00 and 14:00–18:00 clinic time.
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.service])
        cls.now = local_time(cls.clinic, 2030, 1, 1, 8)  # Tuesday morning

    def setUp(self):
        self.conversation, _ = ChatConversation.start(clinic=self.clinic, language="en")
        self.llm = FakeLLM()

    def at(self, hour, minute=0, day=7):
        return local_time(self.clinic, 2030, 1, day, hour, minute)

    def chat(self, text="", *, llm=None, now=None, **kwargs):
        engine = ChatEngine(self.conversation, llm=llm or self.llm, now=now or self.now)
        return engine.handle(text, **kwargs)

    def expect(self, text, **interpretation):
        """Make the fake model interpret ``text`` like this."""
        self.llm.interpretations[text] = interpretation

    def reach_booking_proposal(self, time="09:00", phone=DETAILS["phone"]):
        message = f"Check-up on Monday at {time}, I am Arta Krasniqi, {phone}"
        details = {**DETAILS, "phone": phone}
        self.expect(message, intent="book", service="Check-up", date=MONDAY, time=time, **details)
        reply = self.chat(message)
        self.assertIsNotNone(reply.pending_action, reply.text)
        return reply


class QuestionTests(ChatEngineTestCase):
    def test_questions_are_answered_from_the_clinic_knowledge_base(self):
        self.llm.answer = "We offer check-ups."
        reply = self.chat("What services do you offer?")
        self.assertEqual(reply.text, "We offer check-ups.")
        system = self.llm.answer_calls[0]["messages"][0]["content"]
        self.assertIn('dental clinic "Smile Studio"', system)
        self.assertIn("Use ONLY the CLINIC INFORMATION", system)
        self.assertIn("Check-up: 30 min", system)
        self.assertIn("Reply in English", system)

    def test_the_reply_language_follows_the_user(self):
        for text, language, name in [
            ("Was kostet eine Kontrolle bei Ihnen?", "de", "German"),
            ("Sa kushton një kontroll te ju?", "sq", "Albanian"),
            ("How much is a check-up?", "en", "English"),
        ]:
            with self.subTest(language=language):
                reply = self.chat(text)
                self.assertEqual(reply.language, language)
                self.assertIn(f"Reply in {name}", self.llm.answer_calls[-1]["messages"][0]["content"])
                self.conversation.refresh_from_db()
                self.assertEqual(self.conversation.language, language)

    def test_medical_questions_get_a_safe_fixed_reply(self):
        self.expect("My tooth hurts, which antibiotic should I take?", intent="medical")
        reply = self.chat("My tooth hurts, which antibiotic should I take?")
        self.assertIn("cannot give diagnoses or medical advice", reply.text)
        self.assertIn("+000 111 222", reply.text)
        self.assertEqual(self.llm.answer_calls, [])

    def test_a_yes_without_anything_pending_is_simply_answered(self):
        self.expect("yes", intent="confirm")
        self.assertEqual(self.chat("yes").text, "Fake answer.")
        self.conversation.refresh_from_db()
        self.assertIsNone(self.conversation.state["flow"])

    def test_an_unavailable_model_gives_a_helpful_fallback(self):
        reply = self.chat("Hello?", llm=UnavailableLLM())
        self.assertEqual(reply.error, "assistant_unavailable")
        self.assertIn("+000 111 222", reply.text)
        roles = list(self.conversation.messages.values_list("role", flat=True))
        self.assertEqual(roles, [ChatRole.USER, ChatRole.ASSISTANT])

    def test_prompts_never_contain_other_patients_data(self):
        stranger = make_patient(self.clinic, first_name="Zyrafete", last_name="Uniqueperson", phone="+999")
        booking.create_appointment(
            patient=stranger, dentist=self.dentist, service=self.service, start_at=self.at(9), now=self.now
        )
        self.chat("Do you have parking?")
        self.expect("Book a check-up on Monday", intent="book", service="Check-up", date=MONDAY)
        self.chat("Book a check-up on Monday")
        prompts = self.llm.all_prompt_text()
        for private in ["Zyrafete", "Uniqueperson", "+999"]:
            self.assertNotIn(private, prompts)


class BookingFlowTests(ChatEngineTestCase):
    def test_full_booking_flow_with_explicit_confirmation(self):
        self.expect("I'd like a check-up on Monday", intent="book", service="Check-up", date=MONDAY)
        reply = self.chat("I'd like a check-up on Monday")
        self.assertIn("Available appointments for Check-up", reply.text)
        self.assertEqual(len(reply.options), 5)
        self.assertEqual(datetime.fromisoformat(reply.options[1]["start"]), self.at(9, 30))

        reply = self.chat("2")  # no model needed for a plain option number
        self.assertIn("first name, last name and phone number", reply.text)

        self.expect("Arta Krasniqi, +000 44 123 456", intent="give_details", **DETAILS)
        reply = self.chat("Arta Krasniqi, +000 44 123 456")
        self.assertIn("Please confirm: Check-up with", reply.text)
        self.assertIn("Monday 07.01.2030 at 09:30", reply.text)
        self.assertEqual(reply.pending_action["type"], "book")
        self.assertFalse(Appointment.objects.exists())

        reply = self.chat("Yes")
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.start_at, self.at(9, 30))
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(appointment.source, AppointmentSource.CHATBOT)
        self.assertEqual(
            (appointment.patient.first_name, appointment.patient.phone), ("Arta", "+00044123456")
        )
        self.assertIn(format_reference(appointment.reference), reply.text)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.state["details"], {})  # not kept after booking

    def test_the_model_alone_can_never_confirm_a_booking(self):
        proposal = self.reach_booking_proposal()
        self.expect("sounds great, do it", intent="confirm")
        reply = self.chat("sounds great, do it")
        self.assertIn('reply "yes" to confirm', reply.text)
        self.assertEqual(reply.pending_action, proposal.pending_action)
        self.assertEqual(self.chat(confirm_action="forged-id").text, "There is nothing to confirm.")
        self.assertFalse(Appointment.objects.exists())

        self.chat(confirm_action=proposal.pending_action["id"])  # the frontend's confirm button
        self.assertEqual(Appointment.objects.count(), 1)

    def test_declining_or_changing_the_topic_discards_the_proposal(self):
        self.reach_booking_proposal()
        self.assertIn("not made any changes", self.chat("No").text)
        self.reach_booking_proposal()
        self.chat("Do you have parking?")
        self.assertEqual(self.chat("yes").pending_action, None)
        self.assertFalse(Appointment.objects.exists())

    def test_one_complete_message_goes_straight_to_confirmation(self):
        reply = self.reach_booking_proposal(time="10:00")
        self.assertIn("Monday 07.01.2030 at 10:00", reply.text)
        self.assertIn("Arta Krasniqi (+00044123456)", reply.text)

    def test_unknown_service_lists_the_clinics_services(self):
        for name in ["Brain surgery", "x'; DROP TABLE appointments_appointment; --"]:
            self.expect(f"Book {name}", intent="book", service=name)
            reply = self.chat(f"Book {name}")
            self.assertIn("Which service would you like to book? We offer: Check-up.", reply.text)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_invalid_phone_number_is_rejected(self):
        self.expect("My number is 12", intent="give_details", phone="12")
        self.assertIn("phone number does not look right", self.chat("My number is 12").text)

    def test_no_free_times_are_reported(self):
        self.expect("Check-up on Saturday", intent="book", service="Check-up", date=SATURDAY)
        self.assertIn("could not find a free appointment", self.chat("Check-up on Saturday").text)

    def test_a_slot_taken_before_confirmation_is_reported_with_new_options(self):
        self.reach_booking_proposal(time="09:00")
        booking.create_appointment(  # someone else books 09:00 meanwhile
            patient=make_patient(self.clinic), dentist=self.dentist, service=self.service,
            start_at=self.at(9), now=self.now,
        )  # fmt: skip
        reply = self.chat("yes")
        self.assertIn("this time has just been taken", reply.text)
        self.assertTrue(reply.options)
        self.assertNotIn(self.at(9).isoformat(), [o["start"] for o in reply.options])
        self.assertEqual(Appointment.objects.filter(start_at=self.at(9)).count(), 1)

    def test_existing_patient_is_reused_only_on_exact_match(self):
        existing = make_patient(self.clinic, first_name="Arta", last_name="Krasniqi", phone="+00044123456")
        self.reach_booking_proposal()
        self.chat("yes")
        self.assertEqual(Appointment.objects.get().patient, existing)
        self.assertEqual(Patient.objects.count(), 1)

        # Same name, other phone: a new patient; never attached to the look-alike record.
        lookalike = make_patient(self.clinic, first_name="Arta", last_name="Krasniqi", phone="+38900000000")
        self.reach_booking_proposal(time="11:00", phone="+389 00 000 001")
        self.chat("yes")
        self.assertEqual(Patient.objects.count(), 3)
        self.assertFalse(lookalike.appointments.exists())
        self.assertEqual(Appointment.objects.get(start_at=self.at(11)).patient.phone, "+38900000001")

    def test_booking_flow_in_albanian_and_german(self):
        cases = [
            ("Dua një kontroll të hënën", "Terminet e lira për Check-up", "e hënë, 07.01.2030, ora 09:00"),
            ("Ich möchte eine Kontrolle am Montag", "Freie Termine für Check-up", "Montag, 07.01.2030, 09:00 Uhr"),
        ]  # fmt: skip
        for text, heading, first_option in cases:
            with self.subTest(text=text):
                self.expect(text, intent="book", service="Check-up", date=MONDAY)
                reply = self.chat(text)
                self.assertIn(heading, reply.text)
                self.assertIn(first_option, reply.text)


class ExistingAppointmentTests(ChatEngineTestCase):
    def setUp(self):
        super().setUp()
        self.patient = make_patient(self.clinic)
        self.appointment = booking.create_appointment(
            patient=self.patient, dentist=self.dentist, service=self.service,
            start_at=self.at(10), now=self.now,
        )  # fmt: skip
        self.reference = format_reference(self.appointment.reference)

    def test_cancelling_needs_the_reference_and_a_confirmation(self):
        self.expect("I want to cancel my appointment", intent="cancel")
        self.assertIn("booking reference", self.chat("I want to cancel my appointment").text)
        reply = self.chat(self.reference.lower().replace("-", ""))  # recognised without the model
        self.assertIn("Do you want to cancel Check-up", reply.text)
        self.assertIn("Monday 07.01.2030 at 10:00", reply.text)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.CONFIRMED)

        self.assertIn("has been cancelled", self.chat("yes").text)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.CANCELLED)

    def test_wrong_references_are_limited(self):
        self.expect("cancel please", intent="cancel")
        self.chat("cancel please")
        for _ in range(MAX_REFERENCE_ATTEMPTS):
            self.assertIn("could not find", self.chat("ZZ22-ZZ22").text)
        self.assertIn("Too many unsuccessful attempts", self.chat(self.reference).text)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, AppointmentStatus.CONFIRMED)

    def test_references_of_another_clinic_are_not_found(self):
        other = make_clinic()
        other_service = make_service(other)
        foreign = booking.create_appointment(
            patient=make_patient(other),
            dentist=make_bookable_dentist(other, services=[other_service]),
            service=other_service,
            start_at=local_time(other, 2030, 1, 7, 10),
            now=self.now,
        )
        message = f"cancel {format_reference(foreign.reference)}"
        self.expect(message, intent="cancel")
        self.assertIn("could not find", self.chat(message).text)
        self.chat("yes")
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, AppointmentStatus.CONFIRMED)

    def test_started_appointments_cannot_be_cancelled_online(self):
        message = f"cancel {self.reference}"
        self.expect(message, intent="cancel")
        reply = self.chat(message, now=self.at(10, 5))
        self.assertIn("can no longer be changed online", reply.text)
        self.assertIsNone(reply.pending_action)

    def test_rescheduling_with_the_reference(self):
        message = f"Please move my appointment {self.reference} to Tuesday"
        self.expect(message, intent="reschedule", date="2030-01-08")
        reply = self.chat(message)
        self.assertIn("Your current appointment: Check-up", reply.text)
        self.assertIn("Tuesday 08.01.2030 at 09:00", reply.text)

        reply = self.chat("1")
        self.assertIn("Move Check-up from Monday 07.01.2030 at 10:00 to Tuesday 08.01.2030 at 09:00", reply.text)
        reply = self.chat("ja")
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, self.at(9, day=8))
        self.assertIn(self.reference, reply.text)  # the reference stays valid
