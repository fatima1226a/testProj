"""Local tests without optional JWT/CORS packages; never use for serving traffic."""
from .test_settings import *  # noqa: F403

LOCAL_TESTS_WITHOUT_JWT_CORS = True
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "corsheaders"]
MIDDLEWARE = [item for item in MIDDLEWARE if not item.startswith("corsheaders.")]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_AUTHENTICATION_CLASSES": []}
ROOT_URLCONF = "server.config.local_test_urls"
