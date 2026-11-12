"""Public, stateless mission preview endpoint."""

import json
import math
from datetime import datetime, timedelta, timezone

from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


MOON_RADIUS_M = 1_737_400.0
LUNAR_DAY_DAYS = 29.53  # NASA Moon Fact Sheet, synodic period.
MODEL_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
# Fixed demo vehicle and forecast settings, not mission safety requirements.
MISSION_HOURS = 24
PANEL_POWER_W = 200.0
SYSTEM_POWER_W = 30.0
HEATER_POWER_W = 50.0
BATTERY_CAPACITY_WH = 2_000.0
INITIAL_SOC_PERCENT = 100.0
MIN_SOC_PERCENT = 20.0
MAX_SLOPE_DEG = 15.0
DTE_MIN_ELEVATION_DEG = 5.0
LANDING_RADIUS_M = 100
LANDING_GRID_STEP_M = 25
LANDING_SLOPE_STEP_M = 10.0
# Chosen demonstration coefficients, not measured lunar deposition rates.
DUST_DECAY_PER_HOUR = 0.002
DUST_MIN_EFFICIENCY = 0.60
SAFE_HAVEN_RADIUS_M = 1_000
SAFE_HAVEN_GRID_STEP_M = 100
SPEED_OF_LIGHT_KM_S = 299_792.458
# NASA lunar-distance reference range; epoch and 28-day phase are synthetic.
EARTH_MOON_MEAN_DISTANCE_KM = 384_400.0
EARTH_MOON_DISTANCE_AMPLITUDE_KM = 21_100.0
SIGNAL_DISTANCE_PERIOD_DAYS = 28.0
# Illustrative fully restrained, one-dimensional elastic material model.
THERMAL_YOUNG_MODULUS_GPA = 70.0
THERMAL_EXPANSION_PER_K = 23e-6
THERMAL_ALLOWABLE_STRESS_MPA = 150.0


def _terrain_gradient(x, y, step=100.0):
    return (
        (_elevation(x + step, y) - _elevation(x - step, y)) / (2 * step),
        (_elevation(x, y + step) - _elevation(x, y - step)) / (2 * step),
    )


def _offset_coordinates(latitude, longitude, east_m, north_m):
    """Spherical tangent offset, including pole crossings and longitude wrap."""
    distance = math.hypot(east_m, north_m)
    if distance == 0:
        return latitude, longitude
    lat, lon = math.radians(latitude), math.radians(longitude)
    up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
    angle = distance / MOON_RADIUS_M
    point = [math.cos(angle) * up[i] + math.sin(angle) * (
        east_m * east[i] + north_m * north[i]
    ) / distance for i in range(3)]
    return (math.degrees(math.atan2(point[2], math.hypot(point[0], point[1]))),
            math.degrees(math.atan2(point[1], point[0])))


def calculate_landing_zone(latitude, longitude):
    """Estimate slope safety on a 25 m disk grid plus a sampled 100 m rim.

    The safe radius is the largest tested 25 m radius whose enclosed samples
    pass. This sampled estimate does not certify terrain between samples.
    Neighbours outside the permitted latitude band count as unsafe.
    """
    offsets = {(float(east), float(north))
               for east in range(-LANDING_RADIUS_M, LANDING_RADIUS_M + 1, LANDING_GRID_STEP_M)
               for north in range(-LANDING_RADIUS_M, LANDING_RADIUS_M + 1, LANDING_GRID_STEP_M)
               if east ** 2 + north ** 2 <= LANDING_RADIUS_M ** 2}
    for index in range(32):
        angle = math.tau * index / 32
        offsets.add((round(LANDING_RADIUS_M * math.cos(angle), 8),
                     round(LANDING_RADIUS_M * math.sin(angle), 8)))
    samples = []
    for east, north in sorted(offsets, key=lambda p: (math.hypot(*p), p)):
        lat, lon = _offset_coordinates(latitude, longitude, east, north)
        x, y = _polar_position(lat, lon)
        gx, gy = _terrain_gradient(x, y, LANDING_SLOPE_STEP_M)
        slope = math.degrees(math.atan(math.hypot(gx, gy)))
        permitted = -90 <= lat <= -60
        samples.append({
            "east_m": east, "north_m": north, "distance_m": round(math.hypot(east, north), 6),
            "latitude": lat, "longitude": lon, "elevation_m": round(_elevation(x, y), 2),
            "slope_deg": slope, "within_allowed_region": permitted,
            "safe": permitted and slope <= MAX_SLOPE_DEG,
        })
    slopes = [sample["slope_deg"] for sample in samples]
    mean = sum(slopes) / len(slopes)
    safe_radius = 0
    for radius in range(LANDING_GRID_STEP_M, LANDING_RADIUS_M + 1, LANDING_GRID_STEP_M):
        if all(sample["safe"] for sample in samples if sample["distance_m"] <= radius):
            safe_radius = radius
        else:
            break
    unsafe_count = sum(not sample["safe"] for sample in samples)
    return {
        "assessed_radius_m": LANDING_RADIUS_M,
        "safe_radius_estimate_m": safe_radius,
        "grid_step_m": LANDING_GRID_STEP_M, "slope_sampling_step_m": LANDING_SLOPE_STEP_M,
        "max_allowed_slope_deg": MAX_SLOPE_DEG,
        "is_safe": unsafe_count == 0,
        "sample_count": len(samples), "unsafe_sample_count": unsafe_count,
        "min_slope_deg": min(slopes), "max_slope_deg": max(slopes),
        "mean_slope_deg": mean,
        "slope_stddev_deg": math.sqrt(sum((slope - mean) ** 2 for slope in slopes) / len(slopes)),
        "slope_range_deg": max(slopes) - min(slopes),
        "elevation_range_m": round(max(s["elevation_m"] for s in samples)
                                   - min(s["elevation_m"] for s in samples), 2),
        "samples": samples,
    }


def _polar_position(latitude, longitude):
    radius = MOON_RADIUS_M * math.radians(latitude + 90)
    lon = math.radians(longitude)
    return radius * math.cos(lon), radius * math.sin(lon)


def _local_horizon(x, y, direction_x, direction_y):
    """Sample the synthetic terrain horizon along a local tangent direction."""
    horizontal = math.hypot(direction_x, direction_y)
    horizon = 0.0
    if horizontal > 1e-12:
        elevation = _elevation(x, y)
        for distance in (250, 500, 1_000, 2_000, 5_000, 10_000, 20_000):
            obstacle = _elevation(x + distance * direction_x / horizontal,
                                  y + distance * direction_y / horizontal)
            curvature_drop = distance ** 2 / (2 * MOON_RADIUS_M)
            horizon = max(horizon, math.atan2(obstacle - elevation - curvature_drop, distance))
    return horizon


def _elevation(x, y):
    """Synthetic polar terrain, metres above a reference lunar sphere.

    Waves and a crater are illustrative, not a measured elevation dataset.
    The Moon has no sea level. x/y are distances in a south polar plane.
    """
    crater = math.exp(-((x - 60_000) ** 2 + (y + 40_000) ** 2) / 20_000 ** 2)
    return (800 * math.sin(x / 8_000) * math.cos(y / 10_000)
            + 350 * math.cos(x / 3_000 + y / 5_000) - 2_000 * crater)


def calculate_conditions(latitude, longitude, timestamp):
    """Deterministic preview model; no ephemeris, DEM or thermal history.

    Insolation is instantaneous incident flux as a percentage of normal
    sunlight, not the fraction of a day spent in sunlight. Solar phase and
    season have an arbitrary origin at MODEL_EPOCH. Polar-plane distances
    approximate the surface; shadows use a sampled local terrain horizon.
    Temperature is an illustrative instantaneous equilibrium in kelvin,
    converted to Celsius, without thermal inertia or subsurface conduction.
    """
    lat, lon = math.radians(latitude), math.radians(longitude)
    x, y = _polar_position(latitude, longitude)
    elevation = _elevation(x, y)
    gradient_x, gradient_y = _terrain_gradient(x, y)
    slope = math.atan(math.hypot(gradient_x, gradient_y))

    days = (timestamp.astimezone(timezone.utc) - MODEL_EPOCH).total_seconds() / 86_400
    hour_angle = lon - math.tau * (days % LUNAR_DAY_DAYS) / LUNAR_DAY_DAYS
    declination = math.radians(1.54) * math.sin(math.tau * (days % 365.25) / 365.25)
    sun_up = (math.sin(lat) * math.sin(declination)
              + math.cos(lat) * math.cos(declination) * math.cos(hour_angle))
    sun_east = -math.cos(declination) * math.sin(hour_angle)
    sun_north = (math.cos(lat) * math.sin(declination)
                 - math.sin(lat) * math.cos(declination) * math.cos(hour_angle))
    sun_x = sun_north * math.cos(lon) - sun_east * math.sin(lon)
    sun_y = sun_north * math.sin(lon) + sun_east * math.cos(lon)
    horizontal = math.hypot(sun_x, sun_y)
    sun_elevation = math.atan2(sun_up, horizontal)

    horizon = _local_horizon(x, y, sun_x, sun_y)

    incidence = (sun_up - gradient_x * sun_x - gradient_y * sun_y) / math.sqrt(
        1 + gradient_x ** 2 + gradient_y ** 2
    )
    illuminated = sun_elevation > horizon and incidence > 0
    insolation = min(1.0, max(0.0, incidence)) if illuminated else 0.0
    # Chosen demo bounds: 50 K in shadow, 390 K at normal incidence.
    temperature_k = (50.0 ** 4 + insolation * (390.0 ** 4 - 50.0 ** 4)) ** 0.25

    return {
        "elevation_m": round(elevation, 2),
        # Keep full precision for the mission's safety threshold decision.
        "slope_deg": math.degrees(slope),
        "sun_elevation_deg": round(math.degrees(sun_elevation), 2),
        "insolation_percent": round(insolation * 100, 2),
        "is_shadowed": not illuminated,
        "temperature_c": round(temperature_k - 273.15, 2),
        "model": "synthetic-v1",
    }


def _utc_string(timestamp):
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def calculate_dust(elapsed_h, duration_h=1.0):
    """Panel attenuation since landing; analytic mean over a forecast bin.

    A residual efficiency plus exponential decay avoids negative efficiency.
    Accumulation continues in shadow. Every request starts a new mission with
    clean panels; absolute calendar dates do not imply prior dust exposure.
    """
    if not math.isfinite(elapsed_h) or elapsed_h < 0:
        raise ValueError("elapsed_h must be finite and non-negative")
    if not math.isfinite(duration_h) or duration_h <= 0:
        raise ValueError("duration_h must be finite and positive")
    start_decay = math.exp(-DUST_DECAY_PER_HOUR * elapsed_h)
    end_decay = start_decay * math.exp(-DUST_DECAY_PER_HOUR * duration_h)
    decay_interval = DUST_DECAY_PER_HOUR * duration_h
    mean_decay = (start_decay * -math.expm1(-decay_interval) / decay_interval
                  if decay_interval else start_decay)
    return {
        "start_efficiency_percent": 100 * (DUST_MIN_EFFICIENCY + (1 - DUST_MIN_EFFICIENCY) * start_decay),
        "end_efficiency_percent": 100 * (DUST_MIN_EFFICIENCY + (1 - DUST_MIN_EFFICIENCY) * end_decay),
        "mean_efficiency_percent": 100 * (DUST_MIN_EFFICIENCY + (1 - DUST_MIN_EFFICIENCY) * mean_decay),
    }


def calculate_radiation(conditions, timestamp):
    """Dimensionless demonstration scenario, NOT a dose or flare prediction.

    A chosen periodic activity scenario and local solar elevation modulate
    an index. Shadow removes only the directional exposure term, never the
    background or synthetic particle-event term. No live observations used.
    """
    days = (timestamp.astimezone(timezone.utc) - MODEL_EPOCH).total_seconds() / 86_400
    activity = (0.5 + 0.5 * math.sin(math.tau * (days % 27.0) / 27.0)) ** 8
    elevation = conditions.get("sun_elevation_deg", 0.0)
    exposure = (max(0.0, math.sin(math.radians(elevation)))
                if not conditions["is_shadowed"] else 0.0)
    index = min(100.0, 20.0 + 60.0 * activity + 20.0 * exposure)
    return {
        "index": round(index, 4),
        "risk_level": "HIGH" if index >= 70 else "MODERATE" if index >= 40 else "LOW",
        "synthetic_activity_index": round(activity * 100, 4),
        "solar_exposure_index": round(exposure * 100, 4),
        "flare_probability": None,
    }


def calculate_thermal_shock(previous_temperature_c, temperature_c, interval_h=1.0):
    """Screen a temperature step with |stress| = E * alpha * |delta T|.

    This is a fully restrained elastic estimate, not a transient fracture or
    fatigue solver. Above the chosen allowable stress, the elastic prediction
    only flags risk; it does not describe plastic response. The first sample
    has no pre-mission history and therefore no inferred thermal shock.
    """
    if not math.isfinite(interval_h) or interval_h <= 0:
        raise ValueError("interval_h must be finite and positive")
    for value in (previous_temperature_c, temperature_c):
        if value is not None and (not math.isfinite(value) or value < -273.15):
            raise ValueError("temperature must be finite and at least absolute zero")
    if temperature_c is None:
        raise ValueError("temperature_c is required")
    delta = temperature_c - previous_temperature_c if previous_temperature_c is not None else 0.0
    stress = THERMAL_YOUNG_MODULUS_GPA * 1_000 * THERMAL_EXPANSION_PER_K * abs(delta)
    ratio = stress / THERMAL_ALLOWABLE_STRESS_MPA
    return {
        "has_previous_sample": previous_temperature_c is not None,
        "delta_temperature_c": round(delta, 4),
        "temperature_rate_c_per_h": round(abs(delta) / interval_h, 4),
        "constrained_stress_mpa": round(stress, 4),
        "allowable_stress_ratio": round(ratio, 6),
        "risk_index": round(min(100.0, ratio * 100), 4),
        "risk_level": "HIGH" if ratio >= 1 else "MODERATE" if ratio >= 0.5 else "LOW",
        "direction": ("INITIAL" if previous_temperature_c is None else
                      "HEATING" if delta > 0 else "COOLING" if delta < 0 else "STABLE"),
    }


def calculate_signal_latency(timestamp, *, dte_visible):
    """Vacuum light time using a synthetic Earth/Moon centre distance.

    No station geometry, electronics, queueing or relay delay is modelled.
    Geometric light times remain defined without DTE; usable direct-link times
    are null then, since propagation time cannot make an obstructed link work.
    """
    days = (timestamp.astimezone(timezone.utc) - MODEL_EPOCH).total_seconds() / 86_400
    phase = math.tau * (days % SIGNAL_DISTANCE_PERIOD_DAYS) / SIGNAL_DISTANCE_PERIOD_DAYS
    distance = EARTH_MOON_MEAN_DISTANCE_KM - EARTH_MOON_DISTANCE_AMPLITUDE_KM * math.cos(phase)
    one_way = distance / SPEED_OF_LIGHT_KM_S
    return {
        "distance_km": round(distance, 4),
        "one_way_s": round(one_way, 8),
        "round_trip_s": round(2 * one_way, 8),
        "link_available": dte_visible,
        "dte_one_way_s": round(one_way, 8) if dte_visible else None,
        "dte_round_trip_s": round(2 * one_way, 8) if dte_visible else None,
    }


def calculate_power(conditions, energy_wh, duration_h=1.0, *, dust_efficiency=1.0):
    """One lossless battery step; track curtailed and unserved energy explicitly."""
    if not 0 <= dust_efficiency <= 1:
        raise ValueError("dust_efficiency must be between 0 and 1")
    clean_generation = PANEL_POWER_W * conditions["insolation_percent"] / 100
    generation = clean_generation * dust_efficiency
    heater = HEATER_POWER_W if conditions["is_shadowed"] else 0.0
    consumption = SYSTEM_POWER_W + heater
    available = energy_wh + (generation - consumption) * duration_h
    stored = min(BATTERY_CAPACITY_WH, max(0.0, available))
    return {
        "generation_w": generation,
        "clean_generation_w": clean_generation,
        "dust_loss_w": clean_generation - generation,
        "systems_w": SYSTEM_POWER_W,
        "heater_w": heater,
        "consumption_w": consumption,
        "net_w": generation - consumption,
        "energy_wh": stored,
        "battery_soc_percent": stored / BATTERY_CAPACITY_WH * 100,
        "unserved_energy_wh": max(0.0, -available),
        "curtailed_energy_wh": max(0.0, available - BATTERY_CAPACITY_WH),
    }


def calculate_dte(latitude, longitude, timestamp):
    """Toy Earth-centre visibility, with terrain and antenna elevation mask.

    A chosen 28-day wobble about the near-side meridian illustrates windows;
    it is not an Earth ephemeris. No ground station, link budget or occultation
    model is included. The Earth is treated as a point at infinite distance.
    """
    days = (timestamp.astimezone(timezone.utc) - MODEL_EPOCH).total_seconds() / 86_400
    phase = math.tau * (days % 28.0) / 28.0
    earth_lat = math.radians(6.0) * math.sin(phase)
    earth_lon = math.radians(6.0) * math.cos(phase)
    lat, lon = math.radians(latitude), math.radians(longitude)
    angle = lon - earth_lon
    up = math.sin(lat) * math.sin(earth_lat) + math.cos(lat) * math.cos(earth_lat) * math.cos(angle)
    east = -math.cos(earth_lat) * math.sin(angle)
    north = math.cos(lat) * math.sin(earth_lat) - math.sin(lat) * math.cos(earth_lat) * math.cos(angle)
    dx = north * math.cos(lon) - east * math.sin(lon)
    dy = north * math.sin(lon) + east * math.cos(lon)
    elevation = math.atan2(up, math.hypot(dx, dy))
    x, y = _polar_position(latitude, longitude)
    mask = max(math.radians(DTE_MIN_ELEVATION_DEG), _local_horizon(x, y, dx, dy))
    return {"visible": elevation > mask, "earth_elevation_deg": round(math.degrees(elevation), 2)}


def calculate_mission(latitude, longitude, timestamp):
    """Forecast [start, end) using one-hour, start-of-bin samples.

    Thresholds include the initial and every subsequent battery state. DTE
    boundaries are approximate to one hour; unavailable DTE does not itself
    fail the mission. Energy integration assumes each sample lasts one hour.
    """
    start = timestamp.astimezone(timezone.utc)
    end = start + timedelta(hours=MISSION_HOURS)
    initial = calculate_conditions(latitude, longitude, start)
    landing_zone = calculate_landing_zone(latitude, longitude)
    energy = BATTERY_CAPACITY_WH * INITIAL_SOC_PERCENT / 100
    minimum_soc = INITIAL_SOC_PERCENT
    generated = consumed = unserved = curtailed = clean_generated = dust_loss = 0.0
    timeline, windows = [], []
    window_start = None
    shadow_run = longest_shadow = blackout_run = longest_blackout = 0
    previous_temperature = None
    previous_shadow = None
    for hour in range(MISSION_HOURS):
        sample_time = start + timedelta(hours=hour)
        conditions = initial if hour == 0 else calculate_conditions(latitude, longitude, sample_time)
        energy_start = energy
        dust = calculate_dust(hour)
        power = calculate_power(conditions, energy,
                                dust_efficiency=dust["mean_efficiency_percent"] / 100)
        radiation = calculate_radiation(conditions, sample_time)
        energy = power["energy_wh"]
        minimum_soc = min(minimum_soc, power["battery_soc_percent"])
        generated += power["generation_w"]  # W * one hour = Wh
        clean_generated += power["clean_generation_w"]
        dust_loss += power["dust_loss_w"]
        consumed += power["consumption_w"]
        unserved += power["unserved_energy_wh"]
        curtailed += power["curtailed_energy_wh"]
        dte = calculate_dte(latitude, longitude, sample_time)
        thermal = calculate_thermal_shock(previous_temperature, conditions["temperature_c"])
        thermal["illumination_transition"] = (
            "INITIAL" if previous_shadow is None else
            "SHADOW_TO_SUN" if previous_shadow and not conditions["is_shadowed"] else
            "SUN_TO_SHADOW" if not previous_shadow and conditions["is_shadowed"] else "NONE"
        )
        previous_temperature = conditions["temperature_c"]
        previous_shadow = conditions["is_shadowed"]
        latency = calculate_signal_latency(sample_time, dte_visible=dte["visible"])
        shadow_run = shadow_run + 1 if conditions["is_shadowed"] else 0
        blackout_run = 0 if dte["visible"] else blackout_run + 1
        longest_shadow = max(longest_shadow, shadow_run)
        longest_blackout = max(longest_blackout, blackout_run)
        if dte["visible"] and window_start is None:
            window_start = sample_time
        elif not dte["visible"] and window_start is not None:
            windows.append({"start": _utc_string(window_start), "end": _utc_string(sample_time)})
            window_start = None
        timeline.append({
            "hour": hour,
            "start": _utc_string(sample_time),
            "end": _utc_string(sample_time + timedelta(hours=1)),
            "insolation_percent": conditions["insolation_percent"],
            "is_shadowed": conditions["is_shadowed"],
            "temperature_c": conditions["temperature_c"],
            **{key: round(value, 4) for key, value in power.items()},
            "generated_energy_wh": round(power["generation_w"], 4),
            "consumed_energy_wh": round(power["consumption_w"], 4),
            "battery_soc_start_percent": round(energy_start / BATTERY_CAPACITY_WH * 100, 4),
            "dust": {key: round(value, 4) for key, value in dust.items()},
            "radiation": radiation,
            "thermal_shock": thermal,
            "signal_latency": latency,
            **dte,
        })
    if window_start is not None:
        windows.append({"start": _utc_string(window_start), "end": _utc_string(end)})
    reasons = []
    if initial["slope_deg"] > MAX_SLOPE_DEG:
        reasons.append("UNSAFE_SLOPE")
    if not landing_zone["is_safe"]:
        reasons.append("UNSAFE_LANDING_ZONE")
    if minimum_soc < MIN_SOC_PERCENT:
        reasons.append("LOW_BATTERY")
    if unserved > 0:
        reasons.append("POWER_SHORTFALL")
    return {
        **initial,
        "status": "FAIL" if reasons else "SUCCESS",
        "failure_reasons": reasons,
        "landing_zone": landing_zone,
        "metadata": {
            "schema_version": "4.0", "is_simulation": True,
            "limitations": [
                "Synthetic terrain and Sun/Earth directions; no measured DEM or ephemeris.",
                "Landing radius is a sampled estimate; hazards between samples are unresolved.",
                "DTE and energy use hourly samples; battery is ideal and temperature has no thermal inertia.",
                "Dust coefficients are illustrative; radiation index is not a dose or a solar-flare forecast.",
                "Safe haven is nearest among sampled candidates; no surface traverse is validated.",
                "Thermal stress is an illustrative constrained elastic screen, not material certification.",
                "Signal delay uses synthetic centre-to-centre distance and excludes processing or relay delays.",
            ],
        },
        "summary": {
            "sunlit_hours": sum(not row["is_shadowed"] for row in timeline),
            "shadow_hours": sum(row["is_shadowed"] for row in timeline),
            "longest_shadow_h": longest_shadow, "longest_dte_blackout_h": longest_blackout,
            "min_temperature_c": min(row["temperature_c"] for row in timeline),
            "max_temperature_c": max(row["temperature_c"] for row in timeline),
            "landing_zone_safe": landing_zone["is_safe"],
            "safe_radius_estimate_m": landing_zone["safe_radius_estimate_m"],
            "peak_thermal_stress_mpa": max(row["thermal_shock"]["constrained_stress_mpa"] for row in timeline),
            "min_signal_one_way_s": min(row["signal_latency"]["one_way_s"] for row in timeline),
            "max_signal_one_way_s": max(row["signal_latency"]["one_way_s"] for row in timeline),
        },
        "assumptions": {
            "duration_h": MISSION_HOURS, "step_h": 1,
            "panel_power_w": PANEL_POWER_W, "systems_w": SYSTEM_POWER_W,
            "shadow_heater_w": HEATER_POWER_W, "battery_capacity_wh": BATTERY_CAPACITY_WH,
            "initial_soc_percent": INITIAL_SOC_PERCENT, "min_soc_percent": MIN_SOC_PERCENT,
            "max_slope_deg": MAX_SLOPE_DEG, "dte_min_elevation_deg": DTE_MIN_ELEVATION_DEG,
            "battery_model": "ideal-lossless", "dte_model": "synthetic-earth-wobble",
            "dust_decay_per_hour": DUST_DECAY_PER_HOUR,
            "dust_min_efficiency_percent": DUST_MIN_EFFICIENCY * 100,
            "dust_initial_age_h": 0, "radiation_affects_verdict": False,
            "thermal_shock_affects_verdict": False,
        },
        "power": {
            "initial_generation_w": timeline[0]["generation_w"],
            "initial_consumption_w": timeline[0]["consumption_w"],
            "generated_energy_wh": round(generated, 4),
            "clean_generated_energy_wh": round(clean_generated, 4),
            "dust_loss_energy_wh": round(dust_loss, 4),
            "consumed_energy_wh": round(consumed, 4),
            "unserved_energy_wh": round(unserved, 4),
            "curtailed_energy_wh": round(curtailed, 4),
            "final_energy_wh": round(energy, 4),
            "final_soc_percent": round(energy / BATTERY_CAPACITY_WH * 100, 4),
            "minimum_soc_percent": round(minimum_soc, 4),
        },
        "dte": {"visible_at_start": timeline[0]["visible"], "windows": windows,
                "available_hours": sum(row["visible"] for row in timeline)},
        "dust": {
            "model": "synthetic-exponential-deposition",
            "age_at_start_h": 0, "age_at_end_h": MISSION_HOURS,
            "initial_efficiency_percent": timeline[0]["dust"]["start_efficiency_percent"],
            "final_efficiency_percent": timeline[-1]["dust"]["end_efficiency_percent"],
            "lost_generation_wh": round(dust_loss, 4),
        },
        "radiation": {
            "model": "synthetic-solar-exposure-scenario", "observed_space_weather": False,
            "units": "dimensionless index, 0..100", "flare_probability": None,
            "initial": timeline[0]["radiation"],
            "peak_index": max(row["radiation"]["index"] for row in timeline),
            "mean_index": round(sum(row["radiation"]["index"] for row in timeline) / MISSION_HOURS, 4),
            "peak_risk_level": max((row["radiation"]["risk_level"] for row in timeline),
                                   key={"LOW": 0, "MODERATE": 1, "HIGH": 2}.get),
        },
        "thermal_shock": {
            "model": "fully-restrained-linear-elastic-screen",
            "material": {
                "name": "illustrative-alloy",
                "young_modulus_gpa": THERMAL_YOUNG_MODULUS_GPA,
                "thermal_expansion_per_k": THERMAL_EXPANSION_PER_K,
                "allowable_stress_mpa": THERMAL_ALLOWABLE_STRESS_MPA,
            },
            "reference_stress_test": {
                "from_temperature_c": -200.0, "to_temperature_c": 120.0,
                "transition_duration_h": 1.0,
                **calculate_thermal_shock(-200.0, 120.0),
            },
            "max_temperature_step_c": max(abs(row["thermal_shock"]["delta_temperature_c"]) for row in timeline),
            "peak_stress_mpa": max(row["thermal_shock"]["constrained_stress_mpa"] for row in timeline),
            "peak_risk_level": max((row["thermal_shock"]["risk_level"] for row in timeline),
                                   key={"LOW": 0, "MODERATE": 1, "HIGH": 2}.get),
            "high_risk_intervals": sum(row["thermal_shock"]["risk_level"] == "HIGH" for row in timeline),
            "shadow_sun_transitions": sum(row["thermal_shock"]["illumination_transition"]
                                          in ("SHADOW_TO_SUN", "SUN_TO_SHADOW") for row in timeline),
        },
        "signal_latency": {
            "model": "synthetic-distance-vacuum-light-time",
            "distance_reference": "Earth/Moon centres, used as a link-distance proxy",
            "speed_of_light_km_s": SPEED_OF_LIGHT_KM_S,
            "distance_period_days": SIGNAL_DISTANCE_PERIOD_DAYS,
            "initial": timeline[0]["signal_latency"],
            "min_one_way_s": min(row["signal_latency"]["one_way_s"] for row in timeline),
            "max_one_way_s": max(row["signal_latency"]["one_way_s"] for row in timeline),
            "min_round_trip_s": min(row["signal_latency"]["round_trip_s"] for row in timeline),
            "max_round_trip_s": max(row["signal_latency"]["round_trip_s"] for row in timeline),
        },
        "forecast": {
            "start": _utc_string(start), "end": _utc_string(end),
            "duration_h": MISSION_HOURS, "step_h": 1,
            "initial_battery_soc_percent": INITIAL_SOC_PERCENT,
            "initial_energy_wh": BATTERY_CAPACITY_WH * INITIAL_SOC_PERCENT / 100,
            "sampling": "Conditions sampled at start; dust attenuation averaged over interval; energy_wh and battery_soc_percent at end.",
            "units": {
                "start": "ISO 8601 UTC", "end": "ISO 8601 UTC", "hour": "h",
                "generation_w": "W", "consumption_w": "W", "net_w": "W",
                "clean_generation_w": "W", "dust_loss_w": "W",
                "dust.*_efficiency_percent": "%", "radiation.index": "dimensionless, 0..100",
                "thermal_shock.delta_temperature_c": "degC",
                "thermal_shock.temperature_rate_c_per_h": "degC/h",
                "thermal_shock.constrained_stress_mpa": "MPa",
                "thermal_shock.allowable_stress_ratio": "dimensionless",
                "thermal_shock.risk_index": "dimensionless, 0..100",
                "signal_latency.distance_km": "km",
                "signal_latency.one_way_s": "s", "signal_latency.round_trip_s": "s",
                "signal_latency.dte_one_way_s": "s", "signal_latency.dte_round_trip_s": "s",
                "systems_w": "W", "heater_w": "W", "temperature_c": "degC",
                "energy_wh": "Wh", "generated_energy_wh": "Wh", "consumed_energy_wh": "Wh",
                "unserved_energy_wh": "Wh", "curtailed_energy_wh": "Wh",
                "battery_soc_percent": "%", "battery_soc_start_percent": "%",
                "insolation_percent": "%", "earth_elevation_deg": "deg",
            },
            "timeline": timeline,
        },
    }


def find_safe_haven(latitude, longitude, timestamp, original):
    """Find the nearest SUCCESS on a bounded 100 m grid within 1 km.

    Each candidate receives the same full 24 h energy/dust/landing assessment
    at the original timestamp. The core simulation never invokes this search,
    so failed candidates cannot trigger recursive scans. This suggests an
    alternate landing site, not a validated driving route or radiation shelter.
    """
    offsets = sorted(
        ((east, north)
         for east in range(-SAFE_HAVEN_RADIUS_M, SAFE_HAVEN_RADIUS_M + 1, SAFE_HAVEN_GRID_STEP_M)
         for north in range(-SAFE_HAVEN_RADIUS_M, SAFE_HAVEN_RADIUS_M + 1, SAFE_HAVEN_GRID_STEP_M)
         if 0 < east ** 2 + north ** 2 <= SAFE_HAVEN_RADIUS_M ** 2),
        key=lambda p: (p[0] ** 2 + p[1] ** 2, p),
    )
    result = {
        "status": "NOT_NEEDED" if original["status"] == "SUCCESS" else "NOT_FOUND",
        "search_radius_m": SAFE_HAVEN_RADIUS_M, "grid_step_m": SAFE_HAVEN_GRID_STEP_M,
        "method": "nearest-successful-grid-point", "candidate_count": len(offsets),
        "scanned_candidates": 0, "evaluated_candidates": 0,
        "route_validated": False, "destination": None,
    }
    if original["status"] == "SUCCESS":
        return result
    for east, north in offsets:
        result["scanned_candidates"] += 1
        lat, lon = _offset_coordinates(latitude, longitude, east, north)
        if not -90 <= lat <= -60:
            continue
        candidate = calculate_mission(lat, lon, timestamp)
        result["evaluated_candidates"] += 1
        if candidate["status"] != "SUCCESS":
            continue
        result["status"] = "FOUND"
        result["destination"] = {
            "latitude": lat, "longitude": lon,
            "distance_m": round(math.hypot(east, north), 4),
            "bearing_deg": round(math.degrees(math.atan2(east, north)) % 360, 4),
            "timestamp": _utc_string(timestamp), "status": candidate["status"],
            "slope_deg": candidate["slope_deg"],
            "safe_radius_estimate_m": candidate["landing_zone"]["safe_radius_estimate_m"],
            "minimum_soc_percent": candidate["power"]["minimum_soc_percent"],
            "final_soc_percent": candidate["power"]["final_soc_percent"],
            "radiation_peak_index": candidate["radiation"]["peak_index"],
        }
        return result
    return result


@csrf_exempt
@require_POST
def mission(request):
    """Validate a landing request and return simulated surface conditions."""
    if request.content_type != "application/json":
        return JsonResponse({"error": "Ожидается application/json"}, status=400)

    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return JsonResponse({"error": "Некорректный JSON"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Ожидается JSON-объект"}, status=400)

    latitude = data.get("latitude")
    if type(latitude) not in (int, float) or not -90 <= latitude <= -60:
        return JsonResponse(
            {"error": "Посадка разрешена только на Южном полюсе Луны"},
            status=400,
        )

    longitude = data.get("longitude")
    if type(longitude) not in (int, float) or not -180 <= longitude <= 180:
        return JsonResponse(
            {"error": "Долгота должна быть числом от -180 до 180"}, status=400
        )

    timestamp = data.get("timestamp")
    try:
        parsed_timestamp = parse_datetime(timestamp) if isinstance(timestamp, str) else None
    except ValueError:
        parsed_timestamp = None
    if parsed_timestamp is None or not is_aware(parsed_timestamp):
        return JsonResponse(
            {"error": "timestamp должен быть датой ISO 8601 с часовым поясом"},
            status=400,
        )

    try:
        result = calculate_mission(latitude, longitude, parsed_timestamp)
        result["safe_haven"] = find_safe_haven(latitude, longitude, parsed_timestamp, result)
    except OverflowError:
        return JsonResponse({"error": "timestamp выходит за допустимый диапазон прогноза"}, status=400)

    return JsonResponse({
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": timestamp,
        **result,
    }, json_dumps_params={"allow_nan": False})
