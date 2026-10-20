from django.contrib import admin

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin

from .models import Service


@admin.register(Service)
class ServiceAdmin(ClinicScopedAdmin):
    list_display = ["name", "clinic", "duration_minutes", "price", "is_active"]
    list_filter = [CLINIC_FILTER, "is_active"]
    list_select_related = ["clinic"]
    search_fields = ["name"]
    autocomplete_fields = ["clinic"]
