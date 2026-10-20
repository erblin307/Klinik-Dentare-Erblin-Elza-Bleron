"""
JSON endpoints for the website chat (plain Django views, no REST framework).

POST   /api/chat/clinics/<slug>/conversations/   start; returns id, token and greeting
POST   /api/chat/conversations/<id>/messages/    {"message": "..."} or {"confirm_action": "<id>"}
DELETE /api/chat/conversations/<id>/             delete the conversation and its messages

Requests about a conversation authenticate with ``Authorization: Bearer
<token>``. No cookies are involved, so CSRF protection does not apply. The
clinic comes from the URL when starting and from the conversation afterwards,
never from the request body.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.clinics.models import Clinic

from . import ratelimit
from .engine import ChatEngine
from .models import ChatConversation, ChatLanguage

MAX_MESSAGE_CHARS = 1000
MAX_MESSAGES_PER_CONVERSATION = 60
MESSAGES_PER_MINUTE = 10
CONVERSATIONS_PER_HOUR_PER_CLIENT = 20


def _error(status, code):
    return JsonResponse({"error": code}, status=status)


def _client_key(request):
    # Behind a reverse proxy, configure it to set REMOTE_ADDR to the client address.
    return request.META.get("REMOTE_ADDR", "unknown")


def _json_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _authorized_conversation(request, conversation_id, *, lock, allow_expired=False):
    """``(conversation, None)`` or ``(None, error response)``."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    queryset = ChatConversation.objects.select_related("clinic").filter(public_id=conversation_id)
    if lock:
        queryset = queryset.select_for_update(nowait=True, of=("self",))
    try:
        with transaction.atomic():
            conversation = queryset.first()
    except DatabaseError:  # another message of this conversation is being processed
        return None, _error(409, "busy")
    # Unknown conversation and wrong token look the same: no enumeration.
    if conversation is None or not token or not conversation.token_matches(token):
        return None, _error(404, "not_found")
    if not conversation.clinic.is_active:
        return None, _error(404, "not_found")
    ttl = timedelta(minutes=settings.CHATBOT_CONVERSATION_TTL_MINUTES)
    if not allow_expired and conversation.last_activity_at < timezone.now() - ttl:
        return None, _error(410, "expired")
    return conversation, None


@csrf_exempt
@require_http_methods(["POST"])
def start_conversation(request, clinic_slug):
    clinic = Clinic.objects.filter(slug=clinic_slug, is_active=True).first()
    if clinic is None:
        return _error(404, "not_found")
    if not ratelimit.allow(
        f"chat-start:{_client_key(request)}",
        limit=CONVERSATIONS_PER_HOUR_PER_CLIENT,
        window_seconds=3600,
    ):
        return _error(429, "rate_limited")
    body = _json_body(request)
    if body is None:
        return _error(400, "invalid_json")
    language = body.get("language")
    if language not in ChatLanguage.values:
        language = settings.CHATBOT_DEFAULT_LANGUAGE

    conversation, token = ChatConversation.start(clinic=clinic, language=language)
    reply = ChatEngine(conversation).greeting()
    return JsonResponse(
        {"conversation_id": str(conversation.public_id), "token": token, **reply.as_dict()},
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
def post_message(request, conversation_id):
    body = _json_body(request)
    if body is None:
        return _error(400, "invalid_json")
    message = body.get("message", "")
    confirm_action = body.get("confirm_action")
    if not isinstance(message, str) or not (confirm_action is None or isinstance(confirm_action, str)):
        return _error(400, "invalid_message")
    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return _error(400, "message_too_long")
    if not message and confirm_action is None:
        return _error(400, "empty_message")

    # The row lock serialises messages of one conversation (flow state).
    with transaction.atomic():
        conversation, error = _authorized_conversation(request, conversation_id, lock=True)
        if error:
            return error
        if not ratelimit.allow(
            f"chat-message:{conversation.pk}", limit=MESSAGES_PER_MINUTE, window_seconds=60
        ):
            return _error(429, "rate_limited")
        if conversation.message_count >= MAX_MESSAGES_PER_CONVERSATION:
            return _error(429, "conversation_limit")
        reply = ChatEngine(conversation).handle(message, confirm_action=confirm_action)
    return JsonResponse(reply.as_dict())


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_conversation(request, conversation_id):
    with transaction.atomic():
        # Expired conversations may still be erased by their owner.
        conversation, error = _authorized_conversation(
            request, conversation_id, lock=True, allow_expired=True
        )
        if error:
            return error
        conversation.delete()
    return HttpResponse(status=204)
