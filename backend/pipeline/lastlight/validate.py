"""Validate schemas plus cross-document invariants without network access."""

from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
from importlib import import_module
from pathlib import Path

from .schema_validation import validate


ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = ("sites", "provenance", "validation")


def parse_json(data, source="JSON"):
    def reject(value):
        raise ValueError(f"{source}: invalid JSON number {value}")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{source}: duplicate key {key}")
            result[key] = value
        return result

    def decimal(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{source}: non-finite JSON number {value}")
        return parsed

    return json.loads(data, parse_constant=reject, parse_float=decimal,
                      object_pairs_hook=pairs)


def read_json(path):
    return parse_json(path.read_bytes(), str(path))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_dataset(directory, *, document_bytes=None):
    directory = Path(directory)
    documents = {}
    for name in DOCUMENTS:
        schema = read_json(ROOT / "schemas" / f"{name}.schema.json")
        document = (read_json(directory / f"{name}.json") if document_bytes is None
                    else parse_json(document_bytes[name], f"{name}.json"))
        validate(document, schema)
        try:
            jsonschema = import_module("jsonschema")
        except ImportError:
            pass
        else:
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(
                schema, format_checker=jsonschema.FormatChecker()
            ).validate(document)
        documents[name] = document

    sites, provenance, validation = (documents[name] for name in DOCUMENTS)
    require(len({doc["datasetId"] for doc in documents.values()}) == 1, "datasetId mismatch")
    sites_raw = (directory / "sites.json").read_bytes() if document_bytes is None else document_bytes["sites"]
    require(sha256(sites_raw).hexdigest() == provenance["sitesSha256"],
            "sites.json SHA-256 mismatch")
    require(len({s["id"] for s in sites["sites"]}) == len(sites["sites"]), "duplicate site id")
    start = datetime.fromisoformat(sites["window"]["start"].replace("Z", "+00:00"))
    if sites["version"] == 1:
        require(sites["window"].get("stepH") == 1, "v1 requires hourly stepH=1")
        step_minutes = 60
    else:
        require("stepMinutes" in sites["window"], "v2 requires stepMinutes")
        step_minutes = sites["window"]["stepMinutes"]
        require("secondSignature" in provenance, "v2 requires secondSignature review metadata")
    signature = provenance.get("secondSignature")
    if signature is not None:
        require(signature["sitesSha256"] == provenance["sitesSha256"], "second signature dataset hash mismatch")
        if signature["status"] == "pending":
            require(signature["signedBy"] is None and signature["signedAt"] is None,
                    "pending second signature cannot claim a signer or date")
        else:
            require(isinstance(signature["signedBy"], str) and bool(signature["signedBy"].strip())
                    and signature["signedAt"] is not None, "signed second signature needs reviewer and date")
    for site in sites["sites"]:
        require(site.get("stepMinutes", 60) == step_minutes, "site/window step mismatch")
        require(len(site["hours"]) == sites["window"]["count"], "hour count mismatch")
        for i, hour in enumerate(site["hours"]):
            actual = datetime.fromisoformat(hour["t"].replace("Z", "+00:00"))
            require(actual == start + timedelta(minutes=i * step_minutes), "nonconsecutive sample timestamps")
        for horizon in (list(site.get("horizonByMast", {}).values())
                        + site.get("horizonClones", [])):
            require(len(horizon) == len(site["horizon"]), "horizon length mismatch")
        for horizon in site.get("horizonByMast", {}).values():
            require(all(high <= base for high, base in zip(horizon, site["horizon"])),
                    "higher mast raises horizon")
        if provenance["capabilities"]["uncertainty"]:
            require(bool(site.get("horizonClones")), "uncertainty requires clones")

    require(len({s["id"] for s in provenance["sources"]}) == len(provenance["sources"]),
            "duplicate source id")
    if provenance["mode"] == "final":
        for source in provenance["sources"]:
            require(not source["synthetic"] and bool(source["url"] or source["query"])
                    and all(source[k] is not None for k in ("version", "accessedAt", "sha256")),
                    "final source is synthetic or incomplete")
    else:
        require(provenance["seed"] is not None, "demo requires seed")
    require(len({c["id"] for c in validation["checks"]}) == len(validation["checks"]),
            "duplicate check id")
    for check in validation["checks"]:
        if provenance["mode"] == "demo" and check["level"] is not None:
            require(check["status"] == "pending", "demo scientific checks must remain pending")
        if check["status"] != "pending":
            require(all(check[k] is not None for k in ("ranAt", "measurement", "tolerance", "report")),
                    "completed check lacks evidence")
            report = (directory / check["report"]["path"]).resolve()
            require(report.is_relative_to(directory.resolve()), "report path escapes dataset")
            require(report.is_file(), "missing check report")
            require(sha256(report.read_bytes()).hexdigest() == check["report"]["sha256"],
                    "check report SHA-256 mismatch")
    return documents
