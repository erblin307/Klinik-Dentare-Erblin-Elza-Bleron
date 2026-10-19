from django.contrib import admin

from apps.core.admin import ClinicScopedAdmin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(ClinicScopedAdmin):
    # Keep the list view to identifying fields only; details stay on the form.
    list_display = ["last_name", "first_name", "clinic", "phone", "is_active"]
    list_filter = ["clinic", "is_active"]
    list_select_related = ["clinic"]
    search_fields = ["last_name", "first_name", "phone", "email"]
    autocomplete_fields = ["clinic"]
    ordering = ["last_name", "first_name"]
