from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path(
        "clinics/<slug:clinic_slug>/conversations/",
        views.start_conversation,
        name="start-conversation",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/",
        views.post_message,
        name="post-message",
    ),
    path(
        "conversations/<uuid:conversation_id>/",
        views.delete_conversation,
        name="delete-conversation",
    ),
]
