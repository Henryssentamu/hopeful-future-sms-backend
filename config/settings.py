"""
Django settings for the Hopeful Future Portal school-management-system backend.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

from .environment import env_bool, env_csv, env_int, get_environment, validate_production_configuration

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ENVIRONMENT = get_environment()
IS_PRODUCTION = ENVIRONMENT == "production"

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-development-only-key-never-use-this-value-in-production",
).strip()
DEBUG = env_bool("DJANGO_DEBUG", ENVIRONMENT == "development")
ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", "" if IS_PRODUCTION else "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local apps, in FK dependency order (see plan doc) — order here mostly
    # affects admin ordering, not migration order, but kept consistent.
    "apps.accounts",
    "apps.core",
    "apps.staff",
    "apps.academics",
    "apps.students",
    "apps.results",
    "apps.finance",
    "apps.timetable",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — MySQL always, no sqlite fallback (even for local dev without
# Docker, point DB_HOST at Docker's published mysql port once it's running).
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "" if IS_PRODUCTION else "hfss"),
        "USER": os.getenv("DB_USER", "" if IS_PRODUCTION else "hfss"),
        "PASSWORD": os.getenv("DB_PASSWORD", "" if IS_PRODUCTION else "hfss"),
        "HOST": os.getenv("DB_HOST", "" if IS_PRODUCTION else "mysql"),
        "PORT": os.getenv("DB_PORT", "" if IS_PRODUCTION else "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# The school is in Kayunga, Uganda.
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Deny-by-default: every view requires authentication unless it
    # explicitly opts into AllowAny (e.g. the login endpoint).
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "login_ip": os.getenv("AUTH_LOGIN_IP_THROTTLE_RATE", "30/minute"),
        "login_username": os.getenv("AUTH_LOGIN_USERNAME_THROTTLE_RATE", "5/minute"),
        "token_refresh_ip": os.getenv("AUTH_REFRESH_IP_THROTTLE_RATE", "60/minute"),
    },
    # Trust only REMOTE_ADDR unless deployment explicitly declares how many
    # reverse proxies sanitize X-Forwarded-For before traffic reaches Django.
    "NUM_PROXIES": env_int("DRF_NUM_PROXIES", 0),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=45),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Hopeful Future Portal API",
    "DESCRIPTION": "Backend API for the Hopeful Future Secondary School management system.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS — the frontend's Vite dev server runs on port 8080 (see
# frontends/hopeful-future-portal/vite.config.ts), not the Vite default.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_csv("CORS_ALLOWED_ORIGINS", "" if IS_PRODUCTION else "http://localhost:8080")
CSRF_TRUSTED_ORIGINS = env_csv(
    "CSRF_TRUSTED_ORIGINS",
    "" if IS_PRODUCTION else "http://localhost:8080,http://127.0.0.1:8080",
)

# Production transport policy. HSTS subdomain coverage and preload remain
# explicit rollout decisions because enabling them before every subdomain is
# HTTPS-ready can make those subdomains inaccessible in supporting browsers.
SECURE_SSL_REDIRECT = IS_PRODUCTION
# The edge proxy restricts operational probes; these expose no application data.
SECURE_REDIRECT_EXEMPT = [r"^health/live/$", r"^health/ready/$"]
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

TRUST_PROXY_SSL_HEADER = env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", False)
if TRUST_PROXY_SSL_HEADER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Redis — cache and Celery broker live on DIFFERENT logical DBs so a cache
# flush never touches Celery's queue/result state.
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_CACHE_DB = os.getenv("REDIS_CACHE_DB", "1")
REDIS_CELERY_DB = os.getenv("REDIS_CELERY_DB", "0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CACHE_DB}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
        },
    }
}

CACHE_BACKEND = os.getenv("DJANGO_CACHE_BACKEND", "redis").strip().lower()
if CACHE_BACKEND == "database":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "sms_cache",
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }
elif CACHE_BACKEND != "redis":
    raise ImproperlyConfigured("DJANGO_CACHE_BACKEND must be redis or database.")

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Result confirmation remains synchronous and transactional in both runtimes.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
if CACHE_BACKEND == "database" and not CELERY_TASK_ALWAYS_EAGER:
    raise ImproperlyConfigured("The database-cache shared-hosting profile requires CELERY_TASK_ALWAYS_EAGER=True.")

# ---------------------------------------------------------------------------
# Seed data (see apps/core/management/commands/seed_demo_data.py)
# ---------------------------------------------------------------------------
SEED_DEMO_PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "" if IS_PRODUCTION else "Demo@2025")

if IS_PRODUCTION:
    validate_production_configuration(
        environment_variables=os.environ,
        debug=DEBUG,
        secret_key=SECRET_KEY,
        allowed_hosts=ALLOWED_HOSTS,
        cors_allowed_origins=CORS_ALLOWED_ORIGINS,
        csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
        database_settings=DATABASES["default"],
        secure_hsts_seconds=SECURE_HSTS_SECONDS,
        throttle_rates=REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
    )
