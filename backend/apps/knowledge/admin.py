from django.contrib import admin

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin

from .models import KnowledgeEntry


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(ClinicScopedAdmin):
    list_display = ["title", "category", "language", "is_published", "clinic", "updated_at"]
    list_filter = [CLINIC_FILTER, "category", "language", "is_published"]
    list_select_related = ["clinic"]
    search_fields = ["title", "content"]
    autocomplete_fields = ["clinic"]
