# Project Rules

Binding rules for everyone (people and AI assistants) working on this
repository: a reusable Dental Clinic SaaS demo built with Django, Supabase
PostgreSQL, a Next.js frontend (later) and a local Ollama assistant (later).

When a rule and a request conflict, stop and ask before proceeding.

## 1. How we work

1. **Inspect before changing.** Read the relevant code, migrations and docs
   first. Understand why something exists before modifying it.
2. **No vibe coding.** Every change has a clear purpose, is the smallest
   change that achieves it, is understood line by line by its author, and is
   covered by tests. No speculative features, no copy-pasted code nobody can
   explain.
3. **Work in phases.** Each task has an explicit scope. Finish it, report on
   it, and stop. Never start the next phase automatically.
4. **Do not modify unrelated files.** Refactors and drive-by fixes go in their
   own, separately agreed change.
5. **Preserve existing working functionality.** If a change must break
   behaviour, say so explicitly and get approval first.

## 2. Dependencies

Keep dependencies few, mainstream and pinned to a compatible range in
`backend/requirements.txt`. Adding one requires a reason recorded here.

| Package         | Why it is needed                                            |
| --------------- | ----------------------------------------------------------- |
| Django 5.2 LTS  | Web framework, ORM, migrations, admin. LTS until April 2028. |
| psycopg 3       | PostgreSQL driver (Supabase).                               |
| python-dotenv   | Loads `backend/.env` during local development.              |

Not used on purpose: test-data factory libraries (plain functions suffice),
alternative test runners (Django's runner suffices), any paid AI SDK.

## 3. Architecture

- Follow `ARCHITECTURE.md`. Changes to the structure described there update
  that document in the same change.
- One Django app per bounded context under `backend/apps/`. Apps depend only
  "downwards" (see the dependency graph in `ARCHITECTURE.md`); no circular
  imports.
- Business invariants that the database can express (uniqueness, ranges,
  overlaps, tenant consistency) are enforced **in the database** with named
  constraints, and mirrored by model validation for friendly error messages.
  Never rely on the frontend or the admin alone for integrity.
- Workflows (booking, availability search, notifications) will live in
  service modules, not in views, serializers or signals.

## 4. Multi-clinic isolation

- Every table holding clinic data inherits `ClinicScopedModel` and therefore
  has a non-null `clinic_id`.
- Every foreign key between two clinic-scoped models is declared with
  `SameClinicConstraint`, and its target declares
  `UniqueConstraint(fields=["clinic", "id"])`. Tests fail if this is missed.
- A record's clinic never changes after creation.
- Future API code must always derive the clinic from the authenticated
  context, never from client input, and filter every query by it.

## 5. Security and privacy

- **Never commit credentials.** Secrets live only in environment variables
  or `backend/.env` (git-ignored). `backend/.env.example` holds placeholders
  only. Settings have no defaults for secrets and fail fast when missing.
- Never paste keys, passwords, connection strings or tokens into code, docs,
  tests, commit messages, issues or chat transcripts.
- **Never expose patient data.** No real patient data in the repository,
  fixtures, tests, screenshots, logs, issues or AI prompts. Tests use clearly
  fictitious data.
- Do not log personal data (names, phone numbers, dates of birth, notes).
- Collect only the patient data the clinic needs (data minimisation).
- AI knowledge entries contain public clinic information only — never
  patient data.
- The Supabase Data API must not expose the Django tables (see
  `ARCHITECTURE.md`, "Supabase"). The backend never uses Supabase API keys.
- `DEBUG` is off unless explicitly enabled for local development.

## 6. AI

- Only local models served by **Ollama**. No paid or external AI APIs.
- The assistant is not built yet; do not add AI code until that phase starts.
- Patient data is never sent to any external service.

## 7. Database and migrations

- PostgreSQL only (exclusion constraints are PostgreSQL features).
- Migrations are generated with `makemigrations`, reviewed, and committed.
  Any hand edit is marked with a comment explaining why.
- `makemigrations --check` must report no changes (enforced by a test).
- **Never apply migrations to a production database without explicit
  approval.** Before approval: review `sqlmigrate` output and take a backup.
- Develop and run tests against a **local** PostgreSQL. The test runner
  creates and drops a `test_*` database on the configured server, so never
  run tests with production credentials.

## 8. Testing

- `python manage.py test` must pass before every commit.
- Every database constraint has a test that triggers it and asserts the
  constraint's **name**, so a test cannot pass because of an unrelated error.
- New models get integrity tests in `backend/tests/`.

## 9. Code style

- Follow Django conventions and PEP 8; descriptive names; small modules.
- Comments explain *why*, not *what*.
- Database constraints and indexes have explicit names prefixed with the app
  label (e.g. `catalog_service_duration_range`), so errors are traceable.
