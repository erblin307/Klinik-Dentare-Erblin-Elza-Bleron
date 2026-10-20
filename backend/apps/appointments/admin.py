from zoneinfo import ZoneInfo

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.utils import timezone

from apps.core.admin import CLINIC_FILTER, ClinicScopedAdmin

from . import booking
from .models import Appointment

ACTIVE_CHANGE_FIELDS = {"dentist", "start_at"}


class AppointmentAdminForm(forms.ModelForm):
    """
    Checks the booking rules while validating, so problems show up as form
    errors. Saving is done by ``AppointmentAdmin`` through the booking service.
    """

    class Meta:
        model = Appointment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status = self.fields.get("status")
        if self.instance.pk and status:
            allowed = {self.instance.status, *booking.allowed_statuses(self.instance)}
            status.choices = [choice for choice in status.choices if choice[0] in allowed]

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        # self.instance still holds the stored values here.
        if self.instance.pk is None:
            booking.validate_new_appointment(
                patient=cleaned["patient"],
                dentist=cleaned["dentist"],
                service=cleaned["service"],
                start_at=cleaned["start_at"],
            )
            return cleaned
        moved = ACTIVE_CHANGE_FIELDS & set(self.changed_data)
        if moved and "status" in self.changed_data:
            raise forms.ValidationError("Reschedule and change the status in separate steps.")
        if moved:
            booking.validate_reschedule(
                self.instance, start_at=cleaned["start_at"], dentist=cleaned["dentist"]
            )
        elif "status" in self.changed_data:
            booking.validate_status_change(self.instance, cleaned["status"])
        return cleaned


@admin.register(Appointment)
class AppointmentAdmin(ClinicScopedAdmin):
    form = AppointmentAdminForm
    list_display = ["clinic_time", "patient", "dentist", "service", "status", "reference", "clinic"]
    list_filter = [
        CLINIC_FILTER,
        ("dentist", admin.RelatedOnlyFieldListFilter),
        "status",
        "source",
    ]
    list_select_related = ["clinic", "patient", "dentist__staff_member", "service"]
    search_fields = ["patient__last_name", "patient__first_name", "=reference"]
    autocomplete_fields = ["patient", "dentist", "service"]
    date_hierarchy = "start_at"
    ordering = ["-start_at"]
    actions = ["cancel_selected"]

    add_fields = ["patient", "dentist", "service", "start_at", "source", "notes"]
    change_fields = [
        "clinic", "reference", "patient", "service", "dentist", "start_at", "end_at",
        "status", "source", "notes", "created_at", "updated_at",
    ]  # fmt: skip

    def get_fields(self, request, obj=None):
        return self.change_fields if obj else self.add_fields

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return [*fields, "reference", "patient", "service", "end_at", "source"] if obj else fields

    @admin.display(description="Start (clinic time)", ordering="start_at")
    def clinic_time(self, obj):
        local = obj.start_at.astimezone(ZoneInfo(obj.clinic.timezone))
        return f"{local:%Y-%m-%d %H:%M} {local.tzname()}"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.pk = booking.create_appointment(
                patient=obj.patient,
                dentist=obj.dentist,
                service=obj.service,
                start_at=obj.start_at,
                source=obj.source,
                notes=obj.notes,
            ).pk
            obj._state.adding = False
        else:
            if ACTIVE_CHANGE_FIELDS & set(form.changed_data):
                booking.reschedule_appointment(obj, start_at=obj.start_at, dentist=obj.dentist)
            elif "status" in form.changed_data:
                booking.change_status(obj, obj.status)
            if "notes" in form.changed_data:
                Appointment.objects.filter(pk=obj.pk).update(
                    notes=obj.notes, updated_at=timezone.now()
                )
        obj.refresh_from_db()

    def changeform_view(self, request, *args, **kwargs):
        # The form validated, but a concurrent booking took the slot before
        # saving; the database constraint rejected ours. Report, don't crash.
        try:
            return super().changeform_view(request, *args, **kwargs)
        except booking.BookingError as error:
            self.message_user(request, error.messages[0], messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

    @admin.action(description="Cancel selected appointments", permissions=["change"])
    def cancel_selected(self, request, queryset):
        cancelled = refused = 0
        for appointment in queryset:
            if not self.has_change_permission(request, appointment):
                refused += 1
                continue
            try:
                booking.cancel_appointment(appointment)
                cancelled += 1
            except booking.BookingError:
                refused += 1
        if cancelled:
            self.message_user(request, f"Cancelled {cancelled} appointment(s).", messages.SUCCESS)
        if refused:
            self.message_user(
                request,
                f"{refused} appointment(s) could not be cancelled: they have started, "
                "are already final, or you lack permission.",
                messages.WARNING,
            )
