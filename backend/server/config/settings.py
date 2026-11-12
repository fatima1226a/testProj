"""Django API settings. Read secrets from the environment or server/.env."""

from datetime import timedelta
import os
from importlib.util import find_spec
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured  # type: ignore[reportMissingModuleSource]
from .environment import load_local_environment


load_local_environment()
BASE_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY = os.environ.get("LAST_LIGHT_SECRET_KEY", "")
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured("LAST_LIGHT_SECRET_KEY must contain at least 32 characters")
DEBUG = os.environ.get("LAST_LIGHT_DEBUG", "0") == "1"
API_BACKEND = os.environ.get("LAST_LIGHT_API_BACKEND", "django")
if API_BACKEND not in ("django", "drf"):
    raise ImproperlyConfigured("LAST_LIGHT_API_BACKEND must be django or drf")
if API_BACKEND == "drf" and any(find_spec(name) is None for name in
                                ("rest_framework", "rest_framework_simplejwt", "corsheaders")):
    raise ImproperlyConfigured("DRF mode requires server/requirements.txt; use LAST_LIGHT_API_BACKEND=django offline")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("LAST_LIGHT_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "server.accounts.apps.AccountsConfig", "server.datasets.apps.DatasetsConfig", "server.runs.apps.RunsConfig",
]
if API_BACKEND == "drf":
    INSTALLED_APPS += ["rest_framework", "corsheaders"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware" if API_BACKEND == "drf" else "server.native_middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

STATIC_URL = "/static/"
ROOT_URLCONF = "server.config.urls"
WSGI_APPLICATION = "server.config.wsgi.application"
ASGI_APPLICATION = "server.config.asgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": os.environ.get("LAST_LIGHT_DB_PATH", str(BASE_DIR / "db.sqlite3")),
                         # IMMEDIATE takes the write lock up front, so parallel writes wait instead of deadlocking.
                         "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"}}}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("LAST_LIGHT_FRONTEND_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
if "*" in CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("LAST_LIGHT_FRONTEND_ORIGINS must list exact origins; '*' is not allowed")
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = API_BACKEND == "django"
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CSRF_FAILURE_VIEW = "server.native_api.csrf_failure"
CORS_URLS_REGEX = r"^/api/.*$"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["server.drf_parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 50,
}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
              "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "AUTH_HEADER_TYPES": ("Bearer",)}
RUN_HISTORY_LIMIT = 50
EMAIL_BACKEND = os.environ.get("LAST_LIGHT_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
