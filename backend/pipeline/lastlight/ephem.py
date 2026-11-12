"""JPL Horizons lunar topocentric Sun/Earth ephemerides, with verified cache.

Network is used only on an explicit cache miss. Tests inject a byte transport.
API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
Conventions: https://ssd.jpl.nasa.gov/horizons/manual.html
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlencode

from .validate import read_json


API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGETS = {"sun": 10, "earth": 399}


class HorizonsError(ValueError):
    """Invalid configuration, response, or cache; no substitute data is used."""


def utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class EphemConfig:
    lat: float
    lon: float
    height_m: float  # Total observer altitude above Horizons reference ellipsoid.
    start: str
    count: int = 888
    step_minutes: int = 60

    def __post_init__(self):
        for field, value in (("lat", self.lat), ("lon", self.lon), ("height_m", self.height_m)):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise HorizonsError(f"{field} must be finite")
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:
            raise HorizonsError("expected latitude [-90,90], east-positive longitude [-180,180]")
        if type(self.count) is not int or not 2 <= self.count <= 10000:
            raise HorizonsError("count must be an integer in [2,10000]")
        if type(self.step_minutes) is not int or self.step_minutes not in (10, 60):
            raise HorizonsError("step_minutes must be 60 (production) or 10 (validation)")
        if not isinstance(self.start, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z", self.start):
            raise HorizonsError("start must be ISO UTC, aligned to a minute, ending in Z")
        try:
            self.start_datetime()
        except ValueError as error:
            raise HorizonsError("invalid start date") from error

    def start_datetime(self):
        return datetime.fromisoformat(self.start.replace("Z", "+00:00"))


def build_params(config: EphemConfig, target: int) -> dict[str, str]:
    if target not in TARGETS.values():
        raise HorizonsError("only Sun (10) and Earth (399) are supported")
    start = config.start_datetime()
    stop = start + timedelta(minutes=(config.count - 1) * config.step_minutes)
    raw = {
        "COMMAND": str(target), "CENTER": "coord@301", "COORD_TYPE": "GEODETIC",
        "SITE_COORD": f"{config.lon % 360:.12g},{config.lat:.12g},{config.height_m / 1000:.12g}",
        "MAKE_EPHEM": "YES", "OBJ_DATA": "NO", "EPHEM_TYPE": "OBSERVER",
        "START_TIME": start.strftime("%Y-%m-%d %H:%M:%S"),
        "STOP_TIME": stop.strftime("%Y-%m-%d %H:%M:%S"),
        "STEP_SIZE": f"{config.step_minutes} min", "QUANTITIES": "4",
        "APPARENT": "AIRLESS", "ANG_FORMAT": "DEG", "EXTRA_PREC": "YES",
        "CSV_FORMAT": "YES", "CAL_FORMAT": "CAL", "CAL_TYPE": "GREGORIAN",
        "TIME_TYPE": "UT", "TIME_ZONE": "+00:00", "TIME_DIGITS": "SECONDS",
        "ELEV_CUT": "-90", "SKIP_DAYLT": "NO",
    }
    return {"format": "json", **{key: f"'{value}'" for key, value in raw.items()}}


def requests_transport(url: str, params: dict[str, str], timeout: float) -> bytes:
    # Imported lazily: the verified offline cache works without requests installed.
    import requests
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as error:
        raise HorizonsError(f"Horizons HTTP request failed: {error}") from error


def parse_calendar(value: str) -> datetime:
    match = re.fullmatch(r"(?:A\.D\.\s+)?(\d{4})-([A-Za-z]{3})-(\d{2})\s+"
                         r"(\d{2}):(\d{2}):(\d{2})(?:\.(0+))?", value.strip())
    if not match:
        raise HorizonsError(f"unsupported Horizons UT calendar value: {value!r}")
    year, month, day, hour, minute, second, _ = match.groups()
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    try:
        return datetime(int(year), months.index(month.title()) + 1, int(day), int(hour),
                        int(minute), int(second), tzinfo=timezone.utc)
    except ValueError as error:
        raise HorizonsError(f"invalid calendar value: {value!r}") from error


def parse_response(raw: bytes, config: EphemConfig, target: int) -> tuple[list[dict], dict]:
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise HorizonsError("Horizons response is not JSON") from error
    if not isinstance(payload, dict) or payload.get("error"):
        raise HorizonsError(f"Horizons API error: {payload}")
    text = payload.get("result")
    signature = payload.get("signature")
    if not isinstance(text, str) or not isinstance(signature, dict):
        raise HorizonsError("missing result or API signature")
    if not re.search(r"Center body name:\s*Moon\s*\(301\)", text):
        raise HorizonsError("response observer is not on the Moon")
    if not re.search(rf"Target body name:[^\n]*\({target}\)", text):
        raise HorizonsError("response target mismatch")
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        raise HorizonsError("missing or ambiguous ephemeris table markers")
    before, rest = text.split("$$SOE")
    body, _ = rest.split("$$EOE")
    headers = [next(csv.reader([line])) for line in before.splitlines()
               if "Date__(UT)" in line and "," in line]
    if len(headers) != 1:
        raise HorizonsError("expected one UT CSV header")
    header = [item.strip() for item in headers[0]]

    def column(prefix):
        indices = [i for i, label in enumerate(header)
                   if label.startswith(prefix) and "(a-app)" in label]
        if len(indices) != 1:
            raise HorizonsError(f"missing airless {prefix} column")
        return indices[0]

    az_index, el_index = column("Azi"), column("Elev")
    rows = []
    for row in csv.reader(body.strip().splitlines()):
        if not row or all(not field.strip() for field in row):
            continue
        if len(row) != len(header):
            raise HorizonsError("CSV row width mismatch")
        try:
            timestamp = parse_calendar(row[0])
            az, el = float(row[az_index]), float(row[el_index])
        except (ValueError, IndexError) as error:
            raise HorizonsError("invalid time or angle (including n.a.)") from error
        if not math.isfinite(az) or not math.isfinite(el) or not 0 <= az < 360 or not -90 <= el <= 90:
            raise HorizonsError("non-finite or out-of-range angle")
        expected = config.start_datetime() + timedelta(minutes=len(rows) * config.step_minutes)
        if timestamp != expected:
            raise HorizonsError("missing, duplicate, or out-of-order timestamp")
        rows.append({"t": utc(timestamp), "az": az, "el": el})
    if len(rows) != config.count:
        raise HorizonsError(f"expected {config.count} rows, got {len(rows)}")
    return rows, signature


class HorizonsClient:
    def __init__(self, cache_dir: Path, *, offline=False, timeout=60,
                 transport: Callable = requests_transport):
        if not math.isfinite(timeout) or timeout <= 0:
            raise HorizonsError("timeout must be finite and positive")
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.timeout = timeout
        self.transport = transport

    def fetch(self, config: EphemConfig, target: int) -> tuple[list[dict], dict]:
        params = build_params(config, target)
        query = API_URL + "?" + urlencode(sorted(params.items()))
        key = sha256(query.encode()).hexdigest()
        raw_path = self.cache_dir / f"{key}.json"
        meta_path = self.cache_dir / f"{key}.meta.json"
        cached = raw_path.exists() or meta_path.exists()
        if cached:
            if not raw_path.is_file() or not meta_path.is_file():
                raise HorizonsError("incomplete cache entry")
            raw, meta = raw_path.read_bytes(), read_json(meta_path)
            if meta.get("query") != query or meta.get("sha256") != sha256(raw).hexdigest():
                raise HorizonsError("cache query or SHA-256 mismatch; refusing download")
            rows, signature = parse_response(raw, config, target)
            if meta.get("version") != signature.get("version"):
                raise HorizonsError("cache API version mismatch")
        else:
            if self.offline:
                raise HorizonsError("offline cache miss")
            raw = self.transport(API_URL, params, self.timeout)
            rows, signature = parse_response(raw, config, target)
            meta = {"id": f"horizons-{target}-{key}", "synthetic": False, "url": API_URL,
                    "query": query, "version": signature.get("version"),
                    "accessedAt": utc(datetime.now(timezone.utc)), "sha256": sha256(raw).hexdigest()}
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(raw)
            meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return rows, meta

    def ephemerides(self, config: EphemConfig) -> dict:
        sun, sun_source = self.fetch(config, TARGETS["sun"])
        earth, earth_source = self.fetch(config, TARGETS["earth"])
        hours = [{"t": s["t"], "sunAz": s["az"], "sunEl": s["el"],
                  "earthAz": e["az"], "earthEl": e["el"]} for s, e in zip(sun, earth)]
        return {"hours": hours, "stepMinutes": config.step_minutes,
                "sources": [sun_source, earth_source]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lat", "lon", "height-m"):
        parser.add_argument(f"--{name}", type=float, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--count", type=int, default=888)
    parser.add_argument("--step-minutes", type=int, choices=(10, 60), default=60)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    config = EphemConfig(args.lat, args.lon, args.height_m, args.start, args.count, args.step_minutes)
    result = HorizonsClient(args.cache, offline=args.offline).ephemerides(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"PASS: {len(result['hours'])} ephemeris rows written to {args.output}")


if __name__ == "__main__":
    main()
