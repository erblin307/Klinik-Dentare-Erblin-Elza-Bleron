from django.contrib import admin

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin, ClinicScopedInline
from apps.scheduling.models import WorkingHours

from .models import Dentist, DentistService, StaffMember


@admin.register(StaffMember)
class StaffMemberAdmin(ClinicScopedAdmin):
    list_display = ["full_name", "role", "clinic", "email", "is_active"]
    list_filter = [CLINIC_FILTER, "role", "is_active"]
    list_select_related = ["clinic"]
    search_fields = ["first_name", "last_name", "email"]
    autocomplete_fields = ["clinic", "user"]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Linking a login account grants access to the clinic: platform admins only.
        return fields if request.user.is_superuser else [*fields, "user"]


class DentistServiceInline(ClinicScopedInline):
    model = DentistService
    fields = ["service"]
    autocomplete_fields = ["service"]
    verbose_name_plural = "Services performed (only these can be booked)"


class WorkingHoursInline(ClinicScopedInline):
    model = WorkingHours
    fields = ["weekday", "start_time", "end_time"]
    ordering = ["weekday", "start_time"]
    verbose_name_plural = (
        "Weekly working hours (clinic time; a gap between two blocks on one day is a break)"
    )


@admin.register(Dentist)
class DentistAdmin(ClinicScopedAdmin):
    list_display = ["__str__", "clinic", "specialty", "is_bookable"]
    list_filter = [CLINIC_FILTER, "is_bookable"]
    list_select_related = ["clinic", "staff_member"]
    search_fields = ["staff_member__first_name", "staff_member__last_name"]
    autocomplete_fields = ["clinic", "staff_member"]
    inlines = [DentistServiceInline, WorkingHoursInline]
