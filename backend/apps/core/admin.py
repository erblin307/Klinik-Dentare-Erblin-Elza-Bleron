from django.contrib import admin
from django.forms.models import BaseInlineFormSet


class ClinicScopedAdmin(admin.ModelAdmin):
    """
    Defaults for admins of clinic-scoped models.

    A record's clinic is fixed once created: moving data between clinics is
    not a routine operation and is blocked by the database for linked rows.
    """

    list_filter = ["clinic"]
    readonly_fields = ["created_at", "updated_at"]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return [*fields, "clinic"] if obj else fields


class InheritClinicInlineFormSet(BaseInlineFormSet):
    """Inline rows take the clinic of their parent object (hide ``clinic``)."""

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.instance.clinic_id = self.instance.clinic_id
        return form
