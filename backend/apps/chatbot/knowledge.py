"""
The clinic knowledge base given to the language model.

Everything is read from the database for one clinic: clinic details, active
services and prices, bookable dentists and their working hours, upcoming
clinic closures, and published ``KnowledgeEntry`` articles (policies, FAQs,
...) ranked by relevance to the question. Staff maintain all of it in the
Django admin. Patient data and internal notes are never included.
"""

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Case, IntegerField, Value, When

from apps.catalog.models import Service
from apps.knowledge.models import KnowledgeEntry
from apps.scheduling.models import TimeOff, Weekday
from apps.staff.models import Dentist

ENTRY_LIMIT = 8
ENTRY_CHAR_BUDGET = 6000
CLOSURE_HORIZON_DAYS = 60

_TERM = re.compile(r"[^\W\d_]+", re.UNICODE)
# Question words that would only add noise to the search.
_STOPWORDS = {
    "what", "when", "where", "which", "does", "have", "with", "your", "this", "that",
    "from", "about", "there", "would", "could", "please",
    "was", "wann", "wie", "welche", "haben", "ihre", "eine", "einen", "nicht", "sind", "bitte",
    "çfarë", "cfare", "kur", "keni", "juaj", "është", "eshte", "mund", "ju", "lutem",
}  # fmt: skip


def build_context(clinic, *, query, language, today):
    sections = [
        _clinic_section(clinic),
        _services_section(clinic),
        _dentists_section(clinic),
        _closures_section(clinic, today),
        _entries_section(clinic, query, language),
    ]
    return "\n\n".join(section for section in sections if section)


def relevant_entries(clinic, query, language, *, limit=ENTRY_LIMIT):
    """Published entries of the clinic, most relevant (then same language) first."""
    entries = KnowledgeEntry.objects.filter(clinic=clinic, is_published=True)
    terms = search_terms(query)
    if terms:
        vector = SearchVector("title", weight="A", config="simple") + SearchVector(
            "content", weight="B", config="simple"
        )
        # Prefix matching ("termin:*") copes with inflected forms (terminin, termineve).
        search = SearchQuery(" | ".join(f"{t}:*" for t in terms), search_type="raw", config="simple")
        entries = entries.annotate(rank=SearchRank(vector, search))
    else:
        entries = entries.annotate(rank=Value(0.0))
    entries = entries.annotate(
        same_language=Case(
            When(language=language, then=Value(1)), default=Value(0), output_field=IntegerField()
        )
    )
    return list(entries.order_by("-rank", "-same_language", "category", "title")[:limit])


def search_terms(query):
    """Distinct lower-case search prefixes; letters only, so safe for to_tsquery."""
    terms = []
    for token in _TERM.findall(query.lower()):
        if len(token) >= 4 and token not in _STOPWORDS:
            term = token[:6]
            if term not in terms:
                terms.append(term)
    return terms[:12]


def _clinic_section(clinic):
    lines = [f"Clinic name: {clinic.name}"]
    address = ", ".join(
        part for part in [clinic.address_line, clinic.postal_code, clinic.city, clinic.country] if part
    )
    for label, value in [
        ("Address", address),
        ("Phone", clinic.phone),
        ("E-mail", clinic.email),
        ("Time zone", clinic.timezone),
        ("Currency", clinic.currency),
    ]:
        if value:
            lines.append(f"{label}: {value}")
    return "## Clinic\n" + "\n".join(lines)


def _bookable_dentists(clinic):
    return (
        Dentist.objects.filter(clinic=clinic, is_bookable=True, staff_member__is_active=True)
        .select_related("staff_member")
        .prefetch_related("working_hours", "services")
        .order_by("staff_member__last_name", "staff_member__first_name")
    )


def _services_section(clinic):
    services = Service.objects.filter(clinic=clinic, is_active=True).order_by("name")
    performers = {}
    for dentist in _bookable_dentists(clinic):
        for service in dentist.services.all():
            performers.setdefault(service.pk, []).append(str(dentist))
    lines = []
    for service in services:
        price = (
            f"{service.price} {clinic.currency}" if service.price is not None
            else "price after consultation"
        )  # fmt: skip
        line = f"- {service.name}: {service.duration_minutes} min, {price}."
        if service.description:
            line += f" {service.description}"
        if service.pk in performers:
            line += f" Performed by: {', '.join(performers[service.pk])}."
        lines.append(line)
    if not lines:
        return "## Services\nNo services are listed."
    return "## Services (name: duration, price)\n" + "\n".join(lines)


def _dentists_section(clinic):
    lines = []
    for dentist in _bookable_dentists(clinic):
        line = f"- {dentist}"
        if dentist.specialty:
            line += f" ({dentist.specialty})"
        if dentist.bio:
            line += f": {dentist.bio}"
        days = {}
        for block in sorted(dentist.working_hours.all(), key=lambda b: (b.weekday, b.start_time)):
            days.setdefault(block.weekday, []).append(
                f"{block.start_time:%H:%M}–{block.end_time:%H:%M}"
            )
        hours = "; ".join(
            f"{Weekday(day).label} {', '.join(blocks)}" for day, blocks in sorted(days.items())
        )
        line += f"\n  Working hours: {hours or 'none'}"
        lines.append(line)
    if not lines:
        return "## Dentists\nNo dentists are listed."
    return (
        "## Dentists and working hours (clinic time; no entry for a day means no "
        "appointments that day; gaps are breaks)\n" + "\n".join(lines)
    )


def _closures_section(clinic, today):
    tz = ZoneInfo(clinic.timezone)
    window_start = datetime.combine(today, time(0), tzinfo=tz)
    closures = TimeOff.objects.filter(
        clinic=clinic,
        dentist__isnull=True,  # only clinic-wide closures; staff absences stay internal
        end_at__gt=window_start,
        start_at__lt=window_start + timedelta(days=CLOSURE_HORIZON_DAYS),
    ).order_by("start_at")
    lines = [
        f"- closed from {closure.start_at.astimezone(tz):%Y-%m-%d %H:%M} "
        f"to {closure.end_at.astimezone(tz):%Y-%m-%d %H:%M}"
        for closure in closures
    ]
    return "## Upcoming clinic closures (clinic time)\n" + "\n".join(lines) if lines else ""


def _entries_section(clinic, query, language):
    parts, used = [], 0
    for entry in relevant_entries(clinic, query, language):
        text = f"### {entry.title} [{entry.get_category_display()}, language: {entry.language}]\n{entry.content}"
        if used + len(text) > ENTRY_CHAR_BUDGET:
            break
        parts.append(text)
        used += len(text)
    if not parts:
        return "## Clinic information articles\nNone available."
    return "## Clinic information articles\n" + "\n\n".join(parts)
