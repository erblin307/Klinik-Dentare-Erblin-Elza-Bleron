from contextlib import contextmanager

from django.db import IntegrityError, transaction
from django.test import TestCase


class IntegrityTestCase(TestCase):
    @contextmanager
    def assertViolates(self, constraint_name):
        """Assert that the block fails on exactly the named database constraint."""
        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            yield
        diag = getattr(ctx.exception.__cause__, "diag", None)
        self.assertEqual(getattr(diag, "constraint_name", None), constraint_name)
