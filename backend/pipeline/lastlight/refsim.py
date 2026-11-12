"""Independent IEEE-754 reference for simulate and P1, written from the spec.

CLI input: one JSON {sites: [...], cases: [{siteIndex, fn, plan, context?}]}.
Output: one JSON line {value: ...} or {error: {code, message}} per case.
No TypeScript implementation, production schema validator, or network is used.
"""
import json
import math
import statistics
import sys


class PlanError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value):
    return number(value) and value == int(value)


def invalid(message):
    raise PlanError("INVALID_PLAN", message)


def validate_horizon(profile, length=None):
    if not isinstance(profile, list) or len(profile) < 2 or (length is not None and len(profile) != length):
        invalid("invalid horizon length")
    if any(not number(value) or not -90 <= value <= 90 for value in profile):
        invalid("invalid horizon angle")


def horizon_at(profile, azimuth):
    position = ((float(azimuth) % 360 + 360) % 360) * len(profile) / 360
    left = math.floor(position)
    a, b = float(profile[left]), float(profile[(left + 1) % len(profile)])
    return a + (b - a) * (position - left)


def step_minutes(site):
    value = site.get("stepMinutes", 60)
    if type(value) not in (int, float) or value not in (10, 60):
        invalid("stepMinutes must be 10 or 60")
    return int(value)


def validate_plan(site, plan, context=None):
    context = context or {}
    if not isinstance(site, dict) or not isinstance(plan, dict) or plan.get("siteId") != site.get("id"):
        invalid("unknown siteId")
    start = plan.get("startIndex")
    if not integer(start) or start < 0 or start + 168 * 60 // step_minutes(site) > len(site["hours"]):
        raise PlanError("OUT_OF_WINDOW", "requires a complete 168-hour window")
    if plan.get("durationH") != 168:
        invalid("durationH must be 168")
    for key in ("loadW", "panelW", "heaterW"):
        if not number(plan.get(key)) or plan[key] < 0:
            invalid(f"invalid {key}")
    if not number(plan.get("capacityWh")) or plan["capacityWh"] <= 0:
        invalid("invalid capacityWh")
    for key in ("initialPct", "minPct"):
        if not number(plan.get(key)) or not 0 <= plan[key] <= 100:
            invalid(f"invalid {key}")
    limit = plan.get("maxBlackoutH")
    if "maxBlackoutH" not in plan or (limit is not None and (not integer(limit) or limit < 0)):
        invalid("invalid maxBlackoutH")
    if plan["heaterW"] > 0 and context.get("capabilities", {}).get("heater") is not True:
        raise PlanError("FEATURE_UNAVAILABLE", "heater unavailable")
    mast = plan.get("mastM")
    if not number(mast) or mast not in (2, 5, 10):
        invalid("invalid mastM")
    validate_horizon(site["horizon"])
    profile = site["horizon"] if mast == 2 else site.get("horizonByMast", {}).get(str(int(mast)))
    if profile is None:
        raise PlanError("FEATURE_UNAVAILABLE", "mast profile unavailable")
    validate_horizon(profile, len(site["horizon"]))
    if mast != 2 and any(high > base for high, base in zip(profile, site["horizon"])):
        invalid("raised mast horizon exceeds base")
    return profile


def simulate(site, plan, context=None):
    profile = validate_plan(site, plan, context)
    minutes = step_minutes(site)
    count = 168 * 60 // minutes
    dt = minutes / 60
    capacity = float(plan["capacityWh"])
    energy = capacity * float(plan["initialPct"]) / 100
    threshold = capacity * float(plan["minPct"]) / 100
    if not math.isfinite(energy) or not math.isfinite(threshold):
        invalid("energy arithmetic overflow")
    minimum = energy
    dark = blackout = longest_dark = longest_blackout = lit = 0
    failure = {"hour": 0, "reason": "battery"} if plan["initialPct"] < plan["minPct"] else None
    output = []
    start = int(plan["startIndex"])
    for k, hour in enumerate(site["hours"][start:start + count]):
        for key in ("sunAz", "sunEl", "earthAz", "earthEl"):
            value = hour.get(key)
            if not number(value) or (not 0 <= value < 360 if key.endswith("Az") else not -90 <= value <= 90):
                invalid(f"invalid ephemeris {key}")
        sun = hour["sunEl"] > horizon_at(profile, hour["sunAz"])
        earth = hour["earthEl"] > horizon_at(profile, hour["earthAz"])
        s = int(sun)
        net = float(plan["panelW"]) * s - float(plan["loadW"]) - float(plan["heaterW"]) * (1 - s)
        energy = min(capacity, max(0.0, energy + net * dt))
        minimum = min(minimum, energy)
        dark = 0 if sun else dark + 1
        blackout = 0 if earth else blackout + 1
        longest_dark = max(longest_dark, dark)
        longest_blackout = max(longest_blackout, blackout)
        lit += s
        if failure is None:
            if energy < threshold:
                failure = {"hour": (k + 1) * minutes / 60, "reason": "battery"}
            elif plan["maxBlackoutH"] is not None and blackout * minutes > plan["maxBlackoutH"] * 60:
                failure = {"hour": (k + 1) * minutes / 60, "reason": "earth"}
        output.append({"sunlit": sun, "earthVisible": earth, "batteryPct": energy / capacity * 100})
    return {"ok": failure is None, "failure": failure, "hours": output,
            "kpis": {"minBatteryPct": minimum / capacity * 100, "longestDarkH": longest_dark * minutes / 60,
                     "longestBlackoutH": longest_blackout * minutes / 60, "sunlitPct": lit / count * 100}}


def min_capacity_for(site, plan, context=None):
    baseline = simulate(site, plan, context)
    if plan["maxBlackoutH"] is not None and baseline["kpis"]["longestBlackoutH"] > plan["maxBlackoutH"]:
        return None
    if plan["initialPct"] < plan["minPct"]:
        return None
    def passes(capacity):
        return simulate(site, {**plan, "capacityWh": capacity}, context)["ok"]
    if not passes(100000):
        return None
    low, high = 1, 100000
    while low < high:
        candidate = (low + high) // 2
        if passes(candidate):
            high = candidate
        else:
            low = candidate + 1
    return low


def uncertainty(site, plan, context=None):
    validate_plan(site, plan, context)
    if "horizonClones" not in site or (context or {}).get("capabilities", {}).get("uncertainty") is False:
        return None
    clones = site["horizonClones"]
    if not isinstance(clones, list) or not clones:
        invalid("clones must be a nonempty array")
    if plan["mastM"] != 2:
        raise PlanError("FEATURE_UNAVAILABLE", "clones are only defined for mast 2 m")
    failed = []
    passed = 0
    for profile in clones:
        validate_horizon(profile, len(site["horizon"]))
        result = simulate({**site, "horizon": profile}, plan, context)
        if result["ok"]:
            passed += 1
        else:
            failed.append(result["failure"]["hour"])
    return {"passRate": passed / len(clones), "failureHour": None if not failed else
            {"min": min(failed), "median": statistics.median(failed), "max": max(failed)}}


def main():
    batch = json.load(sys.stdin)
    functions = {"simulate": simulate, "minCapacityFor": min_capacity_for, "uncertainty": uncertainty}
    for case in batch["cases"]:
        try:
            value = functions[case["fn"]](batch["sites"][case["siteIndex"]], case["plan"], case.get("context"))
            result = {"value": value}
        except PlanError as error:
            result = {"error": {"code": error.code, "message": str(error)}}
        print(json.dumps(result, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
