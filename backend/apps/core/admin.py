"""
Admin base classes that enforce clinic isolation for staff users.

Superusers see everything. Other users see only the clinics they are active
staff members of, with the permissions of their role there
(``apps.staff.access``).
"""

from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
from django.forms.models import BaseInlineFormSet
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.staff.access import accessible_clinic_ids, clinic_ids_with_perm

# A list filter offering only clinics that occur in the (already scoped) list.
CLINIC_FILTER = ("clinic", admin.RelatedOnlyFieldListFilter)


def scope_to_clinics(queryset, clinic_ids, lookup="clinic_id"):
    """Filter ``queryset`` to ``clinic_ids``; ``None`` means no restriction."""
    return queryset if clinic_ids is None else queryset.filter(**{f"{lookup}__in": clinic_ids})


class ClinicAccessMixin:
    """
    For ModelAdmin and inline classes:

    * object permissions use the user's role in the object's clinic (for an
      inline, the parent object's clinic);
    * foreign key choices only offer records of the user's clinics, and the
      ``clinic`` choice only clinics where the user may add this model;
    * datetime inputs state the time zone they are entered in.
    """

    def _has(self, request, action, obj):
        perm = f"{self.opts.app_label}.{get_permission_codename(action, self.opts)}"
        return request.user.has_perm(perm, obj)

    def has_view_permission(self, request, obj=None):
        return self._has(request, "view", obj) or self._has(request, "change", obj)

    def has_add_permission(self, request, obj=None):
        return self._has(request, "add", obj)

    def has_change_permission(self, request, obj=None):
        return self._has(request, "change", obj)

    def has_delete_permission(self, request, obj=None):
        return self._has(request, "delete", obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related = db_field.related_model
        if related is Clinic:
            add_perm = f"{self.opts.app_label}.{get_permission_codename('add', self.opts)}"
            kwargs["queryset"] = scope_to_clinics(
                Clinic.objects.all(), clinic_ids_with_perm(request.user, add_perm), "pk"
            )
        elif any(f.name == "clinic" for f in related._meta.concrete_fields):
            kwargs["queryset"] = scope_to_clinics(
                related._default_manager.all(), accessible_clinic_ids(request.user)
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.DateTimeField) and db_field.editable:
            hint = f"Time zone: {timezone.get_current_timezone_name()}."
            kwargs["help_text"] = f"{db_field.help_text} {hint}".strip()
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class ClinicScopedAdmin(ClinicAccessMixin, admin.ModelAdmin):
    """
    Defaults for admins of clinic-scoped models.

    A record's clinic is fixed once created: moving data between clinics is
    not a routine operation and is blocked by the database for linked rows.
    """

    list_filter = [CLINIC_FILTER]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return scope_to_clinics(super().get_queryset(request), accessible_clinic_ids(request.user))

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return [*fields, "clinic"] if obj else fields


class InheritClinicInlineFormSet(BaseInlineFormSet):
    """Inline rows take the clinic of their parent object (hide ``clinic``)."""

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.instance.clinic_id = self.instance.clinic_id
        return form


class ClinicScopedInline(ClinicAccessMixin, admin.TabularInline):
    """Tabular inline for a clinic-scoped child of a clinic-scoped parent."""

    formset = InheritClinicInlineFormSet
    extra = 0
