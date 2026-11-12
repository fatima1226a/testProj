"""API and model tests for the selected backend; unavailable backend suite skips."""
import os
os.environ.setdefault("LAST_LIGHT_SECRET_KEY", "test-only-key-not-for-server-use-0000000000")
from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["testserver", "localhost"]
