from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.core.constraints import SameClinicConstraint


class SchemaTests(TestCase):
    def test_models_and_migrations_are_in_sync(self):
        out = StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
        except SystemExit:
            self.fail(f"Model changes without a migration:\n{out.getvalue()}")

    def test_btree_gist_extension_is_installed(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")
            self.assertIsNotNone(cursor.fetchone())


class SameClinicConstraintTests(TestCase):
    def test_deconstruct_round_trip(self):
        constraint = SameClinicConstraint(field="dentist", name="example_same_clinic")
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "apps.core.constraints.SameClinicConstraint")
        self.assertEqual(kwargs, {"field": "dentist", "name": "example_same_clinic"})
        self.assertEqual(SameClinicConstraint(*args, **kwargs), constraint)
        self.assertNotEqual(
            SameClinicConstraint(field="patient", name="example_same_clinic"), constraint
        )
