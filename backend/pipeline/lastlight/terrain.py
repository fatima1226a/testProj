"""Strict lunar DEM sampling. No missing value is replaced by zero.

Raster dependencies are imported only when opening a real raster; analytic
terrain used by the model tests has no third-party dependencies.
"""

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
from typing import Protocol, Sequence


class TerrainError(ValueError):
    pass


def finite(value, name):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise TerrainError(f"{name} must be finite")
    return float(value)


def coordinates(lat, lon):
    finite(lat, "latitude")
    finite(lon, "longitude")
    if not -90 < lat < 90 or not -180 <= lon <= 180:
        raise TerrainError("expected latitude (-90,90), east-positive longitude [-180,180]")


@dataclass(frozen=True)
class TerrainInfo:
    source: str
    resolution_m: float
    radius_m: float
    height_datum: str
    body_frame: str
    crs: str
    sha256: str | None = None

    def __post_init__(self):
        if finite(self.resolution_m, "resolution_m") <= 0 or finite(self.radius_m, "radius_m") <= 0:
            raise TerrainError("resolution and radius must be positive")
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.source, self.height_datum, self.body_frame, self.crs)):
            raise TerrainError("source, CRS, height datum and body frame must be explicit")


class Terrain(Protocol):
    info: TerrainInfo

    def sample_many(self, points: Sequence[tuple[float, float]]) -> list[float]:
        """Input (latitude, longitude), output elevation in meters."""
        ...


class RasterTerrain:
    """Nearest-pixel sampling in the CRS read from the raster metadata.

Vertical datum and lunar body frame must be in tags or explicitly transcribed
from the accompanying PDS label. We do not infer them from a filename.
"""

    def __init__(self, path, *, metadata=None):
        try:
            import importlib
            rasterio = importlib.import_module("rasterio")
            pyproj = importlib.import_module("pyproj")
            CRS, Transformer = pyproj.CRS, pyproj.Transformer
        except ImportError as error:
            raise TerrainError("Install numpy, rasterio and pyproj from pipeline/requirements.txt") from error
        self.path = Path(path)
        self.dataset = rasterio.open(self.path)
        try:
            src = self.dataset
            if src.crs is None or src.count != 1:
                raise TerrainError("DEM requires an explicit CRS and one elevation band")
            crs = CRS.from_wkt(src.crs.to_wkt())
            if not crs.is_projected or any(abs(axis.unit_conversion_factor - 1) > 1e-12 for axis in crs.axis_info):
                raise TerrainError("DEM horizontal CRS must be projected in meters")
            a, b = crs.ellipsoid.semi_major_metre, crs.ellipsoid.semi_minor_metre
            if not math.isfinite(a) or abs(a - b) > 1e-3 or not 1_700_000 < a < 1_800_000:
                raise TerrainError("this implementation requires a spherical lunar CRS")
            if abs(src.res[0] - src.res[1]) > 1e-6:
                raise TerrainError("DEM must have square pixels")
            tags = {**src.tags(), **src.tags(1)}
            supplied = metadata or {}
            for key, tag in (("height_datum", "HEIGHT_DATUM"), ("body_frame", "BODY_FRAME")):
                if supplied.get(key) and tags.get(tag) and supplied[key] != tags[tag]:
                    raise TerrainError(f"metadata conflicts with raster {tag}")
            if supplied and not supplied.get("metadata_source"):
                raise TerrainError("external metadata requires metadata_source (PDS label/reference)")
            unit = src.units[0] or tags.get("VERTICAL_UNIT") or supplied.get("vertical_unit")
            units = {"m": 1, "meter": 1, "meters": 1, "metre": 1, "metres": 1, "km": 1000}
            if unit is None or str(unit).lower() not in units:
                raise TerrainError("DEM vertical unit is unknown or unsupported")
            self.unit_factor = units[str(unit).lower()]
            self.scale, self.offset = float(src.scales[0]), float(src.offsets[0])
            if not math.isfinite(self.scale) or self.scale <= 0 or not math.isfinite(self.offset):
                raise TerrainError("invalid raster scale or offset")
            self.transformer = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
            digest = sha256()
            with self.path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            self.info = TerrainInfo(str(self.path), float(src.res[0]), a,
                                    tags.get("HEIGHT_DATUM") or supplied.get("height_datum", ""),
                                    tags.get("BODY_FRAME") or supplied.get("body_frame", ""),
                                    crs.to_wkt(), digest.hexdigest())
            self.metadata_source = supplied.get("metadata_source", "GeoTIFF tags")
        except Exception:
            self.dataset.close()
            raise

    def sample_many(self, points):
        xy = []
        for lat, lon in points:
            coordinates(lat, lon)
            try:
                x, y = self.transformer.transform(lon, lat, errcheck=True)
            except Exception as error:
                raise TerrainError(f"cannot project point {lat},{lon}") from error
            row, col = self.dataset.index(x, y)
            if not 0 <= row < self.dataset.height or not 0 <= col < self.dataset.width:
                raise TerrainError(f"DEM coverage gap at {lat},{lon}: {self.path}")
            xy.append((x, y))
        result = []
        for point, sample in zip(points, self.dataset.sample(xy, indexes=1, masked=True)):
            if sample.mask[0]:
                raise TerrainError(f"DEM nodata at {point}: {self.path}")
            value = (float(sample[0]) * self.scale + self.offset) * self.unit_factor
            if not math.isfinite(value):
                raise TerrainError(f"non-finite DEM height at {point}")
            result.append(value)
        return result

    def close(self):
        self.dataset.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@dataclass(frozen=True)
class TerrainPair:
    near: Terrain
    far: Terrain
    near_radius_m: float = 8000  # Inscribed circle of a centered 16x16 km tile.
    far_radius_m: float = 100000  # Explicit approximation; convergence needs validation.
    near_step_m: float = 5
    far_step_m: float = 240

    def __post_init__(self):
        for name in ("near_radius_m", "far_radius_m", "near_step_m", "far_step_m"):
            if finite(getattr(self, name), name) <= 0:
                raise TerrainError(f"{name} must be positive")
        if self.near_radius_m > 8000 or self.far_radius_m <= self.near_radius_m:
            raise TerrainError("near radius must be <= 8 km; far radius must exceed near radius")
        if abs(self.near.info.resolution_m - 5) > .01 or abs(self.far.info.resolution_m - 240) > .1:
            raise TerrainError("expected 5 m near DEM and 240 m far DEM")
        if self.near_step_m > 5 or self.far_step_m > 240:
            raise TerrainError("ray step must not exceed DEM resolution")
        if self.near_radius_m < self.near_step_m or self.far_radius_m < self.far_step_m:
            raise TerrainError("each ray must contain at least one sample")
        for name in ("height_datum", "body_frame", "radius_m"):
            if getattr(self.near.info, name) != getattr(self.far.info, name):
                raise TerrainError(f"near/far {name} mismatch; convert explicitly before sampling")

    @property
    def radius_m(self):
        return self.near.info.radius_m
