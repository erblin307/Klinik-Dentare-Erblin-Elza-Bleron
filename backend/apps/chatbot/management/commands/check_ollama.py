from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.chatbot.llm import LLMUnavailable, get_llm_client


class Command(BaseCommand):
    help = "Check that the configured Ollama server is reachable and has the model."

    def handle(self, *args, **options):
        try:
            models = get_llm_client().installed_models()
        except LLMUnavailable as exc:
            raise CommandError(f"Ollama is not reachable at {settings.OLLAMA_BASE_URL}: {exc}")
        if settings.OLLAMA_MODEL not in models:
            raise CommandError(
                f"Model {settings.OLLAMA_MODEL!r} is not installed. "
                f"Run: ollama pull {settings.OLLAMA_MODEL}"
            )
        self.stdout.write(self.style.SUCCESS(f"Ollama OK, model {settings.OLLAMA_MODEL} available."))
