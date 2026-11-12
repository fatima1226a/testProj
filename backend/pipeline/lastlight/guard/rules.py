from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path
import re

from ..validate import DOCUMENTS, parse_json, validate_dataset


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return sha256(raw).hexdigest()


def timestamp(value):
    require(isinstance(value, str) and value.endswith("Z"), "expected UTC timestamp ending in Z")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "timestamp needs timezone")
    return result


@dataclass
class GuardReport:
    dataset_id: str | None = None
    rules: list[dict] = field(default_factory=list)
    document_bytes: dict[str, bytes] = field(default_factory=dict, repr=False)
    documents: dict = field(default_factory=dict, repr=False)

    @property
    def ok(self):
        return not any(rule["status"] == "failed" for rule in self.rules)

    def as_dict(self):
        return {"scope": "backend", "datasetId": self.dataset_id, "ok": self.ok, "rules": self.rules}

    def require_ok(self):
        if not self.ok:
            raise GuardError(self)
        return self


class GuardError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("; ".join(f"{r['rule']}: {r['message']}" for r in report.rules if r["status"] == "failed"))


def check_existing_release(report, existing):
    """D2 predicate, also called after get_or_create to handle a competing import."""
    require(existing["datasetId"] == report.dataset_id, "existing release datasetId mismatch")
    require(existing["sitesSha256"] == digest(report.document_bytes["sites"]),
            "cannot overwrite datasetId with a different sites.json hash")
    if "mode" in existing:
        require(existing["mode"] == report.documents["provenance"]["mode"],
                "stored DB mode differs from release provenance")
    if "documents" in existing:
        require(all(bytes(existing["documents"][name]) == raw for name, raw in report.document_bytes.items()),
                "existing release documents are immutable")


def inspect_release(directory, *, document_bytes=None, current_commit=None, manifest_path=None,
                    existing_release=None, history_records=None, api_documents=None):
    """Inspect without writes; pending scientific validation is permitted.

    existing_release: {datasetId, sitesSha256, documents?: {name: bytes}}.
    history_records: API records belonging to this release, including dataset_notice.
    api_documents: raw HTTP response bodies for sites/provenance/validation.
    Evidence file paths are confined to the release directory.
    """
    directory = Path(directory).resolve()
    report = GuardReport()

    def record(rule, status, message):
        report.rules.append({"rule": rule, "status": status, "message": message})

    def run(rule, action):
        try:
            action()
        except Exception as error:
            record(rule, "failed", str(error))
        else:
            record(rule, "passed", "Checked")

    try:
        report.document_bytes = {name: bytes(document_bytes[name]) if document_bytes is not None
                                 else (directory / f"{name}.json").read_bytes() for name in DOCUMENTS}
        report.documents = {name: parse_json(raw, f"{name}.json") for name, raw in report.document_bytes.items()}
        require(all(isinstance(value, dict) for value in report.documents.values()), "documents must be JSON objects")
    except Exception as error:
        record("D3", "failed", f"Cannot read release: {error}")
        return report
    sites, provenance, validation = (report.documents[name] for name in DOCUMENTS)
    report.dataset_id = provenance.get("datasetId")
    mode = provenance.get("mode")
    sources = provenance.get("sources", [])
    checks = validation.get("checks", [])
    evidence_cache = {}

    def evidence(path):
        require(isinstance(path, str) and bool(path), "evidence path is missing")
        target = (directory / path).resolve()
        require(target.is_relative_to(directory), "evidence path escapes release directory")
        if target not in evidence_cache:
            evidence_cache[target] = target.read_bytes()
        return evidence_cache[target]

    def checked_report(check):
        ref = check["report"]
        require(isinstance(ref, dict), f"{check['id']}: missing report reference")
        raw = evidence(ref["path"])
        require(digest(raw) == ref["sha256"], f"{check['id']}: report SHA-256 mismatch")
        require(bool(raw.strip()), f"{check['id']}: empty report")
        return raw

    def a1():
        require(isinstance(sources, list) and bool(sources), "final needs sources")
        for source in sources:
            require(source.get("synthetic") is False, "final contains synthetic or unclassified source")
            require(bool(source.get("url") or source.get("query")), "source URL/query missing")
            require(bool(source.get("version")), "source version missing")
            timestamp(source.get("accessedAt"))
            require(bool(re.fullmatch(r"[a-f0-9]{64}", source.get("sha256") or "")), "source SHA-256 missing")

    if mode == "final":
        run("A1", a1)
    else:
        record("A1", "not_applicable", "Final-source completeness applies to mode=final")

    def a2():
        fetched = [s for s in sources if s.get("synthetic") is not True]
        manifest = parse_json(evidence("fetch-manifest.json"), "fetch-manifest.json")
        entries = manifest["sources"]
        require(isinstance(entries, list), "fetch-manifest.sources must be an array")
        actual = {s["id"]: s["sha256"] for s in entries}
        require(len(actual) == len(entries), "duplicate source in fetch manifest")
        expected = {s["id"]: s["sha256"] for s in fetched}
        require(len(expected) == len(fetched), "duplicate source in provenance")
        require(actual == expected, "fetch-manifest hashes differ from provenance")
        require(all(isinstance(h, str) and re.fullmatch(r"[a-f0-9]{64}", h) for h in actual.values()),
                "fetch-manifest contains missing/invalid hashes")

    if isinstance(sources, list) and sources and all(isinstance(s, dict) and s.get("synthetic") is True for s in sources):
        record("A2", "not_applicable", "Synthetic demo has no fetched source hashes")
    else:
        run("A2", a2)
    record("A3", "not_applicable", "Frontend rule; predicate is absent from backend specification 0.4")

    def a4():
        require(isinstance(history_records, list), "history_records must be a JSON array")
        for item in history_records:
            require(item.get("dataset_id") == report.dataset_id, "history dataset_id mismatch")
            require(item.get("dataset_mode") == mode, "history mode differs from authoritative dataset")
            require(item.get("dataset_notice") == ("DEMO DATA" if mode == "demo" else None),
                    "demo history must expose DEMO DATA notice independently of editable label")

    if history_records or (history_records is not None and not isinstance(history_records, list)):
        run("A4", a4)
    else:
        record("A4", "pending", "No history response supplied; UI rendering is outside backend scope")

    def b1():
        require(isinstance(checks, list), "checks must be an array")
        for check in checks:
            if check["status"] not in ("passed", "failed"):
                continue
            timestamp(check["ranAt"])
            require(check["measurement"] is not None and check["tolerance"] is not None,
                    f"{check['id']}: measurement or tolerance missing")
            raw = checked_report(check)
            # Bind machine-readable evidence when it declares the dataset hash.
            if check["report"]["path"].endswith(".json"):
                data = parse_json(raw, check["report"]["path"])
                if "sitesSha256" in data:
                    require(data["sitesSha256"] == digest(report.document_bytes["sites"]),
                            f"{check['id']}: evidence belongs to different sites.json")

    run("B1", b1)

    def b2():
        expected_commit = current_commit or os.environ.get("GITHUB_SHA")
        require(isinstance(expected_commit, str) and bool(re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", expected_commit)),
                "independent --commit/GITHUB_SHA required for passed level-1/parity")
        raw = evidence("ci-report.json")
        ci = parse_json(raw, "ci-report.json")
        require(ci["commit"] == expected_commit, "ci-report belongs to a different commit")
        require(ci.get("sitesSha256") == digest(report.document_bytes["sites"]),
                "ci-report belongs to different sites.json")
        require(isinstance(ci["versions"], dict) and bool(ci["versions"])
                and all(isinstance(v, str) and v for v in ci["versions"].values()), "ci-report versions missing")
        manifest = Path(manifest_path) if manifest_path is not None else directory / "manifest.json"
        require(ci["manifestSha256"] == digest(manifest.read_bytes()), "fixture manifest SHA-256 mismatch")
        for check in checks:
            if check["status"] == "passed" and (check["level"] == 1 or check["id"] == "parity"):
                require(ci["checks"][check["id"]]["status"] == "passed",
                        f"ci-report does not confirm {check['id']}")
                require(digest(raw) == check["report"]["sha256"] and check["report"]["path"] == "ci-report.json",
                        f"{check['id']}: passed CI check must reference ci-report.json")

    if isinstance(checks, list) and any(isinstance(c, dict) and c.get("status") == "passed"
                                      and (c.get("level") == 1 or c.get("id") == "parity") for c in checks):
        run("B2", b2)
    else:
        record("B2", "not_applicable", "No passed level-1 or parity claims")

    def b3():
        for check in checks:
            if check["status"] == "passed" and check["level"] in (2, 3, 4):
                protocol = parse_json(checked_report(check), check["report"]["path"])
                require(isinstance(protocol.get("signedBy"), str) and bool(protocol["signedBy"].strip()),
                        f"{check['id']}: signedBy missing")
                timestamp(protocol.get("signedAt"))
                require(protocol.get("checkId") == check["id"] and protocol.get("status") == "passed",
                        "protocol check/status mismatch")
                require(protocol.get("sitesSha256") == digest(report.document_bytes["sites"]),
                        "protocol belongs to different sites.json")

    if isinstance(checks, list) and any(isinstance(c, dict) and c.get("status") == "passed" and c.get("level") in (2, 3, 4) for c in checks):
        run("B3", b3)
    else:
        record("B3", "not_applicable", "No passed level-2/3/4 claims")

    def b4():
        require(all(c["status"] == "pending" for c in checks if c["level"] in (1, 2, 3, 4)),
                "scientific checks of a demo must remain pending")

    if mode == "demo":
        run("B4", b4)

    def d1():
        require(isinstance(report.dataset_id, str) and bool(report.dataset_id), "datasetId missing")
        require(all(d.get("datasetId") == report.dataset_id for d in report.documents.values()), "datasetId mismatch")
        require(provenance.get("sitesSha256") == digest(report.document_bytes["sites"]), "sites.json SHA-256 mismatch")

    run("D1", d1)

    if existing_release is not None:
        run("D2", lambda: check_existing_release(report, existing_release))
    else:
        record("D2", "not_applicable", "No existing DB release supplied; Django import enforces D2 in transaction")
    run("D3", lambda: validate_dataset(directory, document_bytes=report.document_bytes))

    def c4():
        require(set(api_documents) == set(DOCUMENTS), "need all three raw API document bodies")
        require(all(bytes(api_documents[name]) == raw for name, raw in report.document_bytes.items()),
                "API document bytes differ from release files")

    if api_documents is None:
        record("C4", "pending", "No raw API response bodies supplied")
    else:
        run("C4", c4)
    return report
