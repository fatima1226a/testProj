"""Lunar terrain horizon: atan(delta_height/d) - d/(2R), in radians."""

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

from .terrain import RasterTerrain, TerrainError, TerrainPair, coordinates, finite


def destination(lat, lon, azimuth_deg, distance_m, radius_m):
    """Spherical great-circle endpoint: azimuth from true north clockwise."""
    coordinates(lat, lon)
    if finite(distance_m, "distance_m") <= 0 or finite(radius_m, "radius_m") <= 0:
        raise TerrainError("distance and radius must be positive")
    angle = distance_m / radius_m
    phi, lam, az = map(math.radians, (lat, lon, finite(azimuth_deg, "azimuth")))
    phi2 = math.asin(max(-1, min(1, math.sin(phi) * math.cos(angle)
                               + math.cos(phi) * math.sin(angle) * math.cos(az))))
    lam2 = lam + math.atan2(math.sin(az) * math.sin(angle) * math.cos(phi),
                            math.cos(angle) - math.sin(phi) * math.sin(phi2))
    return math.degrees(phi2), (math.degrees(lam2) + 180) % 360 - 180


def apparent_angle(height_m, observer_height_m, distance_m, radius_m):
    for value, name in ((height_m, "height"), (observer_height_m, "observer height"),
                        (distance_m, "distance"), (radius_m, "radius")):
        finite(value, name)
    if distance_m <= 0 or radius_m <= 0:
        raise TerrainError("d=0 excluded; radius must be positive")
    return math.degrees(math.atan((height_m - observer_height_m) / distance_m)
                        - distance_m / (2 * radius_m))


def distances(limit, step):
    values = [i * step for i in range(1, math.floor(limit / step) + 1)]
    if not values or values[-1] < limit:
        values.append(limit)
    return values


def checked_samples(terrain, points):
    values = terrain.sample_many(points)
    if len(values) != len(points):
        raise TerrainError("terrain returned an incomplete ray")
    return [finite(value, "sampled height") for value in values]


def build_horizon(terrain: TerrainPair, lat, lon, *, mast_m=2, azimuth_count=360):
    coordinates(lat, lon)
    if finite(mast_m, "mast_m") <= 0:
        raise TerrainError("mast height must be positive")
    if type(azimuth_count) is not int or azimuth_count < 2:
        raise TerrainError("azimuth_count must be an integer >= 2")
    ground = checked_samples(terrain.near, [(lat, lon)])[0]
    observer_height = ground + mast_m
    horizon = []
    overlap_differences = []
    near_distances = distances(terrain.near_radius_m, terrain.near_step_m)
    far_distances = distances(terrain.far_radius_m, terrain.far_step_m)
    overlap_distances = [d for d in far_distances if d <= terrain.near_radius_m]
    overlap_differences.append(ground - checked_samples(terrain.far, [(lat, lon)])[0])
    for index in range(azimuth_count):
        azimuth = index * 360 / azimuth_count
        maximum = -math.inf
        for source, ray in ((terrain.near, near_distances), (terrain.far, far_distances)):
            points = [destination(lat, lon, azimuth, d, terrain.radius_m) for d in ray]
            heights = checked_samples(source, points)
            maximum = max(maximum, max(apparent_angle(h, observer_height, d, terrain.radius_m)
                                       for h, d in zip(heights, ray)))
        if overlap_distances:
            overlap_points = [destination(lat, lon, azimuth, d, terrain.radius_m)
                              for d in overlap_distances]
            overlap_differences.extend(a - b for a, b in zip(
                checked_samples(terrain.near, overlap_points), checked_samples(terrain.far, overlap_points)))
        horizon.append(maximum)  # Preserve negative horizons; do not clamp to zero.
    report = {
        "status": "passed", "mastM": mast_m, "azimuthCount": azimuth_count,
        "azimuthConvention": "north-clockwise", "units": {"angles": "degrees", "distance": "meters"},
        "radiusM": terrain.radius_m, "groundHeightM": ground,
        "observerHeightM": observer_height,
        "near": {**asdict(terrain.near.info), "radiusM": terrain.near_radius_m,
                 "stepM": terrain.near_step_m, "raySamples": len(near_distances) * azimuth_count},
        "far": {**asdict(terrain.far.info), "radiusM": terrain.far_radius_m,
                "stepM": terrain.far_step_m, "raySamples": len(far_distances) * azimuth_count},
        "overlap": {"count": len(overlap_differences),
                    "meanNearMinusFarM": sum(overlap_differences) / len(overlap_differences),
                    "maxAbsDifferenceM": max(abs(d) for d in overlap_differences),
                    "rmseM": math.sqrt(sum(d * d for d in overlap_differences) / len(overlap_differences))},
        "notes": ["Successful ray sampling is not scientific validation.",
                  "Nearest-pixel sampling; step, extent and azimuth convergence remain to be checked."]}
    return {"horizon": horizon, "report": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--near", type=Path, required=True)
    parser.add_argument("--far", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, help="JSON {near: {...}, far: {...}} from PDS labels")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--far-radius-m", type=float, required=True)
    parser.add_argument("--azimuth-count", type=int, default=360)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    with RasterTerrain(args.near, metadata=metadata.get("near")) as near, \
            RasterTerrain(args.far, metadata=metadata.get("far")) as far:
        result = build_horizon(TerrainPair(near, far, far_radius_m=args.far_radius_m),
                               args.lat, args.lon, azimuth_count=args.azimuth_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"PASS: {len(result['horizon'])} horizon samples written to {args.output}")


if __name__ == "__main__":
    main()
