from django.contrib import admin

from apps.core.admin import ClinicScopedAdmin, InheritClinicInlineFormSet

from .models import Dentist, DentistService, StaffMember


@admin.register(StaffMember)
class StaffMemberAdmin(ClinicScopedAdmin):
    list_display = ["full_name", "role", "clinic", "email", "is_active"]
    list_filter = ["clinic", "role", "is_active"]
    list_select_related = ["clinic"]
    search_fields = ["first_name", "last_name", "email"]
    autocomplete_fields = ["clinic", "user"]


class DentistServiceInline(admin.TabularInline):
    model = DentistService
    formset = InheritClinicInlineFormSet
    fields = ["service"]
    autocomplete_fields = ["service"]
    extra = 0


@admin.register(Dentist)
class DentistAdmin(ClinicScopedAdmin):
    list_display = ["__str__", "clinic", "specialty", "is_bookable"]
    list_filter = ["clinic", "is_bookable"]
    list_select_related = ["clinic", "staff_member"]
    search_fields = ["staff_member__first_name", "staff_member__last_name"]
    autocomplete_fields = ["clinic", "staff_member"]
    inlines = [DentistServiceInline]
