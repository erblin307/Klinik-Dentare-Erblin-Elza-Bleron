from django.contrib import admin

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin

from .models import TimeOff, WorkingHours

DENTIST_FILTER = ("dentist", admin.RelatedOnlyFieldListFilter)


@admin.register(WorkingHours)
class WorkingHoursAdmin(ClinicScopedAdmin):
    list_display = ["dentist", "weekday", "start_time", "end_time", "clinic"]
    list_filter = [CLINIC_FILTER, DENTIST_FILTER, "weekday"]
    list_select_related = ["clinic", "dentist__staff_member"]
    autocomplete_fields = ["clinic", "dentist"]
    ordering = ["dentist", "weekday", "start_time"]


@admin.register(TimeOff)
class TimeOffAdmin(ClinicScopedAdmin):
    """Days off, vacations, one-off breaks and (without a dentist) clinic closures."""

    list_display = ["__str__", "clinic", "start_at", "end_at"]
    list_filter = [CLINIC_FILTER, DENTIST_FILTER]
    list_select_related = ["clinic", "dentist__staff_member"]
    autocomplete_fields = ["clinic", "dentist"]
    date_hierarchy = "start_at"
    ordering = ["-start_at"]
