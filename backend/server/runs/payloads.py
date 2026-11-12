"""Snapshot validation without recomputing the browser simulation."""
import json
import re
from django.core.exceptions import ValidationError

# Compared after dropping case and separators, so accessToken, access_token and Access-Token all match.
TOKEN_KEYS = {"jwt", "token", "access", "refresh", "accesstoken", "refreshtoken", "idtoken", "authorization",
              "bearer", "sessionid", "csrftoken", "password", "apikey"}
JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
MAX_JSON_DEPTH = 64


def check_json_tree(data):
    """Reject nesting that recursive encoders cannot handle and strings SQLite cannot store."""
    stack = [(data, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValidationError(f"JSON nesting must not exceed {MAX_JSON_DEPTH} levels")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in (*value.keys(), *value.values()))
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise ValidationError("Strings must be valid Unicode") from None


def validate_snapshots(plan, result):
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if re.sub(r"[^a-z]", "", str(key).lower()) in TOKEN_KEYS:
                    raise ValidationError("Authentication data must not be stored in snapshots")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str) and JWT.search(value):
            raise ValidationError("JWT must not be stored in snapshots")

    for value in (plan, result):
        if not isinstance(value, dict):
            raise ValidationError("Plan and result must be JSON objects")
        check_json_tree(value)
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValidationError("Snapshots must contain finite JSON values") from error
        visit(value)
