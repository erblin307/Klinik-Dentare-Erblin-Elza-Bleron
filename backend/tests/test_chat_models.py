from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.booking import find_appointment, normalize_reference
from apps.appointments.models import REFERENCE_ALPHABET, Appointment, generate_reference
from apps.chatbot.models import ChatConversation, ChatMessage
from apps.staff.models import StaffRole

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


class BookingReferenceTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        dentist, service = make_dentist(cls.clinic), make_service(cls.clinic)
        cls.first, cls.second = (
            make_appointment(dentist=dentist, patient=make_patient(cls.clinic), service=service,
                             start_at=MONDAY_9AM + timedelta(hours=h))
            for h in (0, 1)
        )  # fmt: skip

    def test_references_are_random_unambiguous_and_contain_a_digit(self):
        references = {generate_reference() for _ in range(500)}
        self.assertEqual(len(references), 500)
        for reference in references:
            self.assertEqual(len(reference), 8)
            self.assertTrue(set(reference) <= set(REFERENCE_ALPHABET))
            self.assertTrue(any(ch.isdigit() for ch in reference))

    def test_reference_is_unique(self):
        with self.assertViolates("appointments_appointment_reference_key"):
            Appointment.objects.filter(pk=self.second.pk).update(reference=self.first.reference)

    def test_lookup_is_normalised_and_scoped_to_the_clinic(self):
        typed = f" {self.first.reference[:4].lower()}-{self.first.reference[4:]} "
        self.assertEqual(normalize_reference(typed), self.first.reference)
        self.assertEqual(find_appointment(self.clinic, typed), self.first)
        self.assertIsNone(find_appointment(make_clinic(), self.first.reference))
        for invalid in ["", "SHORT", "ABCDEFGHI", "ABCD-EFG0"]:  # 0 is not in the alphabet
            self.assertIsNone(normalize_reference(invalid))


class ChatModelConstraintTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.conversation, _ = ChatConversation.start(clinic=cls.clinic, language="sq")

    def test_language_must_be_supported(self):
        with self.assertViolates("chatbot_chatconversation_language_valid"):
            ChatConversation.objects.filter(pk=self.conversation.pk).update(language="fr")

    def test_message_role_must_be_valid(self):
        with self.assertViolates("chatbot_chatmessage_role_valid"):
            ChatMessage.objects.create(
                clinic=self.clinic, conversation=self.conversation, role="system", content="x"
            )

    def test_message_belongs_to_the_conversations_clinic(self):
        with self.assertViolates("chatbot_chatmessage_conversation_same_clinic"):
            ChatMessage.objects.create(
                clinic=make_clinic(), conversation=self.conversation, role="user", content="x"
            )


class RetentionTests(TestCase):
    def test_purge_deletes_only_conversations_past_retention(self):
        clinic = make_clinic()
        old, _ = ChatConversation.start(clinic=clinic, language="en")
        recent, _ = ChatConversation.start(clinic=clinic, language="en")
        ChatMessage.objects.create(clinic=clinic, conversation=old, role="user", content="My phone is ...")
        ChatConversation.objects.filter(pk=old.pk).update(last_activity_at=timezone.now() - timedelta(days=31))
        call_command("purge_chat_conversations", stdout=StringIO())
        self.assertEqual(list(ChatConversation.objects.all()), [recent])
        self.assertFalse(ChatMessage.objects.exists())


class TranscriptAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.conversation, _ = ChatConversation.start(clinic=cls.clinic, language="en")
        other_conversation, _ = ChatConversation.start(clinic=make_clinic(), language="en")
        cls.other_url = reverse("admin:chatbot_chatconversation_change", args=[other_conversation.pk])

        def staff_user(username, role):
            user = User.objects.create_user(username=username, password="unused", is_staff=True)
            make_staff_member(cls.clinic, role=role, user=user)
            return user

        cls.manager = staff_user("manager", StaffRole.MANAGER)
        cls.receptionist = staff_user("reception", StaffRole.RECEPTIONIST)

    def test_managers_may_read_and_erase_own_clinic_transcripts_only(self):
        self.client.force_login(self.manager)
        url = reverse("admin:chatbot_chatconversation_change", args=[self.conversation.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_change_permission"])
        self.assertEqual(self.client.get(reverse("admin:chatbot_chatconversation_add")).status_code, 403)
        self.assertRedirects(self.client.get(self.other_url), reverse("admin:index"))
        delete_url = reverse("admin:chatbot_chatconversation_delete", args=[self.conversation.pk])
        self.client.post(delete_url, {"post": "yes"})
        self.assertFalse(ChatConversation.objects.filter(pk=self.conversation.pk).exists())

    def test_receptionists_cannot_read_transcripts(self):
        self.client.force_login(self.receptionist)
        response = self.client.get(reverse("admin:chatbot_chatconversation_changelist"))
        self.assertEqual(response.status_code, 403)
