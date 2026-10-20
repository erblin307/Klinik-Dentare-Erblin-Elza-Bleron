from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.chatbot.models import ChatConversation


class Command(BaseCommand):
    help = "Delete chat conversations (and their messages) older than the retention period."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.CHATBOT_RETENTION_DAYS)

    def handle(self, *args, days, **options):
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = ChatConversation.objects.filter(last_activity_at__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted} rows of chat data inactive for {days}+ days.")
