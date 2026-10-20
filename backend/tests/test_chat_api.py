import threading
import uuid
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.db import connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.chatbot import views
from apps.chatbot.models import ChatConversation, ChatMessage

from .chat_support import FakeLLM
from .factories import make_bookable_dentist, make_clinic, make_service


def start_url(slug):
    return reverse("chatbot:start-conversation", args=[slug])


def message_url(conversation_id):
    return reverse("chatbot:post-message", args=[conversation_id])


def delete_url(conversation_id):
    return reverse("chatbot:delete-conversation", args=[conversation_id])


class ChatApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic(slug="smile", timezone="Europe/Tirane")
        cls.service = make_service(cls.clinic, name="Check-up")
        cls.dentist = make_bookable_dentist(cls.clinic, services=[cls.service], weekdays=range(7))

    def setUp(self):
        cache.clear()  # rate-limit counters
        self.llm = FakeLLM(answer="We are happy to help.")
        patcher = mock.patch("apps.chatbot.engine.get_llm_client", return_value=self.llm)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self, **body):
        response = self.client.post(start_url("smile"), body, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def send(self, conversation, token=None, **body):
        token = conversation["token"] if token is None else token
        return self.client.post(
            message_url(conversation["conversation_id"]),
            body,
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )


class StartConversationTests(ChatApiTestCase):
    def test_starts_with_a_greeting_in_the_requested_or_default_language(self):
        data = self.start(language="de")
        self.assertEqual(data["language"], "de")
        self.assertIn("Guten Tag", data["text"])
        self.assertEqual(set(data), {"conversation_id", "token", "text", "language", "options", "pending_action", "error"})
        self.assertIn("Përshëndetje", self.start()["text"])  # CHATBOT_DEFAULT_LANGUAGE = sq
        self.assertEqual(self.start(language="fr")["language"], "sq")

    def test_only_a_hash_of_the_token_is_stored(self):
        data = self.start()
        conversation = ChatConversation.objects.get(public_id=data["conversation_id"])
        self.assertNotEqual(conversation.token_hash, data["token"])
        self.assertTrue(conversation.token_matches(data["token"]))
        self.assertEqual(conversation.clinic, self.clinic)

    def test_unknown_or_inactive_clinics_are_not_found(self):
        make_clinic(slug="closed", is_active=False)
        for slug in ["nope", "closed"]:
            self.assertEqual(self.client.post(start_url(slug)).status_code, 404)

    def test_starting_is_rate_limited_per_client(self):
        for _ in range(views.CONVERSATIONS_PER_HOUR_PER_CLIENT):
            self.start()
        response = self.client.post(start_url("smile"))
        self.assertEqual((response.status_code, response.json()), (429, {"error": "rate_limited"}))

    def test_invalid_json_and_wrong_method(self):
        response = self.client.post(start_url("smile"), "{oops", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(start_url("smile")).status_code, 405)


class MessageTests(ChatApiTestCase):
    def test_reply_shape(self):
        response = self.send(self.start(), message="Do you have parking?")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"text": "We are happy to help.", "language": "en", "options": [], "pending_action": None, "error": None},
        )

    def test_conversations_require_their_own_token(self):
        conversation, other = self.start(), self.start()
        for token in ["", "wrong", other["token"]]:
            with self.subTest(token=token):
                response = self.send(conversation, token=token or False, message="Hi")
                self.assertEqual(response.status_code, 404)
        unknown = {"conversation_id": str(uuid.uuid4()), "token": conversation["token"]}
        self.assertEqual(self.send(unknown, message="Hi").status_code, 404)

    def test_invalid_messages_are_rejected(self):
        conversation = self.start()
        cases = [
            {"message": ""},
            {"message": 42},
            {"confirm_action": ["x"]},
            {"message": "x" * (views.MAX_MESSAGE_CHARS + 1)},
        ]
        for body in cases:
            with self.subTest(body=str(body)[:40]):
                self.assertEqual(self.send(conversation, **body).status_code, 400)

    def test_expired_conversations_are_gone(self):
        conversation = self.start()
        ChatConversation.objects.filter(public_id=conversation["conversation_id"]).update(
            last_activity_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(self.send(conversation, message="Hi").status_code, 410)

    def test_message_limits(self):
        conversation = self.start()
        for _ in range(views.MESSAGES_PER_MINUTE):
            self.assertEqual(self.send(conversation, message="Hi").status_code, 200)
        self.assertEqual(self.send(conversation, message="Hi").status_code, 429)

        cache.clear()
        ChatConversation.objects.filter(public_id=conversation["conversation_id"]).update(
            message_count=views.MAX_MESSAGES_PER_CONVERSATION
        )
        response = self.send(conversation, message="Hi")
        self.assertEqual((response.status_code, response.json()["error"]), (429, "conversation_limit"))

    def test_csrf_is_not_needed_because_no_cookies_are_used(self):
        self.client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.send(self.start(), message="Hi").status_code, 200)

    def test_booking_through_the_api_with_the_confirm_button(self):
        conversation = self.start(language="en")
        day = (timezone.now() + timedelta(days=2)).date().isoformat()
        text = "Check-up at 10:00, I am Arta Krasniqi, +000 44 123 456"
        self.llm.interpretations[text] = {
            "intent": "book", "service": "Check-up", "date": day, "time": "10:00",
            "first_name": "Arta", "last_name": "Krasniqi", "phone": "+000 44 123 456",
        }  # fmt: skip
        proposal = self.send(conversation, message=text).json()
        self.assertEqual(proposal["pending_action"]["type"], "book")
        self.assertFalse(Appointment.objects.exists())

        reply = self.send(conversation, confirm_action=proposal["pending_action"]["id"]).json()
        appointment = Appointment.objects.get()
        self.assertIn(appointment.reference[:4], reply["text"])
        self.assertEqual(appointment.clinic, self.clinic)


class DeleteConversationTests(ChatApiTestCase):
    def test_owner_can_erase_the_conversation(self):
        conversation = self.start()
        self.send(conversation, message="My name is Arta")
        headers = {"Authorization": f"Bearer {conversation['token']}"}
        url = delete_url(conversation["conversation_id"])
        self.assertEqual(self.client.delete(url).status_code, 404)  # token required
        self.assertEqual(self.client.delete(url, headers=headers).status_code, 204)
        self.assertFalse(ChatConversation.objects.exists())
        self.assertFalse(ChatMessage.objects.exists())
        self.assertEqual(self.client.delete(url, headers=headers).status_code, 404)

    def test_expired_conversations_can_still_be_erased(self):
        conversation = self.start()
        ChatConversation.objects.update(last_activity_at=timezone.now() - timedelta(days=5))
        headers = {"Authorization": f"Bearer {conversation['token']}"}
        response = self.client.delete(delete_url(conversation["conversation_id"]), headers=headers)
        self.assertEqual(response.status_code, 204)


class ConcurrentMessageTests(TransactionTestCase):
    def test_a_second_message_while_one_is_processed_gets_409(self):
        clinic = make_clinic(slug="busy")
        conversation, token = ChatConversation.start(clinic=clinic, language="en")
        locked, release = threading.Event(), threading.Event()

        def hold_lock():
            try:
                with transaction.atomic():
                    ChatConversation.objects.select_for_update().get(pk=conversation.pk)
                    locked.set()
                    release.wait(10)
            finally:
                connections.close_all()

        thread = threading.Thread(target=hold_lock)
        thread.start()
        locked.wait(10)
        try:
            response = self.client.post(
                message_url(conversation.public_id),
                {"message": "Hi"},
                content_type="application/json",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            release.set()
            thread.join(10)
        self.assertEqual((response.status_code, response.json()), (409, {"error": "busy"}))
