from django.contrib import admin

from .models import Clinic


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "city", "timezone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "city"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created_at", "updated_at"]
