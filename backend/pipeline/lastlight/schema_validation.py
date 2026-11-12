"""Offline validator for the JSON Schema keywords used by this project's schemas.

This is deliberately not a general Draft 2020-12 implementation. Unsupported
keywords fail closed. When installed, jsonschema also validates the same files.
"""

from datetime import datetime
import math
from urllib.parse import urlsplit


KEYWORDS = {
    "$schema", "title", "$defs", "$ref", "type", "additionalProperties",
    "required", "properties", "const", "enum", "minimum", "maximum",
    "exclusiveMaximum", "minLength", "minItems", "minProperties", "items",
    "format", "pattern", "oneOf",
}


def validate(value, schema, root=None, path="$"):
    import re

    root = schema if root is None else root
    unknown = schema.keys() - KEYWORDS
    if unknown:
        raise ValueError(f"Unsupported schema keywords: {sorted(unknown)}")

    def fail(message):
        raise ValueError(f"{path}: {message}")

    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            fail("only local schema references are supported")
        target = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        validate(value, target, root, path)
    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            try:
                validate(value, option, root, path)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            fail("expected exactly one matching schema")
    numeric = type(value) in (int, float)
    if numeric and not math.isfinite(value):
        fail("non-finite number")
    if "type" in schema:
        types = schema["type"]
        types = [types] if isinstance(types, str) else types
        checks = {
            "null": value is None, "boolean": type(value) is bool,
            "number": numeric,
            "integer": numeric and value == int(value),
            "string": isinstance(value, str), "object": isinstance(value, dict),
            "array": isinstance(value, list),
        }
        if not any(checks[t] for t in types):
            fail(f"expected {types}")
    # JSON booleans must not compare equal to JSON numbers.
    def equal(a, b):
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        return a == b

    if "const" in schema and not equal(value, schema["const"]):
        fail("constant mismatch")
    if "enum" in schema and not any(equal(value, item) for item in schema["enum"]):
        fail("value outside enum")
    if numeric:
        for key, test in (
            ("minimum", lambda bound: value >= bound),
            ("maximum", lambda bound: value <= bound),
            ("exclusiveMaximum", lambda bound: value < bound),
        ):
            if key in schema and not test(schema[key]):
                fail(key)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            fail("string too short")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            fail("pattern mismatch")
        if schema.get("format") == "date-time":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value):
                fail("expected ISO UTC timestamp ending in Z")
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                fail("invalid date-time")
        elif schema.get("format") == "uri":
            if not urlsplit(value).scheme or re.search(r"\s", value):
                fail("invalid URI")
        elif "format" in schema:
            fail("unsupported string format")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            fail("array too short")
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], root, f"{path}[{index}]")
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            fail("object too small")
        if set(schema.get("required", [])) - value.keys():
            fail("missing required properties")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            fail("unexpected properties")
        for key in value.keys() & properties.keys():
            validate(value[key], properties[key], root, f"{path}.{key}")
