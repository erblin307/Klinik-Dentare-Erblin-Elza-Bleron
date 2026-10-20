"""
Read-only JSON endpoints for the public clinic website.

They expose only public clinic information — the same the chatbot may use —
and real availability from the booking service. Nothing is written here:
appointments are booked through the chat API with its explicit confirmation.

GET /api/public/clinics/<slug>/                 clinic details, opening hours, closures
GET /api/public/clinics/<slug>/services/        active services
GET /api/public/clinics/<slug>/dentists/        bookable dentists with working hours
GET /api/public/clinics/<slug>/articles/        published knowledge articles (?language=, ?category=)
GET /api/public/clinics/<slug>/availability/    ?service=<id>&date=YYYY-MM-DD[&days=1..7][&dentist=<id>]
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.appointments.booking import BookingError, get_available_slots
from apps.catalog.models import Service
from apps.clinics.models import Clinic
from apps.core import ratelimit
from apps.knowledge.models import KnowledgeEntry
from apps.scheduling.models import TimeOff
from apps.staff.models import Dentist

CONTENT_MAX_AGE = 300
CLOSURE_HORIZON_DAYS = 60
MAX_AVAILABILITY_DAYS = 7
AVAILABILITY_STEP_MINUTES = 30
AVAILABILITY_REQUESTS_PER_MINUTE = 60


def _json(data, *, status=200, max_age=None):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = f"public, max-age={max_age}" if max_age else "no-store"
    return response


def _error(status, code):
    return _json({"error": code}, status=status)


def _clinic(slug):
    return Clinic.objects.filter(slug=slug, is_active=True).first()


def _bookable_dentists(clinic):
    return (
        Dentist.objects.filter(clinic=clinic, is_bookable=True, staff_member__is_active=True)
        .select_related("staff_member")
        .prefetch_related("working_hours", "services")
        .order_by("staff_member__last_name", "staff_member__first_name")
    )


def _hours(blocks):
    return [
        {"weekday": b.weekday, "start": f"{b.start_time:%H:%M}", "end": f"{b.end_time:%H:%M}"}
        for b in sorted(blocks, key=lambda b: (b.weekday, b.start_time))
    ]


@require_GET
def clinic_detail(request, clinic_slug):
    clinic = _clinic(clinic_slug)
    if clinic is None:
        return _error(404, "not_found")

    # Opening hours are derived from the bookable dentists' working hours:
    # per weekday, from the earliest start to the latest end.
    span = {}
    for dentist in _bookable_dentists(clinic):
        for block in dentist.working_hours.all():
            start, end = span.get(block.weekday, (block.start_time, block.end_time))
            span[block.weekday] = (min(start, block.start_time), max(end, block.end_time))
    opening_hours = [
        {"weekday": day, "start": f"{start:%H:%M}", "end": f"{end:%H:%M}"}
        for day, (start, end) in sorted(span.items())
    ]

    tz = ZoneInfo(clinic.timezone)
    window_start = datetime.combine(datetime.now(tz).date(), time(0), tzinfo=tz)
    closures = TimeOff.objects.filter(
        clinic=clinic,
        dentist__isnull=True,  # clinic-wide only; reasons and staff absences stay internal
        end_at__gt=window_start,
        start_at__lt=window_start + timedelta(days=CLOSURE_HORIZON_DAYS),
    ).order_by("start_at")

    return _json(
        {
            "name": clinic.name,
            "slug": clinic.slug,
            "email": clinic.email,
            "phone": clinic.phone,
            "address_line": clinic.address_line,
            "postal_code": clinic.postal_code,
            "city": clinic.city,
            "country": clinic.country,
            "timezone": clinic.timezone,
            "currency": clinic.currency,
            "opening_hours": opening_hours,
            "closures": [
                {"start": c.start_at.astimezone(tz).isoformat(), "end": c.end_at.astimezone(tz).isoformat()}
                for c in closures
            ],
        },
        max_age=CONTENT_MAX_AGE,
    )


@require_GET
def service_list(request, clinic_slug):
    clinic = _clinic(clinic_slug)
    if clinic is None:
        return _error(404, "not_found")
    performers = {}
    for dentist in _bookable_dentists(clinic):
        for service in dentist.services.all():
            performers.setdefault(service.pk, []).append(dentist.pk)
    services = [
        {
            "id": service.pk,
            "name": service.name,
            "description": service.description,
            "duration_minutes": service.duration_minutes,
            "price": None if service.price is None else str(service.price),
            "dentist_ids": performers.get(service.pk, []),
        }
        for service in Service.objects.filter(clinic=clinic, is_active=True).order_by("name")
    ]
    return _json({"currency": clinic.currency, "services": services}, max_age=CONTENT_MAX_AGE)


@require_GET
def dentist_list(request, clinic_slug):
    clinic = _clinic(clinic_slug)
    if clinic is None:
        return _error(404, "not_found")
    dentists = [
        {
            "id": dentist.pk,
            "name": str(dentist),
            "specialty": dentist.specialty,
            "bio": dentist.bio,
            "service_ids": sorted(s.pk for s in dentist.services.all() if s.is_active),
            "working_hours": _hours(dentist.working_hours.all()),
        }
        for dentist in _bookable_dentists(clinic)
    ]
    return _json({"dentists": dentists}, max_age=CONTENT_MAX_AGE)


@require_GET
def article_list(request, clinic_slug):
    clinic = _clinic(clinic_slug)
    if clinic is None:
        return _error(404, "not_found")
    articles = KnowledgeEntry.objects.filter(clinic=clinic, is_published=True)
    for parameter in ("language", "category"):
        if request.GET.get(parameter):
            articles = articles.filter(**{parameter: request.GET[parameter]})
    return _json(
        {
            "articles": [
                {
                    "id": a.pk,
                    "title": a.title,
                    "content": a.content,
                    "category": a.category,
                    "language": a.language,
                }
                for a in articles.order_by("category", "title")
            ]
        },
        max_age=CONTENT_MAX_AGE,
    )


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


@require_GET
def availability(request, clinic_slug):
    clinic = _clinic(clinic_slug)
    if clinic is None:
        return _error(404, "not_found")
    client = request.META.get("REMOTE_ADDR", "unknown")
    if not ratelimit.allow(
        f"availability:{client}", limit=AVAILABILITY_REQUESTS_PER_MINUTE, window_seconds=60
    ):
        return _error(429, "rate_limited")

    service_id = _positive_int(request.GET.get("service"))
    days = _positive_int(request.GET.get("days", "1"))
    try:
        first_day = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return _error(400, "invalid_date")
    if service_id is None:
        return _error(400, "invalid_service")
    if days is None or days > MAX_AVAILABILITY_DAYS:
        return _error(400, "invalid_days")
    service = Service.objects.filter(clinic=clinic, pk=service_id, is_active=True).first()
    if service is None:
        return _error(404, "unknown_service")

    dentists = _bookable_dentists(clinic).filter(service_links__service=service)
    if request.GET.get("dentist"):
        dentists = dentists.filter(pk=_positive_int(request.GET["dentist"]) or 0)

    slots = []
    for dentist in dentists:
        try:
            found = get_available_slots(
                dentist,
                service,
                first_day,
                first_day + timedelta(days=days - 1),
                step_minutes=AVAILABILITY_STEP_MINUTES,
            )
        except BookingError:
            continue
        slots += [
            {
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "dentist_id": dentist.pk,
                "dentist": str(dentist),
            }
            for slot in found
        ]
    slots.sort(key=lambda slot: (slot["start"], slot["dentist"]))
    return _json({"timezone": clinic.timezone, "service_id": service.pk, "slots": slots})
