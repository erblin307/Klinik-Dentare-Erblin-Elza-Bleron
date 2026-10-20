"""
Client for a local Ollama server (https://github.com/ollama/ollama/blob/main/docs/api.md).

Only the ``/api/chat`` and ``/api/tags`` endpoints are used, over plain HTTP
with the standard library — no SDK, no external AI service. The model,
address and timeout are configured in settings (``OLLAMA_*``).
"""

import json
import urllib.error
import urllib.request

from django.conf import settings


# Ignore HTTP(S)_PROXY environment variables: prompts can contain personal
# data and must only travel to the configured (local) Ollama server.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LLMUnavailable(Exception):
    """The language model could not produce a usable answer."""


class OllamaClient:
    def __init__(self, *, base_url, model, timeout, temperature=0.2):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    def chat(self, messages, *, json_schema=None):
        """
        Send ``messages`` (``[{"role": ..., "content": ...}]``) and return the
        reply text. With ``json_schema`` the model is constrained to JSON that
        matches the schema (Ollama structured outputs).
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        data = self._request("/api/chat", payload)
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMUnavailable("Unexpected response from Ollama.") from exc

    def installed_models(self):
        return [model["name"] for model in self._request("/api/tags").get("models", [])]

    def _request(self, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            with _OPENER.open(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            # Never include prompt contents in the error: they may hold personal data.
            raise LLMUnavailable(f"Ollama request to {path} failed: {type(exc).__name__}") from exc


def get_llm_client():
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT_SECONDS,
    )
