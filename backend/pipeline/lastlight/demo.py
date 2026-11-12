"""Deterministic synthetic mini-2x200; no external scientific data."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import importlib.util
from pathlib import Path
import random

from .validate import ROOT, validate_dataset


DEFAULT_OUTPUT = ROOT / "packages/sim/fixtures/mini-2x200"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def generate(output=DEFAULT_OUTPUT, seed=42):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dataset_id = f"demo-mini-2x200-v2-10min-seed-{seed}"
    horizon_b = [round(max(0, 20 * (1 - abs(az - 180) / 20),
                           4 * (1 - abs(az - 315) / 10)), 6) for az in range(360)]
    sites = []
    for site_id, lat, lon, horizon in (("A", -89.0, 0.0, [0] * 360),
                                      ("B", -89.5, 45.0, horizon_b)):
        hours = []
        for index in range(1200):
            hour_index = index // 6
            dark = site_id == "B" and 6 <= hour_index % 24 < 11
            blocked = site_id == "B" and any(lo <= hour_index < hi for lo, hi in
                                               ((20, 23), (70, 76), (150, 155)))
            equality = site_id == "B" and index == 600
            hours.append({
                "t": (start + timedelta(minutes=index * 10)).isoformat().replace("+00:00", "Z"),
                "sunAz": 180 if dark else round(rng.uniform(0, 359.999), 6),
                "sunEl": 10 if dark else 25,
                "earthAz": 315 if equality else (180 if blocked else 0),
                "earthEl": 4 if equality else (10 if blocked else 5),
            })
        sites.append({"id": site_id, "name": f"DEMO Site {site_id}", "lat": lat, "lon": lon, "stepMinutes": 10,
                      "horizon": horizon, "hours": hours})
    write_json(output / "sites.json", {
        "version": 2, "datasetId": dataset_id,
        "window": {"start": "2026-01-01T00:00:00Z", "stepMinutes": 10, "count": 1200}, "sites": sites,
    })
    write_json(output / "provenance.json", {
        "datasetId": dataset_id, "mode": "demo",
        "generator": {"name": "lastlight.demo", "version": "2.0.0"}, "seed": seed,
        "coordinateConventions": {"angles": "degrees", "heights": "meters", "time": "UTC",
                                  "azimuth": "north-clockwise",
                                  "longitude": "east-positive [-180,180]", "horizonMastM": 2},
        "sources": [{"id": "synthetic-demo", "synthetic": True, "url": None,
                     "query": f"lastlight.demo v2.0.0 stepMinutes=10 seed={seed}", "version": "2.0.0",
                     "accessedAt": None, "sha256": None}],
        "capabilities": {"minCapacity": False, "heater": False, "uncertainty": False},
        "sitesSha256": sha256((output / "sites.json").read_bytes()).hexdigest(),
        "secondSignature": {"status": "pending", "signedBy": None, "signedAt": None,
                            "sitesSha256": sha256((output / "sites.json").read_bytes()).hexdigest(),
                            "scope": "fixture-expectations",
                            "comment": "Independent reviewer has not signed the fixture expectations."},
        "notes": ["DEMO DATA: all coordinates, horizons and ephemerides are synthetic.",
                  "Not suitable for mission planning or scientific validation.",
                  "A: always sunlit and Earth visible. B: mountain 20 deg at 180 deg, hill 4 deg at 315 deg.",
                  "B: shadow at hours 6..10 UTC daily; Earth blocked at [20,23), [70,76), [150,155).",
                  "B: Earth exactly on horizon at hour 100 for one 10-minute interval; equality means blocked.",
                  "v2: 200 hours, 1200 independently generated synthetic samples at exactly 10 minutes.",
                  "P1 features are unavailable. Seed controls synthetic sun azimuths.",
                  "Unknown external-source metadata is null; no data was fetched."]
    })
    checks = [{"id": f"level-{level}", "level": level, "status": "pending", "ranAt": None,
               "measurement": None, "tolerance": None, "report": None} for level in range(1, 5)]
    checks.insert(0, {"id": "schema", "level": None, "status": "pending", "ranAt": None,
                      "measurement": None, "tolerance": None, "report": None})
    validation = {"datasetId": dataset_id, "checks": checks}
    write_json(output / "validation.json", validation)
    validate_dataset(output)
    # Timestamp is real execution time, kept outside the deterministic sites.json.
    ran_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    report = {"check": "schema", "ranAt": ran_at, "status": "passed",
              "validators": ["lastlight.schema_validation (project keyword subset)"]
                            + (["jsonschema Draft202012Validator"]
                               if importlib.util.find_spec("jsonschema") else []),
              "measurement": {"documents": 3, "schemaErrors": 0, "invariantErrors": 0},
              "tolerance": {"schemaErrors": 0, "invariantErrors": 0},
              "sitesSha256": sha256((output / "sites.json").read_bytes()).hexdigest(),
              "schemasSha256": {name: sha256(path.read_bytes()).hexdigest() for name in
                                 ("sites", "provenance", "validation")
                                 for path in [ROOT / "schemas" / f"{name}.schema.json"]}}
    write_json(output / "schema-report.json", report)
    checks[0].update({"status": "passed", "ranAt": ran_at,
                      "measurement": report["measurement"], "tolerance": report["tolerance"],
                      "report": {"path": "schema-report.json",
                                 "sha256": sha256((output / "schema-report.json").read_bytes()).hexdigest()}})
    write_json(output / "validation.json", validation)
    validate_dataset(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate_dataset(args.output)
    else:
        generate(args.output, args.seed)
    print(f"PASS: 3 documents validated: {args.output}")


if __name__ == "__main__":
    main()
