# Written by hand: a unique column with a random default needs three steps so
# that existing rows each get their own value (a plain AddField would give all
# existing rows the same default and violate the unique constraint).

from django.db import migrations, models

import apps.appointments.models
from apps.appointments.models import generate_reference


def fill_references(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    used = set()
    for pk in Appointment.objects.filter(reference__isnull=True).values_list("pk", flat=True):
        reference = generate_reference()
        while reference in used:
            reference = generate_reference()
        used.add(reference)
        Appointment.objects.filter(pk=pk).update(reference=reference)


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="reference",
            field=models.CharField(editable=False, max_length=8, null=True),
        ),
        migrations.RunPython(fill_references, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="appointment",
            name="reference",
            field=models.CharField(
                default=apps.appointments.models.generate_reference,
                editable=False,
                help_text="Secret code given to the patient; proves ownership of the booking.",
                max_length=8,
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("reference",), name="appointments_appointment_reference_key"
            ),
        ),
    ]
