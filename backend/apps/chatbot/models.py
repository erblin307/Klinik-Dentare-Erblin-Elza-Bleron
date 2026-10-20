import hashlib
import secrets
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.constraints import SameClinicConstraint
from apps.core.models import ClinicScopedModel


class ChatLanguage(models.TextChoices):
    ALBANIAN = "sq", _("Albanian")
    ENGLISH = "en", _("English")
    GERMAN = "de", _("German")


class ChatRole(models.TextChoices):
    USER = "user", _("User")
    ASSISTANT = "assistant", _("Assistant")


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ChatConversation(ClinicScopedModel):
    """
    One chat with an (anonymous) website visitor. Contains personal data the
    visitor typed; deleted on request and after ``CHATBOT_RETENTION_DAYS``.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # SHA-256 of the bearer token; the token itself is only given to the client.
    token_hash = models.CharField(max_length=64, editable=False)
    language = models.CharField(max_length=2, choices=ChatLanguage.choices)
    # Booking-flow state (see apps.chatbot.engine.ConversationState).
    state = models.JSONField(default=dict, blank=True)
    message_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            # Target key for SameClinicConstraint foreign keys.
            models.UniqueConstraint(
                fields=["clinic", "id"], name="chatbot_chatconversation_clinic_key"
            ),
            models.CheckConstraint(
                condition=Q(language__in=ChatLanguage.values),
                name="chatbot_chatconversation_language_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["last_activity_at"], name="chatbot_conv_activity_idx"),
        ]

    def __str__(self):
        return f"Conversation {self.public_id}"

    @classmethod
    def start(cls, *, clinic, language):
        """Create a conversation; returns ``(conversation, token)``."""
        token = secrets.token_urlsafe(32)
        conversation = cls.objects.create(
            clinic=clinic, language=language, token_hash=hash_token(token)
        )
        return conversation, token

    def token_matches(self, token):
        return secrets.compare_digest(self.token_hash, hash_token(token))


class ChatMessage(ClinicScopedModel):
    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ChatRole.choices)
    content = models.TextField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=ChatRole.values), name="chatbot_chatmessage_role_valid"
            ),
            SameClinicConstraint(
                field="conversation", name="chatbot_chatmessage_conversation_same_clinic"
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()} message"
