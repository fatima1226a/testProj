"""Settings and .env loading; settings are evaluated in a fresh interpreter per case."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from server.config.environment import load_local_environment

ROOT = Path(__file__).resolve().parents[2]
KEY = "test-only-key-not-for-server-use-0000000000"
PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from server.config import settings as s
print(json.dumps({"DEBUG": s.DEBUG, "SESSION_COOKIE_SECURE": s.SESSION_COOKIE_SECURE,
                  "CSRF_COOKIE_SECURE": s.CSRF_COOKIE_SECURE, "ALLOWED_HOSTS": s.ALLOWED_HOSTS,
                  "CORS_ALLOWED_ORIGINS": s.CORS_ALLOWED_ORIGINS, "CSRF_TRUSTED_ORIGINS": s.CSRF_TRUSTED_ORIGINS}))
"""


def evaluate_settings(*, probe=PROBE, **variables):
    """Import settings with only the given LAST_LIGHT_* variables; server/.env cannot override them."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("LAST_LIGHT_")}
    environment.update({"LAST_LIGHT_SECRET_KEY": KEY, "PYTHONIOENCODING": "utf-8", **variables})
    return subprocess.run([sys.executable, "-c", probe, str(ROOT)], env=environment, cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")


class SettingsTests(SimpleTestCase):
    def settings_for(self, **variables):
        result = evaluate_settings(**variables)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def assert_rejected(self, message, **variables):
        result = evaluate_settings(**variables)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn(message, result.stderr)

    def test_short_secret_and_unknown_backend_are_rejected(self):
        self.assert_rejected("at least 32 characters", LAST_LIGHT_SECRET_KEY="short")
        self.assert_rejected("must be django or drf", LAST_LIGHT_API_BACKEND="flask")

    def test_drf_mode_without_dependencies_fails_instead_of_falling_back(self):
        # Simulate a missing dependency in the child interpreter, regardless
        # of which packages are installed in the developer's environment.
        probe = ("from unittest.mock import patch\n"
                 "with patch('importlib.util.find_spec', return_value=None):\n"
                 f"    exec({PROBE!r})\n")
        self.assert_rejected("DRF mode requires", probe=probe, LAST_LIGHT_API_BACKEND="drf")

    def test_production_defaults_use_secure_cookies_and_explicit_hosts(self):
        values = self.settings_for(LAST_LIGHT_ALLOWED_HOSTS="api.example.org, ,www.example.org")
        self.assertFalse(values["DEBUG"])
        self.assertTrue(values["SESSION_COOKIE_SECURE"])
        self.assertTrue(values["CSRF_COOKIE_SECURE"])
        self.assertEqual(values["ALLOWED_HOSTS"], ["api.example.org", "www.example.org"])
        debug = self.settings_for(LAST_LIGHT_DEBUG="1")
        self.assertFalse(debug["SESSION_COOKIE_SECURE"])
        self.assertEqual(debug["ALLOWED_HOSTS"], ["localhost", "127.0.0.1"])

    def test_frontend_origins_are_parsed_trusted_for_csrf_and_wildcard_rejected(self):
        values = self.settings_for(LAST_LIGHT_FRONTEND_ORIGINS=" https://a.example.org,,https://b.example.org ")
        self.assertEqual(values["CORS_ALLOWED_ORIGINS"], ["https://a.example.org", "https://b.example.org"])
        self.assertEqual(values["CSRF_TRUSTED_ORIGINS"], values["CORS_ALLOWED_ORIGINS"])
        self.assert_rejected("'*' is not allowed", LAST_LIGHT_FRONTEND_ORIGINS="https://a.example.org,*")


class LocalEnvironmentTests(SimpleTestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(text, encoding="utf-8")
            load_local_environment(path)

    def test_quotes_comments_and_literal_values(self):
        names = ("LAST_LIGHT_T_PLAIN", "LAST_LIGHT_T_DOUBLE", "LAST_LIGHT_T_SINGLE", "LAST_LIGHT_T_LITERAL")
        with patch.dict(os.environ):
            for name in names:
                os.environ.pop(name, None)
            self.load("# comment\n\nLAST_LIGHT_T_PLAIN = value=with=equals\nLAST_LIGHT_T_DOUBLE=\"spaced value\"\n"
                      "LAST_LIGHT_T_SINGLE='кириллица'\nLAST_LIGHT_T_LITERAL=$HOME # not a comment\n")
            self.assertEqual([os.environ[name] for name in names],
                             ["value=with=equals", "spaced value", "кириллица", "$HOME # not a comment"])

    def test_process_environment_has_priority(self):
        with patch.dict(os.environ, {"LAST_LIGHT_T_PRIORITY": "from-process"}):
            self.load("LAST_LIGHT_T_PRIORITY=from-file\n")
            self.assertEqual(os.environ["LAST_LIGHT_T_PRIORITY"], "from-process")

    def test_invalid_lines_name_the_line_number(self):
        for text, message in (("LAST_LIGHT_OK=1\nnot a setting\n", "line 2"), ("OTHER_PREFIX=1\n", "line 1"),
                              ("LAST_LIGHT_T_QUOTE=\"open\n", "Unclosed quote in .env at line 1"),
                              ("LAST_LIGHT_T_QUOTE='\n", "Unclosed quote")):
            with self.subTest(text=text), patch.dict(os.environ):
                with self.assertRaisesRegex(ImproperlyConfigured, message):
                    self.load(text)

    def test_missing_file_is_ignored(self):
        load_local_environment(Path(tempfile.gettempdir()) / "missing-last-light" / ".env")
