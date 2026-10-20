"""Test doubles for the language model."""

import json

from apps.chatbot.interpreter import SCHEMA
from apps.chatbot.llm import LLMUnavailable

EMPTY_INTERPRETATION = {name: None for name in SCHEMA["properties"]}


class FakeLLM:
    """
    Stands in for Ollama. Interpretation calls (with a JSON schema) return
    ``interpretations[message]`` (default: a question); answer calls return
    ``answer``. Every prompt is recorded in ``calls``.
    """

    def __init__(self, interpretations=None, answer="Fake answer."):
        self.interpretations = interpretations or {}
        self.answer = answer
        self.calls = []

    def chat(self, messages, *, json_schema=None):
        self.calls.append({"messages": messages, "structured": json_schema is not None})
        if json_schema is None:
            return self.answer
        data = self.interpretations.get(messages[-1]["content"], {"intent": "question"})
        return data if isinstance(data, str) else json.dumps({**EMPTY_INTERPRETATION, **data})

    @property
    def answer_calls(self):
        return [call for call in self.calls if not call["structured"]]

    def all_prompt_text(self):
        return "\n".join(m["content"] for call in self.calls for m in call["messages"])


class UnavailableLLM:
    def chat(self, messages, *, json_schema=None):
        raise LLMUnavailable("Ollama is down.")
