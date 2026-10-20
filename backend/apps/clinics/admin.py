from django.contrib import admin

from apps.core.admin import ClinicAccessMixin, scope_to_clinics
from apps.staff.access import accessible_clinic_ids

from .models import Clinic


@admin.register(Clinic)
class ClinicAdmin(ClinicAccessMixin, admin.ModelAdmin):
    list_display = ["name", "slug", "city", "timezone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "city"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return scope_to_clinics(
            super().get_queryset(request), accessible_clinic_ids(request.user), "pk"
        )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Identity and activation of a clinic are platform-level decisions.
        return fields if request.user.is_superuser else [*fields, "slug", "is_active"]

    def get_prepopulated_fields(self, request, obj=None):
        return super().get_prepopulated_fields(request, obj) if request.user.is_superuser else {}
