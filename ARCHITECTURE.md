# Architecture

A reusable Dental Clinic SaaS demo. This document describes the system as it
is built today and the decisions behind it. Rules for working on it are in
`PROJECT_RULES.md`.

## 1. System overview

| Layer          | Technology               | Status                       |
| -------------- | ------------------------ | ---------------------------- |
| Backend, admin | Django 5.2 LTS (Python)  | Schema (Task 1); admin and booking engine (Task 2) |
| Database       | Supabase PostgreSQL      | Schema and migrations ready  |
| Frontend       | Next.js + TypeScript     | Website and chat widget (Task 4) |
| AI assistant   | Ollama (local models)    | Chatbot backend and API (Task 3) |

Django owns the database schema: all tables are created by Django migrations,
and Django connects to Supabase as a plain PostgreSQL client. Supabase's own
APIs (Data API, Auth, Storage) are not used.

## 2. Repository layout

```
.
├── ARCHITECTURE.md
├── PROJECT_RULES.md
└── backend/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example          # placeholders only; real values in backend/.env
    ├── config/               # settings, URLs, WSGI/ASGI
    ├── apps/
    │   ├── core/             # abstract base models, tenant constraint, admin base
    │   ├── accounts/         # custom User model (admin logins)
    │   ├── clinics/          # Clinic — the tenant
    │   ├── catalog/          # Service — treatments offered
    │   ├── staff/            # StaffMember, Dentist, DentistService; access control
    │   ├── patients/         # Patient
    │   ├── scheduling/       # WorkingHours, TimeOff
    │   ├── appointments/     # Appointment; booking engine (booking.py)
    │   ├── knowledge/        # KnowledgeEntry — curated content for the AI
    │   ├── chatbot/          # chat engine, Ollama client, chat API, transcripts
    │   └── website/          # read-only public API for the website
    └── tests/                # backend tests (cross-app)
frontend/                     # Next.js website and chat widget (see frontend/README.md)
```

### App dependencies

Apps only depend downwards (`→` means "depends on"; every app also uses
`core`, which depends on nothing project-specific and refers to
`clinics.Clinic` by string only):

```
clinics      → core
catalog      → clinics
staff        → clinics, catalog, accounts
patients     → clinics
scheduling   → clinics, staff
appointments → clinics, staff, patients, catalog, scheduling
knowledge    → clinics
chatbot      → clinics, catalog, staff, patients, scheduling, appointments, knowledge
website      → clinics, catalog, staff, scheduling, appointments, knowledge
```

`apps/core/ratelimit.py` (cache-based fixed-window limits) is shared by the
chat and website APIs.

The graph applies to models and services. `admin.py` modules are the
presentation layer: they may import any app, and all of them use
`apps.staff.access` for clinic scoping (section 7).

## 3. Data model

All primary keys are `bigint` identities. All timestamps are `timestamptz`
stored in UTC. Every model except `User` and `Clinic` is clinic-scoped and has
`clinic_id`, `created_at` and `updated_at`.

```mermaid
erDiagram
    Clinic ||--o{ StaffMember : employs
    Clinic ||--o{ Service : offers
    Clinic ||--o{ Patient : treats
    User |o--o{ StaffMember : "logs in as"
    StaffMember ||--o| Dentist : "clinical profile"
    Dentist ||--o{ DentistService : performs
    Service ||--o{ DentistService : "performed by"
    Dentist ||--o{ WorkingHours : works
    Dentist |o--o{ TimeOff : "is away (empty = whole clinic)"
    Dentist ||--o{ Appointment : sees
    Patient ||--o{ Appointment : books
    Service ||--o{ Appointment : "is booked for"
    Clinic ||--o{ KnowledgeEntry : publishes
```

| Table                      | Purpose                                     | Key rules enforced by PostgreSQL |
| -------------------------- | ------------------------------------------- | -------------------------------- |
| `accounts_user`            | Admin/staff login accounts                  | Django auth defaults |
| `clinics_clinic`           | Tenant: name, slug, contact, time zone, currency | unique `slug` |
| `catalog_service`          | Treatments, duration, optional price        | unique name per clinic; duration 5–480 min; price ≥ 0 |
| `staff_staffmember`        | People working at a clinic, role, optional login | valid role; a login linked once per clinic |
| `staff_dentist`            | Bookable clinical profile of a staff member | one profile per staff member; same clinic as staff member |
| `staff_dentistservice`     | Which dentist performs which service        | unique pair; both in the row's clinic |
| `scheduling_workinghours`  | Weekly recurring availability blocks        | weekday 0–6 (Mon–Sun); end > start; unique block start |
| `scheduling_timeoff`       | Absences; no dentist = clinic-wide closure  | end > start |
| `patients_patient`         | Patient contact data                        | — |
| `appointments_appointment` | Bookings, each with a secret booking `reference` | end > start; valid status/source; **no overlaps**; patient, dentist, service all in the appointment's clinic; unique reference |
| `knowledge_knowledgeentry` | Curated public content for the AI assistant | unique title per clinic + language; valid category |
| `chatbot_chatconversation` | A website chat: language, flow state, token hash | valid language |
| `chatbot_chatmessage`      | Transcript lines of a conversation          | valid role; same clinic as the conversation |

Deletion policy: clinics, patients, dentists and services that are referenced
by appointments are protected (`PROTECT`); deactivate them with `is_active` /
`is_bookable` instead. Schedules, time off and dentist–service links are
deleted with their dentist.

## 4. Multi-clinic isolation

Every clinic-scoped row stores `clinic_id`. A plain foreign key cannot stop an
appointment of clinic A from referencing a dentist of clinic B, so each
relation between clinic-scoped models is a **composite foreign key**:

```sql
-- target side
UNIQUE (clinic_id, id)                                   -- e.g. on staff_dentist
-- referencing side
FOREIGN KEY (clinic_id, dentist_id) REFERENCES staff_dentist (clinic_id, id)
```

This is declared in Python with `apps.core.constraints.SameClinicConstraint`,
so Django's migration autodetector tracks it like any built-in constraint,
`manage.py check --database default` (also run before every test run)
verifies its prerequisites, and model validation (admin
forms) reports a field error instead of a database error. The composite key
also makes it impossible to move a record to another clinic while other rows
still reference it.

Adding a new clinic-scoped model:

1. Inherit `ClinicScopedModel`.
2. For each foreign key to another clinic-scoped model, add
   `SameClinicConstraint(field=..., name=...)`.
3. If other models will reference it, add
   `UniqueConstraint(fields=["clinic", "id"], name="<app>_<model>_clinic_key")`.
4. If a migration creates the key and a constraint referencing it, make sure
   the key comes first (see the comment in `staff/migrations/0001_initial.py`).

Tests in `tests/test_clinic_isolation.py` fail if steps 1–2 are forgotten;
the system check (error `core.E003`) stops the test run if step 3 is.

The `clinic_id` column also drives admin access control (section 7) and is
the hook for future PostgreSQL Row Level Security policies.

## 5. Appointment overlap prevention

Double booking is prevented by PostgreSQL GiST **exclusion constraints**, so it
holds even for concurrent requests (two bookings racing for the same slot):

```sql
EXCLUDE USING gist (dentist_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
    WHERE (status NOT IN ('cancelled', 'no_show'))
EXCLUDE USING gist (patient_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
    WHERE (status NOT IN ('cancelled', 'no_show'))
```

- Intervals are half-open `[start, end)`: back-to-back appointments are fine.
- Cancelled and no-show appointments free their slot. Any other status —
  including statuses added in future — blocks it.
- A patient cannot be in two appointments at once, even with different
  dentists.
- The `btree_gist` extension (needed for `dentist_id WITH =`) is created by
  `appointments/migrations/0001_initial.py`.
- Django's model validation runs the same checks, so the admin shows
  "The dentist already has an appointment at this time." instead of an error page.

Cross-table rules — within working hours, outside time off, a dentist who
performs the service — are enforced by the booking service (section 6), not
the database. Working-hour blocks of one dentist are checked for overlap by
model validation only (overlapping blocks are merged when computing
availability, so they are harmless).

Two transactions inserting conflicting appointments at the same instant can
wait for each other inside the exclusion check; PostgreSQL's deadlock
detector then aborts one (SQLSTATE `40P01`). The booking service retries that
write, which then waits for the winner and fails with the real outcome
(`SLOT_TAKEN` / `PATIENT_BUSY`). Integrity never depends on this retry; only
the error reported to the loser does.

## 6. Booking engine

`apps/appointments/booking.py` is the only code that creates appointments or
changes their time, dentist or status. It takes model instances and plain
values (no request, no admin), so the admin, a future API and the chatbot
share it.

| Function | Purpose |
| -------- | ------- |
| `get_available_slots(dentist, service, start_date, end_date=None, *, step_minutes=15)` | Free slots of the service's duration on clinic-local dates (max 31 days). |
| `create_appointment(*, patient, dentist, service, start_at, source, notes)` | Validate and book; the appointment is **confirmed** immediately. |
| `reschedule_appointment(appointment, *, start_at, dentist=None)` | Move (optionally to another dentist), keeping the duration. |
| `cancel_appointment(appointment)` | Cancel before the start; frees the slot. |
| `change_status(appointment, status)` | Other transitions (check-in, completed, no-show). |
| `validate_new_appointment`, `validate_reschedule`, `validate_status_change` | The same checks without writing, for forms. |

A booking is accepted when, in this order: patient, dentist and service
belong to one active clinic; the dentist is bookable, active and performs the
service (`DentistService`); the patient is active; the start is timezone-aware
and not in the past; the whole interval lies within one working period;
it does not overlap the dentist's time off or a clinic closure; and neither
the dentist nor the patient has an overlapping active appointment.

Failures raise `BookingError`, a `ValidationError` subclass whose `code` is a
`BookingErrorCode` (e.g. `slot_taken`, `outside_working_hours`). Messages
contain no personal data.

Status lifecycle (anything else is refused; final states are never reopened,
a new booking is made instead):

| From | Allowed to |
| ---- | ---------- |
| `pending` | `confirmed`, `cancelled` |
| `confirmed` | `checked_in`, `cancelled` (only before the start), `no_show` (only after the start) |
| `checked_in` | `completed` |
| `completed`, `cancelled`, `no_show` | — (final) |

Rescheduling is possible for `pending` and `confirmed` appointments that have
not started, and leaves them `confirmed`.

Writes run in a transaction: reschedule and status changes lock the
appointment row (`SELECT … FOR UPDATE`); saves run in a savepoint, so a
failed booking leaves the caller's transaction usable. Availability is a
read-only snapshot — a slot can be taken between listing and booking, which
`create_appointment` reports as `SLOT_TAKEN`.

**Working hours, breaks and days off.** Breaks are gaps between two
`WorkingHours` blocks of one day (e.g. 09:00–13:00 and 14:00–18:00); adjacent
blocks merge. Days off, vacations and one-off breaks are `TimeOff` rows; a
`TimeOff` without a dentist closes the whole clinic.

## 7. Admin and access control

Superusers manage everything (platform administrators). Clinic staff log in
with a user that has `is_staff` set and is linked (by a superuser) to an
active `StaffMember` of an active clinic. Their permissions come from that
staff member's role, per clinic (`apps/staff/access.py`,
`ClinicRoleBackend`); Django groups are not used for clinic data.

| Role | Can manage | Can view |
| ---- | ---------- | -------- |
| Manager | services, staff, dentists, working hours, time off, knowledge (incl. delete); patients and appointments (no delete); own clinic details; chat transcripts (read and erase only) | everything of the clinic |
| Receptionist | patients, appointments, time off | services, staff, dentists, working hours, clinic |
| Dentist, hygienist, assistant | existing appointments (status, rescheduling); no new bookings | services, staff, dentists, schedules, patients, appointments, clinic |

All clinic-data admins inherit `ClinicScopedAdmin` / `ClinicScopedInline`
(`apps/core/admin.py`), which:

* show only rows of the user's clinics (lists, change pages, autocomplete,
  list filters); other clinics' records are not reachable by URL;
* check object permissions against the role in the object's clinic — a
  receptionist in clinic A who is a dentist in clinic B may edit patients of
  A but only view those of B;
* offer only the user's clinics in foreign-key choices, and in the `clinic`
  field only clinics where the user may add that kind of record;
* keep a record's clinic read-only after creation. Linking login accounts
  and changing a clinic's slug or active flag are superuser-only.

Appointments are added and edited through the booking service: the add form
asks for patient, dentist, service and start; the end, clinic and status
follow. Changing dentist or start reschedules, changing the status applies a
transition (the dropdown only offers allowed ones), and the list has a
"Cancel selected appointments" action. Rule violations are form errors; if a
concurrent booking takes the slot between validation and saving, the admin
shows the error message instead of failing.

The dentist page edits the weekly working hours and the services performed
inline; time off has its own list.

## 8. Chatbot

`apps/chatbot` answers questions about the clinic and books, cancels and
reschedules appointments in Albanian, English and German, with a local model
served by **Ollama**. No external or paid AI service is involved.

### Modules

| Module | Responsibility |
| ------ | -------------- |
| `llm.py` | Ollama HTTP client (`/api/chat`, standard library only; environment proxies ignored so prompts stay local) |
| `language.py` | Deterministic language detection (sq/en/de) and explicit yes/no recognition |
| `knowledge.py` | Builds the clinic context from the database (see below) |
| `interpreter.py` | LLM → validated `Interpretation` (intent + fields) via a JSON schema |
| `assistant.py` | LLM answers grounded in the clinic context |
| `messages.py` | Fixed texts in the three languages for everything booking-related |
| `engine.py` | Conversation flow; calls `apps.appointments.booking` for every check and write |
| `views.py` | JSON API, authentication, limits |

### What the model may and may not do

The model never acts. It is used for exactly two things:

1. **Interpreting** a message into a fixed JSON schema (intent from an
   allowlist, service/dentist names, date, time, option number, contact
   details, booking reference). Every value is re-validated; names are matched
   against the clinic's own records; malformed output becomes `other`.
2. **Answering questions** from the clinic context, under rules: only use the
   given information, say when something is unknown and give the clinic's
   contact, no diagnoses or medication advice, reply in the user's language.

Everything else is deterministic server code: slot search, the texts that
state times, dentists and references (`messages.py`, so they cannot be
distorted), and all writes through the booking service. The model has no
tools and no database access, so it cannot run SQL; medical questions get a
fixed safe reply.

### Booking through the chat

1. The visitor names a service (and optionally dentist, date, time). The
   engine searches real availability (`get_available_slots`, next 14 days or
   the requested date) and offers up to 5 numbered options, at least 30
   minutes apart; an exact requested time is selected directly.
2. It collects first name, last name and phone (validated).
3. It shows a summary as a **pending action**. Only an explicit confirmation
   executes it: the API's `confirm_action` with the action's id (the
   frontend's button), or a reply that consists only of "yes" words
   ("yes", "po", "ja", ...). A model judging a message as "confirm" is never
   enough.
4. `create_appointment` books and confirms; the reply contains the booking
   reference. If the slot was taken meanwhile, new options are offered.

The patient record is reused only when first name, last name and phone match
exactly (in that clinic); otherwise a new patient is created. Cancelling and
rescheduling require the **booking reference** (8 characters from an
unambiguous alphabet, always with a digit; looked up only in the
conversation's clinic; at most 5 wrong attempts per conversation), followed by
the same explicit confirmation.

### Knowledge base

Built per request from the database of the conversation's clinic — nothing
is hard-coded: clinic details (address, phone, e-mail), active services with
duration and price (or "after consultation"), bookable dentists with
specialty, profile and weekly working hours, upcoming clinic-wide closures,
and published `KnowledgeEntry` articles (policies, FAQs, ...). Articles are
ranked with PostgreSQL full-text search (`simple` configuration, prefix
matching for inflected words), same-language articles first, within a size
budget. Staff manage all of it in the admin; only published articles are
used. Patient data, internal notes, closure reasons and individual staff
absences are never included.

### API

| Method and path | Purpose |
| --------------- | ------- |
| `POST /api/chat/clinics/<slug>/conversations/` | Start; body `{"language": "sq"}` optional. Returns `conversation_id`, `token` and the greeting. |
| `POST /api/chat/conversations/<id>/messages/` | `{"message": "..."}` or `{"confirm_action": "<id>"}`. Returns `text`, `language`, `options`, `pending_action`, `error`. |
| `DELETE /api/chat/conversations/<id>/` | Erase the conversation and its messages. |

- Authentication: `Authorization: Bearer <token>`; only a SHA-256 hash of the
  token is stored. An unknown conversation and a wrong token both give `404`.
  No cookies are used, so the endpoints are CSRF-exempt.
- The clinic comes from the URL when starting and from the conversation
  afterwards, never from the request body.
- Limits: 1 000 characters per message, 10 messages per minute and 60 per
  conversation, 20 new conversations per client address per hour, expiry
  after `CHATBOT_CONVERSATION_TTL_MINUTES` of inactivity (`410`). A message
  sent while the previous one is still processed gets `409`.
- If Ollama is unreachable, the reply is a localised apology with the
  clinic's contact and `"error": "assistant_unavailable"`.

### Personal data

Visitors' messages (which may contain their name and phone) are stored for
the conversation's context, shown read-only to clinic managers in the admin,
erasable by the visitor (`DELETE`) or a manager, and deleted after
`CHATBOT_RETENTION_DAYS` by `python manage.py purge_chat_conversations`
(schedule it daily). Collected contact details are dropped from the flow
state once the booking is made. Message contents are never logged. Prompts
go only to the configured Ollama server.

## 9. Website

### Public read-only API (`apps/website`)

GET-only JSON endpoints for the website. They expose the same public
information as the chatbot's knowledge base and real availability from
`get_available_slots`; they write nothing. Bookings stay in the chat API with
its explicit confirmation.

| Path (`/api/public/clinics/<slug>/…`) | Returns |
| ------------------------------------- | ------- |
| `` (clinic) | name, contact, address, time zone, currency, opening hours (per weekday, earliest start to latest end of the bookable dentists), clinic-wide closures of the next 60 days (no reasons) |
| `services/` | active services: duration, price (`null` = after consultation), ids of dentists who perform them |
| `dentists/` | bookable dentists: name, specialty, bio, service ids, weekly working hours (no contact data or licence numbers) |
| `articles/?language=&category=` | published knowledge articles |
| `availability/?service=&date=&days=1..7&dentist=` | free slots (30-minute steps) with dentist; rate-limited to 60 requests per minute per client |

Content responses may be cached for 5 minutes; availability is `no-store`.
Unknown or inactive clinics give `404`.

### Next.js frontend (`frontend/`)

- App Router with language routes `/sq`, `/en`, `/de`; `proxy.ts` sends `/`
  to the visitor's preferred language. Interface texts are in
  `src/dictionaries`; every clinic fact (name, contact, services, prices,
  dentists, hours, FAQs, about text) comes from the API.
- Pages are server-rendered from the API and regenerated at most every 5
  minutes (ISR). The build works without the backend; pages then show a
  notice until the next regeneration, and keep their last good content if
  the backend goes down later.
- The browser calls `/api/chat/*` and `/api/public/*` on the site's own
  origin; `next.config.ts` forwards them to Django. No CORS, no keys and no
  backend address in the browser.
- **Book page:** real availability per treatment, dentist and day. Choosing
  a time hands the selection to the chat ("I would like to book …"), which
  collects name and phone and books only after the explicit confirmation.
  Nothing is booked from the page itself.
- **Chat widget:** the existing chat API (start, message, `confirm_action`,
  delete); slot options as buttons, Confirm/Not now for pending actions,
  states for loading, errors (busy, rate limit, expired, network) and the
  offline assistant (with the clinic's phone). The conversation is kept in
  `sessionStorage` (this tab only) and can be deleted by the visitor. The
  panel's code loads on first open.
- Accessibility: landmarks and skip link, `aria-current`, labelled controls,
  keyboard support (Escape closes menu and chat), native disclosure widgets,
  visible focus, reduced-motion support; axe-core (WCAG 2.1 AA) reports no
  violations on any page.
- SEO: per-page titles and descriptions, canonical and `hreflang`
  alternates, `sitemap.xml`, `robots.txt`, schema.org `Dentist` data from the
  clinic's real details.
- Photos: none are bundled; labelled placeholders until the clinic adds its
  own (`frontend/public/photos/`). Dentists are shown with monograms.
- Production: route `/api/` to Django at the reverse proxy (see "Deployment
  items" in section 12) so the backend sees each visitor's address for rate
  limiting.

## 10. Time handling

- `USE_TZ = True`; all `DateTimeField`s are stored in UTC (`timestamptz`).
- `Clinic.timezone` (IANA name, validated) defines the local zone in which
  `WorkingHours` times (`time` columns) are interpreted. The booking engine
  converts them per calendar date, so daylight-saving changes keep local
  hours; returned slots carry the clinic's zone.
- In the admin, `ClinicTimezoneMiddleware` activates the clinic's zone for
  staff whose clinics share one zone; superusers and staff of clinics in
  different zones use `DJANGO_TIME_ZONE`. Datetime inputs state their zone,
  and the appointment list shows each start in its clinic's time.
- Weekdays use Python's numbering: Monday = 0 … Sunday = 6.

## 11. Configuration

All configuration comes from environment variables (optionally `backend/.env`,
loaded by python-dotenv; real environment variables take precedence).

| Variable                       | Required | Default               | Notes |
| ------------------------------ | -------- | --------------------- | ----- |
| `DJANGO_SECRET_KEY`            | yes      | —                     | long random string |
| `DJANGO_DEBUG`                 | no       | `false`               | `true` only locally |
| `DJANGO_ALLOWED_HOSTS`         | no       | `localhost,127.0.0.1` | comma-separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS`  | no       | empty                 | e.g. `https://admin.example.com` |
| `DJANGO_TIME_ZONE`             | no       | `UTC`                 | admin display zone |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | yes | — | PostgreSQL connection |
| `DB_PORT`                      | no       | `5432`                | |
| `DB_SSLMODE`                   | no       | `prefer`              | `require` for Supabase |
| `DB_CONN_MAX_AGE`              | no       | `60`                  | seconds; persistent connections |
| `OLLAMA_BASE_URL`              | no       | `http://127.0.0.1:11434` | local Ollama server |
| `OLLAMA_MODEL`                 | no       | `qwen2.5:7b`          | any installed Ollama chat model |
| `OLLAMA_TIMEOUT_SECONDS`       | no       | `60`                  | per model request |
| `CHATBOT_DEFAULT_LANGUAGE`     | no       | `sq`                  | `sq`, `en` or `de` |
| `CHATBOT_CONVERSATION_TTL_MINUTES` | no   | `60`                  | inactivity before a chat expires |
| `CHATBOT_RETENTION_DAYS`       | no       | `30`                  | used by `purge_chat_conversations` |

`python manage.py check_ollama` verifies that Ollama is reachable and the
model is installed (`ollama pull <model>`). Rate limits use Django's cache:
the default in-process cache is fine for one process; several workers need
a shared cache backend for exact limits.

## 12. Supabase

- Connect with the **Session pooler** (IPv4, port 5432) or the direct
  connection. The Transaction pooler (port 6543) is not supported by this
  configuration (it would need server-side cursors disabled).
- Use `DB_SSLMODE=require`.
- `btree_gist` is available on Supabase. The migration enables it if it is not
  already enabled; it can also be enabled beforehand in the dashboard
  (Database → Extensions).
- **Data API exposure:** Supabase can expose tables in the `public` schema
  through its auto-generated REST API. Django manages access itself and does
  not use that API, so before storing any real data either disable the Data
  API for the project or remove `public` from its exposed schemas (or enable
  RLS on every table). Never put the Supabase `anon` or `service_role` keys in
  this backend.
- Migrations against the Supabase database require explicit approval (see
  `PROJECT_RULES.md`). Review with `python manage.py sqlmigrate <app> <n>`,
  back up, then `python manage.py migrate`.

Deployment items still open (depend on the hosting choice):
`SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT` / proxy SSL header, static file
serving, a Content-Security-Policy for the website, and routing `/api/` to
Django directly at the reverse proxy (when API calls pass through the
Next.js server, Django sees the Next.js server as the client address, so the
per-client rate limits apply to all visitors together).

## 13. Testing

- Django's test runner against a local PostgreSQL (`python manage.py test`).
- `backend/tests/` holds:
  - the integrity suite: one test per database constraint, each asserting
    the violated constraint's name; tenant-rule guards; migration drift check;
  - booking tests (`test_booking_*`): availability, breaks, time off, time
    zones and daylight saving, conflicts, cancellation, rescheduling, status
    transitions; each asserts the `BookingErrorCode`;
  - concurrency tests with real parallel transactions (`TransactionTestCase`
    and threads), including one that proves the database blocks a booking
    whose pre-check could not see a concurrent uncommitted one;
  - admin tests: clinic isolation, role permissions, booking via the admin;
  - chatbot tests (`test_chat_*`): language detection and templates in all
    three languages, knowledge retrieval and isolation, the Ollama client
    against a local stand-in server, interpretation validation, booking /
    cancel / reschedule flows, the confirmation rules, the API (auth, limits,
    erasure, concurrent messages). Tests use a fake model; no Ollama needed;
  - website API tests (`test_website_api`): content, exclusions, availability,
    validation, caching headers, rate limiting.
- `frontend/`: unit tests with Node's built-in runner (`npm test`) for
  locale negotiation, formatting in the clinic's time zone, the chat client
  and state, and dictionary completeness; ESLint; TypeScript; production
  build.

## 14. Decisions

| Decision | Reason |
| -------- | ------ |
| Django 5.2 LTS rather than 6.x | Long support window (April 2028); upgrade to the next LTS deliberately. |
| psycopg 3, PostgreSQL only | Exclusion constraints and range types are PostgreSQL features; tests must run on the real engine. |
| Custom `User` model from day one | Django cannot easily swap `AUTH_USER_MODEL` after the first migration. |
| `Dentist` as profile of `StaffMember` | One person record; only clinical staff get a bookable profile. |
| `bigint` primary keys | Django default; public-facing identifiers (booking links) will use separate random tokens. |
| Status choices also enforced by `CHECK` | Django does not enforce `choices` in the database. Adding a choice needs a migration — intended. |
| No REST framework, pgvector or Ollama client yet | Not needed yet; added in the phases that use them. |
| Breaks as gaps between working-hour blocks; days off as `TimeOff` | Reuses the Task 1 models; no separate break model to keep consistent. |
| Admin permissions from `StaffMember.role` per clinic, not Django groups | One source of truth for "who works where as what"; object checks use the role in the object's clinic. |
| Bookings confirmed immediately | Valid bookings need no manual step; `pending` remains for future flows. |
| Slots aligned to the start of each working period, 15-minute step | Predictable times; the step is a parameter. |
| Plain Django JSON views instead of Django REST Framework | Three endpoints with small payloads; no new dependency. |
| Ollama via `urllib`, not an SDK | One endpoint is used; no new dependency; explicit control over proxies and timeouts. |
| The LLM interprets and phrases, the server decides and writes | Keeps bookings correct and safe with small local models; no tool/SQL access for the model. |
| Booking texts from templates, not generated | Times, dentists and references must be exact in every language. |
| Deterministic language detection | Reliable for sq/en/de, testable, no dependency. |
| Booking reference on `Appointment` | Lets anonymous visitors prove ownership of a booking; also useful for staff search. |
| Read-only public API for the website (approved in Task 4) | Pages show real clinic data; no second booking path — booking stays in the chat API with explicit confirmation. |
| Next.js forwards `/api/*` to Django (same origin) | No CORS configuration or backend address in the browser. |
| No UI, i18n, icon or test libraries in the frontend | Tailwind, a small dictionary module, inline SVG icons and Node's test runner suffice. |
| No bundled stock photography | Photos presented as the clinic must be real; placeholders are labelled. |
| Full-text search rather than embeddings | Clinic knowledge is small; avoids pgvector and an embedding model for now. |
| Deadlocks between conflicting inserts are retried (max. 3 attempts) | Known PostgreSQL behaviour of exclusion constraints under exact races; the retry turns it into the correct `SLOT_TAKEN` error. |
