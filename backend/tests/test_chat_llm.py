"""The Ollama client against a local stand-in server speaking Ollama's HTTP API."""

import json
import os
import threading
import urllib.request
from datetime import date, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from apps.chatbot.interpreter import SCHEMA, Interpretation
from apps.chatbot.llm import LLMUnavailable, OllamaClient


class FakeOllama(BaseHTTPRequestHandler):
    requests = []
    mode = "ok"

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append((self.path, body))
        if FakeOllama.mode == "error":
            self.send_response(500)
            self.end_headers()
            return
        payload = b"not json" if FakeOllama.mode == "garbage" else json.dumps(
            {"model": body["model"], "message": {"role": "assistant", "content": "Hi there"}, "done": True}
        ).encode()
        self._send(payload)

    def do_GET(self):
        self._send(json.dumps({"models": [{"name": "qwen2.5:7b"}]}).encode())

    def _send(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class OllamaClientTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def setUp(self):
        FakeOllama.requests, FakeOllama.mode = [], "ok"
        self.client = OllamaClient(base_url=self.url, model="qwen2.5:7b", timeout=5)

    def test_chat_sends_a_non_streaming_request_and_returns_the_reply(self):
        messages = [{"role": "user", "content": "Hello"}]
        self.assertEqual(self.client.chat(messages), "Hi there")
        path, body = FakeOllama.requests[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["model"], "qwen2.5:7b")
        self.assertEqual(body["messages"], messages)
        self.assertIs(body["stream"], False)
        self.assertNotIn("format", body)

    def test_structured_output_passes_the_json_schema(self):
        self.client.chat([{"role": "user", "content": "x"}], json_schema=SCHEMA)
        self.assertEqual(FakeOllama.requests[0][1]["format"], SCHEMA)

    def test_server_errors_and_bad_responses_become_llm_unavailable(self):
        for mode in ["error", "garbage"]:
            FakeOllama.mode = mode
            with self.subTest(mode=mode), self.assertRaises(LLMUnavailable):
                self.client.chat([{"role": "user", "content": "x"}])

    def test_unreachable_server_becomes_llm_unavailable(self):
        client = OllamaClient(base_url="http://127.0.0.1:9", model="m", timeout=2)
        with self.assertRaises(LLMUnavailable) as ctx:
            client.chat([{"role": "user", "content": "my phone is +000 123"}])
        self.assertNotIn("+000 123", str(ctx.exception))  # no prompt data in errors

    def test_proxy_environment_variables_are_ignored(self):
        bogus = "http://127.0.0.1:9"
        proxy_env = {"HTTP_PROXY": bogus, "http_proxy": bogus, "NO_PROXY": "", "no_proxy": ""}
        # Reset urllib's cached default opener so environment proxies would really apply.
        with mock.patch.dict(os.environ, proxy_env), mock.patch.object(urllib.request, "_opener", None):
            self.assertEqual(self.client.chat([{"role": "user", "content": "x"}]), "Hi there")

    def test_check_ollama_command(self):
        out = StringIO()
        with override_settings(OLLAMA_BASE_URL=self.url, OLLAMA_MODEL="qwen2.5:7b"):
            call_command("check_ollama", stdout=out)
        self.assertIn("Ollama OK", out.getvalue())
        with override_settings(OLLAMA_BASE_URL=self.url, OLLAMA_MODEL="missing:1b"):
            with self.assertRaisesMessage(CommandError, "ollama pull missing:1b"):
                call_command("check_ollama")
        with override_settings(OLLAMA_BASE_URL="http://127.0.0.1:9"):
            with self.assertRaisesMessage(CommandError, "not reachable"):
                call_command("check_ollama")


class InterpretationValidationTests(SimpleTestCase):
    def test_valid_output_is_parsed(self):
        result = Interpretation.from_json(json.dumps({
            "intent": "book", "service": " Check-up ", "date": "2030-01-07", "time": "10:30",
            "option": 2, "first_name": "Arta", "phone": "+000 1234567",
        }))  # fmt: skip
        self.assertEqual(result.intent, "book")
        self.assertEqual(result.service, "Check-up")
        self.assertEqual((result.date, result.time, result.option), (date(2030, 1, 7), time(10, 30), 2))

    def test_malformed_or_unexpected_output_is_dropped(self):
        for raw in ["not json", "[1, 2]", "null", json.dumps({"intent": "drop_database"})]:
            with self.subTest(raw=raw):
                self.assertEqual(Interpretation.from_json(raw), Interpretation())
        result = Interpretation.from_json(json.dumps({
            "intent": "book", "date": "next week", "time": "25:99", "option": True,
            "service": 42, "sql": "DROP TABLE x", "phone": "x" * 500,
        }))  # fmt: skip
        self.assertEqual((result.date, result.time, result.option, result.service), (None,) * 4)
        self.assertEqual(len(result.phone), 150)
        self.assertFalse(hasattr(result, "sql"))
