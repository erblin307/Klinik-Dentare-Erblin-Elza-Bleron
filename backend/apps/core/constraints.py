"""Database constraints for clinic (tenant) isolation."""

from django.core import checks
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models import BaseConstraint, UniqueConstraint
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils.translation import gettext_lazy as _


class SameClinicConstraint(BaseConstraint):
    """
    Guarantee that a foreign key of a clinic-scoped model points at a row of
    the same clinic.

    Implemented as a composite foreign key, e.g. for ``Appointment.dentist``::

        FOREIGN KEY (clinic_id, dentist_id) REFERENCES staff_dentist (clinic_id, id)

    Requirements, verified by ``manage.py check --database default`` (and
    automatically before every test run):

    * the constrained field is a ForeignKey/OneToOneField to the target's
      primary key, and both models have a ``clinic`` field;
    * the target declares ``UniqueConstraint(fields=["clinic", "id"])``,
      because PostgreSQL only accepts foreign keys onto unique column sets.

    Nullable foreign keys are allowed: PostgreSQL skips the check while the
    referencing column is NULL. ``validate()`` repeats the check in Python so
    forms (e.g. the admin) show a field error instead of a database error.
    """

    default_violation_error_message = _(
        "The selected record belongs to a different clinic."
    )

    def __init__(
        self, *, field, name, violation_error_code=None, violation_error_message=None
    ):
        self.field = field
        super().__init__(
            name=name,
            violation_error_code=violation_error_code,
            violation_error_message=violation_error_message,
        )

    def _sql_parts(self, model, schema_editor):
        quote = schema_editor.quote_name
        relation = model._meta.get_field(self.field)
        target = relation.related_model._meta
        columns = (model._meta.get_field("clinic").column, relation.column)
        target_columns = (target.get_field("clinic").column, relation.target_field.column)
        return (
            ", ".join(map(quote, columns)),
            quote(target.db_table),
            ", ".join(map(quote, target_columns)),
        )

    def constraint_sql(self, model, schema_editor):
        columns, target_table, target_columns = self._sql_parts(model, schema_editor)
        return (
            f"CONSTRAINT {schema_editor.quote_name(self.name)} "
            f"FOREIGN KEY ({columns}) REFERENCES {target_table} ({target_columns})"
        )

    def create_sql(self, model, schema_editor):
        table = schema_editor.quote_name(model._meta.db_table)
        return f"ALTER TABLE {table} ADD {self.constraint_sql(model, schema_editor)}"

    def remove_sql(self, model, schema_editor):
        quote = schema_editor.quote_name
        return f"ALTER TABLE {quote(model._meta.db_table)} DROP CONSTRAINT {quote(self.name)}"

    def validate(self, model, instance, exclude=None, using=DEFAULT_DB_ALIAS):
        if exclude and self.field in exclude:
            return
        relation = model._meta.get_field(self.field)
        related_pk = getattr(instance, relation.attname)
        if related_pk is None or instance.clinic_id is None:
            return
        related_clinic_id = (
            relation.related_model._base_manager.using(using)
            .filter(pk=related_pk)
            .values_list("clinic_id", flat=True)
            .first()
        )
        if related_clinic_id is not None and related_clinic_id != instance.clinic_id:
            raise ValidationError(
                {
                    self.field: ValidationError(
                        self.get_violation_error_message(),
                        code=self.violation_error_code,
                    )
                }
            )

    def _check(self, model, connection):
        label = model._meta.label
        try:
            relation = model._meta.get_field(self.field)
        except FieldDoesNotExist:
            relation = None
        if not (
            relation
            and relation.concrete
            and (relation.many_to_one or relation.one_to_one)
            and relation.target_field.primary_key
        ):
            return [
                checks.Error(
                    f"SameClinicConstraint '{self.name}': '{self.field}' must be a "
                    f"foreign key of {label} to another model's primary key.",
                    obj=model,
                    id="core.E001",
                )
            ]

        errors = []
        target = relation.related_model
        for scoped in (model, target):
            try:
                scoped._meta.get_field("clinic")
            except FieldDoesNotExist:
                errors.append(
                    checks.Error(
                        f"SameClinicConstraint '{self.name}': {scoped._meta.label} "
                        f"has no 'clinic' field.",
                        obj=model,
                        id="core.E002",
                    )
                )
        has_clinic_key = any(
            isinstance(constraint, UniqueConstraint)
            and constraint.condition is None
            and set(constraint.fields) == {"clinic", target._meta.pk.name}
            for constraint in target._meta.constraints
        )
        if not has_clinic_key:
            errors.append(
                checks.Error(
                    f"SameClinicConstraint '{self.name}': {target._meta.label} must "
                    f"declare UniqueConstraint(fields=['clinic', "
                    f"'{target._meta.pk.name}']).",
                    obj=model,
                    id="core.E003",
                )
            )
        return errors

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        kwargs["field"] = self.field
        return path, args, kwargs

    def __eq__(self, other):
        if isinstance(other, SameClinicConstraint):
            return (
                self.name == other.name
                and self.field == other.field
                and self.violation_error_code == other.violation_error_code
                and self.violation_error_message == other.violation_error_message
            )
        return super().__eq__(other)

    def __repr__(self):
        return f"<{self.__class__.__qualname__}: field={self.field!r} name={self.name!r}>"
