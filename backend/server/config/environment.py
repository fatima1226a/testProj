"""Load local LAST_LIGHT settings without overriding the process environment.

Supports KEY=value and quoted values, with blank lines and full-line comments.
Values are literal: shell expansion and inline comments are not supported.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def load_local_environment(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not name.startswith("LAST_LIGHT_") or not name.isidentifier():
            raise ImproperlyConfigured(f"Invalid setting in .env at line {number}")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ImproperlyConfigured(f"Unclosed quote in .env at line {number}")
            value = value[1:-1]
        os.environ.setdefault(name, value)
