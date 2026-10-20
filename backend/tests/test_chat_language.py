import string
from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.chatbot import messages
from apps.chatbot.language import detect_language, is_affirmative, is_negative

LANGUAGES = ("sq", "en", "de")


class LanguageDetectionTests(SimpleTestCase):
    def test_detects_albanian_english_and_german(self):
        cases = {
            "Sa kushton pastrimi i dhëmbëve?": "sq",
            "Dua të rezervoj një termin për nesër": "sq",
            "Pershendetje, a keni orar te premten?": "sq",
            "How much does a cleaning cost?": "en",
            "I would like to book an appointment tomorrow": "en",
            "Was kostet eine Zahnreinigung?": "de",
            "Ich möchte einen Termin für morgen buchen": "de",
            "Guten Tag, wann haben Sie geöffnet?": "de",
        }
        for text, language in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_language(text, default="en"), language)

    def test_messages_without_language_signal_keep_the_current_language(self):
        for text in ["10:00", "2", "+383 44 000 000", "AB3D-EF7H", "!!!"]:
            with self.subTest(text=text):
                self.assertEqual(detect_language(text, default="de"), "de")

    def test_explicit_yes_and_no(self):
        for text in ["yes", "Yes, please", "ok", "Po", "Po, konfirmoj!", "Ja", "Ja, bitte", "bestätigen"]:
            with self.subTest(text=text):
                self.assertTrue(is_affirmative(text))
                self.assertFalse(is_negative(text))
        for text in ["no", "No thanks", "Jo", "Nein", "nein danke"]:
            with self.subTest(text=text):
                self.assertTrue(is_negative(text))
                self.assertFalse(is_affirmative(text))

    def test_anything_more_than_a_plain_yes_is_not_a_confirmation(self):
        for text in ["yes, but at 11", "po, por nesër", "ja, aber später", "2", "sure thing buddy", ""]:
            with self.subTest(text=text):
                self.assertFalse(is_affirmative(text))


class MessageTemplateTests(SimpleTestCase):
    def test_every_template_exists_in_all_languages_with_the_same_placeholders(self):
        formatter = string.Formatter()
        for key, translations in messages.TEMPLATES.items():
            with self.subTest(key=key):
                self.assertEqual(set(translations), set(LANGUAGES))
                fields = {
                    language: {f for _, f, _, _ in formatter.parse(text) if f}
                    for language, text in translations.items()
                }
                self.assertEqual(len(set(map(frozenset, fields.values()))), 1, fields)
        for table in [messages.WEEKDAYS, messages.FIELD_LABELS, *messages.REASONS.values()]:
            self.assertEqual(set(table), set(LANGUAGES))

    def test_dates_are_formatted_per_language(self):
        value = datetime(2030, 1, 7, 10, 30, tzinfo=ZoneInfo("Europe/Tirane"))
        self.assertEqual(messages.format_datetime(value, "sq"), "e hënë, 07.01.2030, ora 10:30")
        self.assertEqual(messages.format_datetime(value, "en"), "Monday 07.01.2030 at 10:30")
        self.assertEqual(messages.format_datetime(value, "de"), "Montag, 07.01.2030, 10:30 Uhr")

    def test_lists_are_joined_per_language(self):
        items = ["A", "B", "C"]
        self.assertEqual(messages.join(items, "sq"), "A, B dhe C")
        self.assertEqual(messages.join(items, "en"), "A, B and C")
        self.assertEqual(messages.join(items, "de"), "A, B und C")
