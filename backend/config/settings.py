"""
Django settings for the dental clinic backend.

All environment-specific values (secrets, database credentials, hosts) come
from environment variables. In local development they may be placed in
``backend/.env``; see ``backend/.env.example``. Nothing secret has a default.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Real environment variables always win over values in the .env file.
load_dotenv(BASE_DIR / ".env", override=False)


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Environment variable {name} is not set.")
    return value


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Project apps, roughly in dependency order.
    "apps.core",
    "apps.accounts",
    "apps.clinics",
    "apps.catalog",
    "apps.staff",
    "apps.patients",
    "apps.scheduling",
    "apps.appointments",
    "apps.knowledge",
    "apps.chatbot",
    "apps.website",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.staff.middleware.ClinicTimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database: PostgreSQL only. Exclusion constraints used for appointment
# overlap prevention do not exist on other backends.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            # Supabase requires "require"; local development may use "disable".
            "sslmode": env("DB_SSLMODE", "prefer"),
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# Staff users get permissions from their role in each clinic (apps.staff.access).
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.staff.access.ClinicRoleBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization. Datetimes are stored in UTC; each clinic declares its
# own local time zone for schedules (see Clinic.timezone).
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# Chatbot: a local Ollama server only; no external AI service is used.
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT_SECONDS = int(env("OLLAMA_TIMEOUT_SECONDS", "60"))
CHATBOT_DEFAULT_LANGUAGE = env("CHATBOT_DEFAULT_LANGUAGE", "sq")
if CHATBOT_DEFAULT_LANGUAGE not in ("sq", "en", "de"):
    raise ImproperlyConfigured("CHATBOT_DEFAULT_LANGUAGE must be sq, en or de.")
CHATBOT_CONVERSATION_TTL_MINUTES = int(env("CHATBOT_CONVERSATION_TTL_MINUTES", "60"))
CHATBOT_RETENTION_DAYS = int(env("CHATBOT_RETENTION_DAYS", "30"))


# Security defaults that only make sense outside local development.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
