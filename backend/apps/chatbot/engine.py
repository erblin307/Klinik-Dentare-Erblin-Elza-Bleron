"""
Conversation engine: decides what happens with each chat message.

1. The language is detected deterministically (``language``).
2. A pending action (book / cancel / reschedule) is executed only on an
   explicit confirmation: the API's ``confirm_action`` id, or a reply that is
   just "yes". The language model can never confirm anything.
3. Otherwise the model interprets the message (``interpreter``). The engine
   resolves names against the clinic's own records, drives the booking flows
   and calls ``apps.appointments.booking`` for every check and write — or lets
   the model answer a question from the knowledge base (``assistant``).

Existing appointments can only be changed with their booking reference. All
queries are limited to the conversation's clinic.
"""

import re
import secrets
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.appointments.booking import (
    RESCHEDULABLE_STATUSES,
    BookingError,
    BookingErrorCode,
    cancel_appointment,
    create_appointment,
    find_appointment,
    get_available_slots,
    normalize_reference,
    reschedule_appointment,
    validate_status_change,
)
from apps.appointments.models import Appointment, AppointmentSource, AppointmentStatus
from apps.catalog.models import Service
from apps.patients.models import Patient
from apps.staff.models import Dentist

from . import messages as msg
from .assistant import answer
from .details import clean_email, clean_name, clean_phone
from .interpreter import Interpretation, interpret
from .knowledge import build_context
from .language import detect_language, is_affirmative, is_negative
from .llm import LLMUnavailable, get_llm_client
from .models import ChatMessage, ChatRole

MAX_OPTIONS = 5
SEARCH_DAYS = 14
OPTION_GAP = timedelta(minutes=30)
MAX_REFERENCE_ATTEMPTS = 5
HISTORY_MESSAGES = 6
REQUIRED_DETAILS = ("first_name", "last_name", "phone")
FLOWS = ("book", "cancel", "reschedule")

# A booking reference typed in a message: 8 characters with at least one digit
# (references always contain one), optionally split by "-" or a space.
_REFERENCE_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{4}[- ]?[A-Za-z0-9]{4}(?![A-Za-z0-9])")


@dataclass
class ConversationState:
    flow: str | None = None
    service_id: int | None = None
    dentist_id: int | None = None
    appointment_id: int | None = None  # verified by its booking reference
    options: list = field(default_factory=list)  # [{"dentist_id": .., "start": iso}]
    selected: dict | None = None
    details: dict = field(default_factory=dict)  # first_name, last_name, phone, email
    pending: dict | None = None  # {"id": .., "type": .., ...}
    reference_attempts: int = 0

    @classmethod
    def load(cls, data):
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in (data or {}).items() if key in known})

    def start_flow(self, flow):
        self.flow = flow
        self.service_id = self.dentist_id = self.appointment_id = None
        self.options, self.selected, self.pending = [], None, None


@dataclass
class ChatReply:
    text: str
    language: str
    options: list = field(default_factory=list)
    pending_action: dict | None = None
    error: str | None = None

    def as_dict(self):
        return asdict(self)


class ChatEngine:
    def __init__(self, conversation, *, llm=None, now=None):
        self.conversation = conversation
        self.clinic = conversation.clinic
        self.llm = llm or get_llm_client()
        self.now = now or timezone.now()
        self.tz = ZoneInfo(self.clinic.timezone)
        self.state = ConversationState.load(conversation.state)
        self.language = conversation.language

    # -- public ---------------------------------------------------------------

    def greeting(self):
        text = msg.render("greeting", self.language, clinic=self.clinic.name)
        ChatMessage.objects.create(
            clinic=self.clinic, conversation=self.conversation, role=ChatRole.ASSISTANT, content=text
        )
        return self._reply(text)

    def handle(self, message="", *, confirm_action=None):
        history = self._history()
        if message:
            self.language = detect_language(message, self.language)
        try:
            reply = self._respond(message, confirm_action, history)
        except LLMUnavailable:
            reply = self._reply(
                msg.render("unavailable", self.language, contact=self._contact()),
                error="assistant_unavailable",
            )
        self._persist(message or "[confirmed]", reply)
        return reply

    # -- routing --------------------------------------------------------------

    def _respond(self, message, confirm_action, history):
        state = self.state
        if confirm_action is not None:
            return self._execute(confirm_action)
        if state.pending and is_affirmative(message):
            return self._execute(state.pending["id"])
        if state.pending and is_negative(message):
            state.pending = None
            return self._reply(msg.render("declined", self.language))

        interpretation = self._shortcut(message) or self._interpret(message, history)
        if state.pending:
            if interpretation.intent == "confirm":
                return self._reply(msg.render("confirm_hint", self.language), pending=state.pending)
            state.pending = None  # anything else abandons the proposal
            if interpretation.intent == "decline":
                return self._reply(msg.render("declined", self.language))
        return self._dispatch(interpretation, message, history)

    def _shortcut(self, message):
        """Unambiguous replies that need no language model."""
        text = message.strip()
        if self.state.options and text.isdigit():
            return Interpretation(intent="choose_slot", option=int(text))
        if self.state.flow in ("cancel", "reschedule") and not self.state.appointment_id:
            reference = _find_reference(message)
            if reference:
                return Interpretation(intent=self.state.flow, reference=reference)
        return None

    def _dispatch(self, interpretation, message, history):
        intent, flow = interpretation.intent, self.state.flow
        if intent == "medical":
            return self._reply(msg.render("medical", self.language, contact=self._contact()))
        if intent in FLOWS:
            if flow != intent:
                self.state.start_flow(intent)
            return self._flow_step(interpretation, message)
        if intent in ("choose_slot", "give_details") or (
            intent == "other" and interpretation.has_booking_data()
        ):
            if not flow:
                self.state.start_flow("book")
            return self._flow_step(interpretation, message)
        if flow and intent in ("confirm", "decline"):
            return self._flow_step(interpretation, message)
        return self._answer(message, history)

    def _flow_step(self, interpretation, message):
        step = {"book": self._book, "cancel": self._cancel, "reschedule": self._reschedule}
        return step[self.state.flow](interpretation, message)

    # -- flows ----------------------------------------------------------------

    def _book(self, interpretation, message):
        state = self.state
        if interpretation.phone and not clean_phone(interpretation.phone):
            return self._reply(msg.render("invalid_phone", self.language))
        self._merge_details(interpretation)  # first, so details given early are kept
        services = self._bookable_services()
        if not services:
            return self._reply(msg.render("no_services", self.language, contact=self._contact()))
        if interpretation.service:
            service = _best_match(interpretation.service, services, lambda s: s.name)
            if service is None:
                return self._ask_service(services)
            if service.pk != state.service_id:
                state.service_id, state.dentist_id = service.pk, None
                state.options, state.selected = [], None
        service = next((s for s in services if s.pk == state.service_id), None)
        if service is None:
            return self._ask_service(services)

        dentists = self._dentists_for(service)
        self._apply_dentist_choice(interpretation, dentists)
        candidates = [d for d in dentists if state.dentist_id in (None, d.pk)]
        slot_reply = self._slot_step(service, candidates, interpretation)
        if slot_reply:
            return slot_reply
        missing = [name for name in REQUIRED_DETAILS if not state.details.get(name)]
        if missing:
            labels = [msg.FIELD_LABELS[self.language][name] for name in missing]
            return self._reply(
                msg.render(
                    "ask_details",
                    self.language,
                    when=self._when(state.selected["start"]),
                    fields=msg.join(labels, self.language),
                )
            )
        dentist = self._dentist(state.selected["dentist_id"])
        details = state.details
        text = msg.render(
            "confirm_booking",
            self.language,
            service=service.name,
            dentist=dentist,
            when=self._when(state.selected["start"]),
            name=f"{details['first_name']} {details['last_name']}",
            phone=details["phone"],
        )
        return self._propose(
            text, type="book", service_id=service.pk, dentist_id=dentist.pk,
            start=state.selected["start"],
        )  # fmt: skip

    def _cancel(self, interpretation, message):
        appointment, reply = self._verified_appointment(interpretation, message)
        if reply:
            return reply
        try:
            validate_status_change(appointment, AppointmentStatus.CANCELLED, now=self.now)
        except BookingError:
            self.state.start_flow(None)
            return self._reply(msg.render("not_changeable", self.language, contact=self._contact()))
        text = msg.render(
            "confirm_cancel",
            self.language,
            service=appointment.service.name,
            dentist=appointment.dentist,
            when=self._when(appointment.start_at),
        )
        return self._propose(text, type="cancel", appointment_id=appointment.pk)

    def _reschedule(self, interpretation, message):
        state = self.state
        appointment, reply = self._verified_appointment(interpretation, message)
        if reply:
            return reply
        if appointment.status not in RESCHEDULABLE_STATUSES or appointment.start_at <= self.now:
            state.start_flow(None)
            return self._reply(msg.render("not_changeable", self.language, contact=self._contact()))

        intro = ""
        if not state.options and not state.selected:
            intro = msg.render(
                "current_appointment",
                self.language,
                service=appointment.service.name,
                dentist=appointment.dentist,
                when=self._when(appointment.start_at),
            ) + "\n"
        dentists = self._dentists_for(appointment.service)
        if state.dentist_id is None:
            state.dentist_id = appointment.dentist_id  # patients usually keep their dentist
        self._apply_dentist_choice(interpretation, dentists)
        candidates = [d for d in dentists if d.pk == state.dentist_id]
        slot_reply = self._slot_step(appointment.service, candidates, interpretation)
        if slot_reply:
            slot_reply.text = intro + slot_reply.text
            return slot_reply
        dentist = self._dentist(state.selected["dentist_id"])
        text = msg.render(
            "confirm_reschedule",
            self.language,
            service=appointment.service.name,
            old=self._when(appointment.start_at),
            new=self._when(state.selected["start"]),
            dentist=dentist,
        )
        return self._propose(
            text, type="reschedule", appointment_id=appointment.pk, dentist_id=dentist.pk,
            start=state.selected["start"],
        )  # fmt: skip

    # -- executing confirmed actions -------------------------------------------

    def _execute(self, action_id):
        pending = self.state.pending
        if not (pending and isinstance(action_id, str) and secrets.compare_digest(pending["id"], action_id)):
            return self._reply(msg.render("nothing_to_confirm", self.language))
        self.state.pending = None
        try:
            if pending["type"] == "book":
                return self._execute_booking(pending)
            appointment = self._appointment(pending["appointment_id"])
            if appointment is None:
                raise BookingError(BookingErrorCode.NOT_RESCHEDULABLE)
            if pending["type"] == "cancel":
                cancel_appointment(appointment, now=self.now)
                self.state.start_flow(None)
                return self._reply(
                    msg.render("cancelled", self.language, when=self._when(appointment.start_at))
                )
            moved = reschedule_appointment(
                appointment,
                start_at=datetime.fromisoformat(pending["start"]),
                dentist=self._dentist(pending["dentist_id"]),
                now=self.now,
            )
            self.state.start_flow(None)
            return self._reply(
                msg.render(
                    "rescheduled",
                    self.language,
                    when=self._when(moved.start_at),
                    dentist=moved.dentist,
                    reference=format_reference(moved.reference),
                )
            )
        except BookingError as error:
            return self._booking_failed(error)

    def _execute_booking(self, pending):
        service = Service.objects.filter(clinic=self.clinic, pk=pending["service_id"]).first()
        dentist = self._dentist(pending["dentist_id"])
        if service is None or dentist is None:
            raise BookingError(BookingErrorCode.SERVICE_UNAVAILABLE)
        appointment = create_appointment(
            patient=self._patient(),
            dentist=dentist,
            service=service,
            start_at=datetime.fromisoformat(pending["start"]),
            source=AppointmentSource.CHATBOT,
            now=self.now,
        )
        self.state.start_flow(None)
        self.state.details = {}  # data minimisation: not needed any more
        return self._reply(
            msg.render(
                "booked",
                self.language,
                service=service.name,
                dentist=dentist,
                when=self._when(appointment.start_at),
                reference=format_reference(appointment.reference),
            )
        )

    def _booking_failed(self, error):
        text = msg.render("failed", self.language, reason=msg.reason(error.code, self.language))
        self.state.options, self.state.selected = [], None
        if error.code in (BookingErrorCode.SLOT_TAKEN, BookingErrorCode.TIME_OFF) and self.state.flow:
            # Offer fresh times straight away.
            follow_up = self._flow_step(Interpretation(intent="choose_slot"), "")
            return self._reply(f"{text}\n{follow_up.text}", options=follow_up.options)
        return self._reply(text)

    # -- slots ----------------------------------------------------------------

    def _slot_step(self, service, dentists, interpretation):
        """Select a slot or return the reply that offers/asks for one."""
        state = self.state
        if interpretation.option is not None and state.options:
            if 1 <= interpretation.option <= len(state.options):
                state.selected, state.options = state.options[interpretation.option - 1], []
                return None
            return self._offer(service, "choose_from_list")
        if interpretation.date or interpretation.time or not (state.options or state.selected):
            found = self._find_slots(service, dentists, interpretation.date)
            if interpretation.time:
                exact = [s for s in found if s[0].astimezone(self.tz).time() == interpretation.time]
                if exact:
                    state.selected, state.options = _slot_entry(*exact[0]), []
                    return None
                found = [s for s in found if s[0].astimezone(self.tz).time() >= interpretation.time]
            state.selected = None
            state.options = [_slot_entry(*slot) for slot in _spread(found)]
            if not state.options:
                return self._reply(msg.render("no_slots", self.language, service=service.name))
            return self._offer(service, "offer_slots")
        if state.selected:
            return None
        return self._offer(service, "choose_from_list")

    def _find_slots(self, service, dentists, day):
        today = self.now.astimezone(self.tz).date()
        if day is not None and day < today:
            return []
        first, last = (day, day) if day else (today, today + timedelta(days=SEARCH_DAYS - 1))
        found = []
        for dentist in dentists:
            try:
                slots = get_available_slots(dentist, service, first, last, now=self.now)
            except BookingError:
                continue
            found += [(slot.start, dentist) for slot in slots]
        return sorted(found, key=lambda item: (item[0], item[1].pk))

    def _offer(self, service, template):
        lines, payload = [], []
        for number, option in enumerate(self.state.options, start=1):
            dentist = self._dentist(option["dentist_id"])
            start = datetime.fromisoformat(option["start"])
            lines.append(
                msg.render(
                    "option_line", self.language, number=number, when=self._when(start), dentist=dentist
                )
            )
            payload.append(
                {
                    "number": number,
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=service.duration_minutes)).isoformat(),
                    "dentist": str(dentist),
                }
            )
        text = msg.render(template, self.language, service=service.name, options="\n".join(lines))
        return self._reply(text, options=payload)

    # -- helpers --------------------------------------------------------------

    def _verified_appointment(self, interpretation, message):
        """The appointment proven by its booking reference, or a reply asking for it."""
        state = self.state
        if state.appointment_id:
            appointment = self._appointment(state.appointment_id)
            if appointment:
                return appointment, None
        reference = _find_reference(message) or normalize_reference(interpretation.reference or "")
        if reference is None:
            return None, self._reply(msg.render("ask_reference", self.language))
        if state.reference_attempts >= MAX_REFERENCE_ATTEMPTS:
            return None, self._reply(
                msg.render("too_many_attempts", self.language, contact=self._contact())
            )
        appointment = find_appointment(self.clinic, reference)
        if appointment is None:
            state.reference_attempts += 1
            return None, self._reply(msg.render("reference_not_found", self.language))
        state.appointment_id = appointment.pk
        return appointment, None

    def _apply_dentist_choice(self, interpretation, dentists):
        if interpretation.dentist:
            dentist = _best_match(interpretation.dentist, dentists, lambda d: d.staff_member.full_name)
            if dentist and dentist.pk != self.state.dentist_id:
                self.state.dentist_id = dentist.pk
                self.state.options, self.state.selected = [], None

    def _merge_details(self, interpretation):
        cleaners = {
            "first_name": clean_name,
            "last_name": clean_name,
            "phone": clean_phone,
            "email": clean_email,
        }
        for name, cleaner in cleaners.items():
            value = getattr(interpretation, name)
            cleaned = cleaner(value) if value else None
            if cleaned:
                self.state.details[name] = cleaned

    def _patient(self):
        details = self.state.details
        patient = Patient.objects.filter(
            clinic=self.clinic,
            is_active=True,
            first_name__iexact=details["first_name"],
            last_name__iexact=details["last_name"],
            phone=details["phone"],
        ).first()
        return patient or Patient.objects.create(
            clinic=self.clinic,
            first_name=details["first_name"],
            last_name=details["last_name"],
            phone=details["phone"],
            email=details.get("email", ""),
        )

    def _bookable_services(self):
        return list(
            Service.objects.filter(
                clinic=self.clinic,
                is_active=True,
                dentist_links__dentist__is_bookable=True,
                dentist_links__dentist__staff_member__is_active=True,
            )
            .distinct()
            .order_by("name")
        )

    def _dentists_for(self, service):
        return list(
            Dentist.objects.filter(
                clinic=self.clinic,
                is_bookable=True,
                staff_member__is_active=True,
                service_links__service=service,
            )
            .select_related("staff_member", "clinic")
            .order_by("staff_member__last_name", "staff_member__first_name")
        )

    def _dentist(self, pk):
        return Dentist.objects.select_related("staff_member", "clinic").filter(clinic=self.clinic, pk=pk).first()

    def _appointment(self, pk):
        return (
            Appointment.objects.select_related("service", "dentist__staff_member", "dentist__clinic", "patient")
            .filter(clinic=self.clinic, pk=pk)
            .first()
        )

    def _ask_service(self, services):
        names = msg.join([service.name for service in services], self.language)
        return self._reply(msg.render("ask_service", self.language, services=names))

    def _answer(self, message, history):
        context = build_context(
            self.clinic,
            query=message,
            language=self.language,
            today=self.now.astimezone(self.tz).date(),
        )
        text = answer(
            self.llm,
            clinic_name=self.clinic.name,
            contact=self._contact(),
            context=context,
            history=history,
            message=message,
            language=self.language,
        )
        return self._reply(text)

    def _interpret(self, message, history):
        dentists = Dentist.objects.filter(
            clinic=self.clinic, is_bookable=True, staff_member__is_active=True
        ).select_related("staff_member")
        return interpret(
            self.llm,
            message=message,
            history=history,
            today=self.now.astimezone(self.tz).date(),
            services=[service.name for service in self._bookable_services()],
            dentists=[str(dentist) for dentist in dentists],
            option_count=len(self.state.options),
            language=self.language,
        )

    def _history(self):
        recent = self.conversation.messages.order_by("-id")[:HISTORY_MESSAGES]
        return [{"role": m.role, "content": m.content} for m in reversed(recent)]

    def _propose(self, text, **action):
        action["id"] = secrets.token_urlsafe(12)
        self.state.pending = action
        return self._reply(text, pending=action)

    def _persist(self, user_text, reply):
        ChatMessage.objects.bulk_create(
            [
                ChatMessage(clinic=self.clinic, conversation=self.conversation, role=ChatRole.USER, content=user_text),
                ChatMessage(clinic=self.clinic, conversation=self.conversation, role=ChatRole.ASSISTANT, content=reply.text),
            ]
        )  # fmt: skip
        conversation = self.conversation
        conversation.state = asdict(self.state)
        conversation.language = self.language
        conversation.message_count += 1
        conversation.last_activity_at = timezone.now()
        conversation.save(
            update_fields=["state", "language", "message_count", "last_activity_at", "updated_at"]
        )

    def _contact(self):
        return msg.contact(self.clinic, self.language)

    def _when(self, value):
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return msg.format_datetime(value.astimezone(self.tz), self.language)

    def _reply(self, text, *, options=None, pending=None, error=None):
        pending_action = None
        if pending:
            pending_action = {"id": pending["id"], "type": pending["type"]}
        return ChatReply(
            text=text, language=self.language, options=options or [], pending_action=pending_action, error=error
        )


def format_reference(reference):
    return f"{reference[:4]}-{reference[4:]}"


def _find_reference(message):
    for match in _REFERENCE_CANDIDATE.finditer(message):
        candidate = normalize_reference(match.group())
        if candidate and any(ch.isdigit() for ch in candidate):
            return candidate
    return None


def _slot_entry(start, dentist):
    return {"dentist_id": dentist.pk, "start": start.isoformat()}


def _spread(slots):
    """At most MAX_OPTIONS slots, at least OPTION_GAP apart, so the offer is varied."""
    chosen = []
    for start, dentist in slots:
        if chosen and start - chosen[-1][0] < OPTION_GAP:
            continue
        chosen.append((start, dentist))
        if len(chosen) == MAX_OPTIONS:
            break
    return chosen


def _normalize(text):
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def _best_match(query, items, name_of):
    """The item whose name equals, contains or shares a word with ``query``."""
    wanted = _normalize(query)
    if not wanted:
        return None
    names = [(_normalize(name_of(item)), item) for item in items]
    for name, item in names:
        if name == wanted:
            return item
    for name, item in names:
        if wanted in name or name in wanted:
            return item
    words = {w for w in re.findall(r"\w+", wanted) if len(w) >= 3 and w not in {"dr", "doktor", "doctor"}}
    for name, item in names:
        if words & set(re.findall(r"\w+", name)):
            return item
    return None
