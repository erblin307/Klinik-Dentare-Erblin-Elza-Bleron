# Backend (Django)

See `../ARCHITECTURE.md` for the design and `../PROJECT_RULES.md` for the rules.

## Requirements

- Python 3.10+ (developed and tested with 3.13)
- PostgreSQL 14+ for local development and tests (Supabase for deployment)

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then edit .env (never commit it)
```

Create a local database. The role needs `CREATEDB` so the test runner can
create its own `test_*` database:

```sql
CREATE ROLE dental_dev LOGIN PASSWORD 'choose-a-local-password' CREATEDB;
CREATE DATABASE dental_dev OWNER dental_dev;
```

Point `backend/.env` at it (`DB_NAME=dental_dev`, `DB_USER=dental_dev`,
`DB_HOST=127.0.0.1`, `DB_SSLMODE=disable`, `DJANGO_DEBUG=true`), then:

```bash
python manage.py migrate             # local database only
python manage.py createsuperuser
python manage.py runserver           # admin at http://127.0.0.1:8000/admin/
```

## Chatbot (Ollama)

Install [Ollama](https://ollama.com) locally, then:

```bash
ollama pull qwen2.5:7b               # or another model; set OLLAMA_MODEL
python manage.py check_ollama        # verifies server and model
python manage.py purge_chat_conversations   # schedule daily (retention)
```

The chat API is under `/api/chat/` (see "Chatbot" in `../ARCHITECTURE.md`).
Tests do not need Ollama.

## Tests

```bash
python manage.py test
```

Run tests only against a local PostgreSQL, never with production credentials.

## Supabase

Use the Session pooler connection values with `DB_SSLMODE=require`, and read
"Supabase" in `../ARCHITECTURE.md` before connecting. Applying migrations to
the Supabase database requires explicit approval.
