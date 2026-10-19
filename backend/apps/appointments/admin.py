from django.contrib import admin

from apps.core.admin import ClinicScopedAdmin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(ClinicScopedAdmin):
    list_display = ["start_at", "end_at", "patient", "dentist", "service", "status", "clinic"]
    list_filter = ["clinic", "status", "source"]
    list_select_related = ["clinic", "patient", "dentist__staff_member", "service"]
    search_fields = ["patient__last_name", "patient__first_name"]
    autocomplete_fields = ["clinic", "patient", "dentist", "service"]
    date_hierarchy = "start_at"
    ordering = ["-start_at"]
