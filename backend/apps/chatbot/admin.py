from django.contrib import admin

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin, ClinicScopedInline

from .models import ChatConversation, ChatMessage


class ChatMessageInline(ClinicScopedInline):
    model = ChatMessage
    fields = readonly_fields = ["created_at", "role", "content"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatConversation)
class ChatConversationAdmin(ClinicScopedAdmin):
    """Read-only transcripts (for quality checks); deleting one erases it."""

    list_display = ["public_id", "clinic", "language", "message_count", "last_activity_at"]
    list_filter = [CLINIC_FILTER, "language"]
    list_select_related = ["clinic"]
    # The flow state (may hold typed contact details) and token hash are not shown.
    fields = readonly_fields = [
        "public_id", "clinic", "language", "message_count", "last_activity_at", "created_at",
    ]  # fmt: skip
    ordering = ["-last_activity_at"]
    inlines = [ChatMessageInline]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
