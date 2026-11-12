"""Core ORM tests only: deliberately does not test DRF/JWT/CORS integration."""
import os
os.environ.setdefault("LAST_LIGHT_SECRET_KEY", "test-only-key-not-for-server-use-0000000000")
from .settings import *  # noqa: F403

INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ("rest_framework", "corsheaders", "django.contrib.admin")]
MIDDLEWARE = []
ROOT_URLCONF = "server.config.model_test_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
