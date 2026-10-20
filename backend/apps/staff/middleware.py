from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.clinics.models import Clinic

from .access import accessible_clinic_ids


class ClinicTimezoneMiddleware:
    """
    Show and enter datetimes in the clinic's time zone for staff users whose
    clinics share one time zone. Superusers and everyone else use
    ``settings.TIME_ZONE``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz = self._timezone_for(request.user)
        if tz:
            timezone.activate(tz)
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()

    @staticmethod
    def _timezone_for(user):
        if not user.is_authenticated:
            return None
        clinic_ids = accessible_clinic_ids(user)
        if not clinic_ids:  # None (superuser) or no clinics
            return None
        zones = set(Clinic.objects.filter(pk__in=clinic_ids).values_list("timezone", flat=True))
        return ZoneInfo(zones.pop()) if len(zones) == 1 else None
