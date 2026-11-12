import { hasKey, msg, type Msg } from '../../shared/i18n';
import type {
  Failure,
  FailureReason,
  HorizonPoint,
  HourSample,
  Kpi,
  Limits,
  Result,
} from '../result/types';
import type { Assumption, DataSection, RawResponse, Suggestion, SurvivalResult } from './types';

type Rec = Record<string, unknown>;

const rec = (value: unknown): Rec =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Rec) : {};
const arr = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;
const bool = (value: unknown): boolean | null => (typeof value === 'boolean' ? value : null);
const text = (value: unknown): string | null => (typeof value === 'string' ? value : null);

const round = (value: unknown, digits = 2): number | null => {
  const n = num(value);
  return n === null ? null : Number(n.toFixed(digits));
};

function compact(source: Rec): Rec {
  return Object.fromEntries(Object.entries(source).filter(([, v]) => v !== null && v !== undefined));
}

const coded = (prefix: 'risk' | 'haven', value: unknown): Msg | string | null => {
  const key = text(value);
  if (!key) return null;
  const full = `${prefix}.${key}`;
  return hasKey(full) ? msg(full) : key;
};

const risk = (value: unknown) => coded('risk', value);

function reasons(raw: Rec): Assumption[] {
  const landing = rec(raw.landing_zone);
  const power = rec(raw.power);
  const limits = rec(raw.assumptions);
  const slope = num(raw.slope_deg);
  const slopeLimit = num(limits.max_slope_deg);
  const socLimit = num(limits.min_soc_percent);
  const total = num(limits.duration_h) ?? 24;
  const minSoc = num(power.minimum_soc_percent);
  const failures = arr(raw.failure_reasons).filter((r): r is string => typeof r === 'string');
  const failed = new Set(failures);
  const items: Assumption[] = [];

  for (const code of failures) {
    switch (code) {
      case 'UNSAFE_SLOPE':
        items.push({
          title: msg('reason.slope'),
          text:
            slopeLimit === null
              ? msg('reason.slopeBare', { slope })
              : msg('reason.slopeFailLimit', { slope, limit: slopeLimit }),
        });
        break;
      case 'UNSAFE_LANDING_ZONE':
        items.push({
          title: msg('reason.zone'),
          text: msg('reason.zoneText', {
            radius: num(landing.assessed_radius_m),
            unsafe: num(landing.unsafe_sample_count),
            total: num(landing.sample_count),
          }),
        });
        break;
      case 'LOW_BATTERY':
        items.push({
          title: msg('reason.battery'),
          text:
            socLimit === null
              ? msg('reason.batteryFailBare', { min: minSoc })
              : msg('reason.batteryFailLimit', { min: minSoc, limit: socLimit }),
        });
        break;
      case 'POWER_SHORTFALL':
        items.push({
          title: msg('reason.energy'),
          text: msg('reason.energyText', { wh: num(power.unserved_energy_wh) }),
        });
        break;
      default:
        items.push({ title: null, text: code });
    }
  }

  if (!failed.has('UNSAFE_SLOPE')) {
    items.push({
      title: msg('reason.slope'),
      text:
        slopeLimit === null
          ? msg('reason.slopeBare', { slope })
          : msg('reason.slopeOkLimit', { slope, limit: slopeLimit }),
    });
  }
  const summary = rec(raw.summary);
  items.push({
    title: msg('reason.light'),
    text: msg('reason.lightText', {
      sunlit: num(summary.sunlit_hours),
      total,
      shadow: num(summary.longest_shadow_h),
    }),
  });
  if (!failed.has('LOW_BATTERY')) {
    items.push({
      title: msg('reason.battery'),
      text:
        socLimit === null
          ? msg('reason.batteryOkBare', { min: minSoc })
          : msg('reason.batteryOkLimit', { min: minSoc, limit: socLimit }),
    });
  }
  items.push({
    title: msg('reason.temp'),
    text: msg('reason.tempText', {
      min: num(summary.min_temperature_c),
      max: num(summary.max_temperature_c),
    }),
  });
  const dte = rec(raw.dte);
  if (num(dte.available_hours) !== null) {
    items.push({
      title: msg('reason.comms'),
      text: msg('reason.commsText', { hours: num(dte.available_hours), total }),
    });
  }
  return items;
}

function sections(raw: Rec): DataSection[] {
  const landing = rec(raw.landing_zone);
  const summary = rec(raw.summary);
  const power = rec(raw.power);
  const dust = rec(raw.dust);
  const limits = rec(raw.assumptions);
  const thermal = rec(raw.thermal_shock);
  const radiation = rec(raw.radiation);
  const dte = rec(raw.dte);
  const signal = rec(raw.signal_latency);
  const haven = rec(raw.safe_haven);
  const destination = rec(haven.destination);
  const slope = num(raw.slope_deg);
  const slopeLimit = num(limits.max_slope_deg);

  const points = arr(rec(raw.forecast).timeline).flatMap((row) => {
    const r = rec(row);
    const hour = num(r.hour);
    const soc = round(r.battery_soc_percent, 1);
    const temp = round(r.temperature_c, 1);
    const sun = round(r.insolation_percent, 1);
    const gen = round(r.generation_w, 1);
    return hour === null || soc === null || temp === null || sun === null || gen === null
      ? []
      : [{ hour, soc_pct: soc, temp_c: temp, insolation_pct: sun, generation_w: gen }];
  });

  const list: DataSection[] = [
    {
      id: 'coordinates',
      title: msg('sec.coordinates'),
      data: compact({
        valid: true,
        region: msg('val.region'),
        latitude: round(raw.latitude, 4),
        longitude: round(raw.longitude, 4),
        elevation_m: round(raw.elevation_m, 1),
      }),
    },
    {
      id: 'slope',
      title: msg('sec.slope'),
      data: compact({
        slope_deg: round(slope, 2),
        limit_deg: slopeLimit,
        passable: slope !== null && slopeLimit !== null ? slope <= slopeLimit : null,
        landing_radius_m: num(landing.assessed_radius_m),
        safe_radius_m: num(landing.safe_radius_estimate_m),
        zone_safe: bool(landing.is_safe),
        samples: num(landing.sample_count),
        unsafe_samples: num(landing.unsafe_sample_count),
        min_deg: round(landing.min_slope_deg),
        mean_deg: round(landing.mean_slope_deg),
        max_deg: round(landing.max_slope_deg),
        elevation_range_m: round(landing.elevation_range_m, 1),
      }),
    },
    {
      id: 'illumination',
      title: msg('sec.illumination'),
      data: compact({
        sun_elevation_deg: round(raw.sun_elevation_deg),
        insolation_pct: round(raw.insolation_percent),
        shadowed: bool(raw.is_shadowed),
        sunlit_hours: num(summary.sunlit_hours),
        shadow_hours: num(summary.shadow_hours),
        longest_shadow_h: num(summary.longest_shadow_h),
      }),
    },
    {
      id: 'thermal',
      title: msg('sec.thermal'),
      data: compact({
        temp_c: round(raw.temperature_c, 1),
        min_c: round(summary.min_temperature_c, 1),
        max_c: round(summary.max_temperature_c, 1),
        max_step_c: round(thermal.max_temperature_step_c, 1),
        peak_stress_mpa: round(thermal.peak_stress_mpa, 1),
        peak_risk: risk(thermal.peak_risk_level),
        high_risk_intervals: num(thermal.high_risk_intervals),
      }),
    },
    {
      id: 'battery',
      title: msg('sec.battery'),
      data: compact({
        min_soc_pct: round(power.minimum_soc_percent, 1),
        final_soc_pct: round(power.final_soc_percent, 1),
        generated_wh: round(power.generated_energy_wh, 1),
        consumed_wh: round(power.consumed_energy_wh, 1),
        unserved_wh: round(power.unserved_energy_wh, 1),
        curtailed_wh: round(power.curtailed_energy_wh, 1),
      }),
    },
    {
      id: 'timeline',
      title: msg('sec.timeline'),
      data: points.length > 0 ? { step_h: num(limits.step_h) ?? 1, points } : {},
    },
    {
      id: 'regolith',
      title: msg('sec.regolith'),
      data: compact({
        initial_efficiency_pct: round(dust.initial_efficiency_percent, 1),
        final_efficiency_pct: round(dust.final_efficiency_percent, 1),
        lost_generation_wh: round(dust.lost_generation_wh, 1),
      }),
    },
    {
      id: 'safeHaven',
      title: msg('sec.haven'),
      data: compact({
        status: coded('haven', haven.status),
        search_radius_m: num(haven.search_radius_m),
        candidates: num(haven.evaluated_candidates),
        latitude: round(destination.latitude, 4),
        longitude: round(destination.longitude, 4),
        distance_m: round(destination.distance_m, 0),
        bearing_deg: round(destination.bearing_deg, 0),
      }),
    },
    {
      id: 'config',
      title: msg('sec.config'),
      data: compact({
        duration_h: num(limits.duration_h),
        step_h: num(limits.step_h),
        panel_power_w: num(limits.panel_power_w),
        systems_w: num(limits.systems_w),
        heater_w: num(limits.shadow_heater_w),
        capacity_wh: num(limits.battery_capacity_wh),
        initial_soc_pct: num(limits.initial_soc_percent),
        min_allowed_soc_pct: num(limits.min_soc_percent),
        max_slope_deg: slopeLimit,
      }),
    },
    {
      id: 'other',
      title: msg('sec.transit'),
      data: compact(
        Object.fromEntries(
          Object.entries(rec(raw.transit)).filter(([, v]) => ['number', 'string', 'boolean'].includes(typeof v)),
        ),
      ),
    },
    {
      id: 'other',
      title: msg('sec.radiation'),
      data: compact({
        peak_index: round(radiation.peak_index, 1),
        mean_index: round(radiation.mean_index, 1),
        peak_risk: risk(radiation.peak_risk_level),
      }),
    },
    {
      id: 'other',
      title: msg('sec.comms'),
      data: compact({
        visible_at_start: bool(dte.visible_at_start),
        available_hours: num(dte.available_hours),
        windows: arr(dte.windows).length || null,
        min_one_way_s: round(signal.min_one_way_s, 3),
        max_one_way_s: round(signal.max_one_way_s, 3),
      }),
    },
  ];
  return list.filter((section) => Object.keys(rec(section.data)).length > 0);
}

const pick = (source: Rec, keys: string[]): unknown => {
  for (const key of keys) if (source[key] !== undefined && source[key] !== null) return source[key];
  return undefined;
};

const SUN_AZ = ['sun_azimuth_deg', 'solar_azimuth_deg', 'sun_az_deg'];
const SUN_EL = ['sun_elevation_deg', 'solar_elevation_deg', 'sun_el_deg'];
const EARTH_AZ = ['earth_azimuth_deg', 'earth_az_deg'];
const EARTH_EL = ['earth_elevation_deg', 'earth_el_deg'];
const EARTH_FLAG = ['earth_visible', 'dte_visible', 'earth_in_view', 'dte_available', 'is_earth_visible'];
const ROW_TIME = ['timestamp', 'time', 'utc', 'datetime'];
const HORIZON_KEYS = ['horizon_profile', 'horizon', 'horizon_mask'];

const angleOf = (row: Rec, flat: string[], body: 'sun' | 'earth', nested: string[]): number | null =>
  num(pick(row, flat)) ?? num(pick(rec(row[body]), nested));

const BATTERY_CODES = new Set(['LOW_BATTERY', 'POWER_SHORTFALL']);
const TERRAIN_CODES = new Set(['UNSAFE_SLOPE', 'UNSAFE_LANDING_ZONE']);

function limitsOf(raw: Rec): Limits {
  const a = rec(raw.assumptions);
  return {
    durationH: num(a.duration_h),
    stepH: num(a.step_h),
    minSocPct: num(a.min_soc_percent),
    initialSocPct: num(a.initial_soc_percent),
    capacityWh: num(a.battery_capacity_wh),
    panelW: num(a.panel_power_w),
    systemsW: num(a.systems_w),
    heaterW: num(a.shadow_heater_w),
    maxSlopeDeg: num(a.max_slope_deg),
  };
}

type Window = [from: number, to: number];

function toMs(value: unknown, landingMs: number | null): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return landingMs === null ? null : landingMs + value * 3_600_000;
  }
  if (typeof value === 'string') {
    const t = Date.parse(value);
    return Number.isFinite(t) ? t : null;
  }
  return null;
}

function windowsOf(dte: Rec, landingMs: number | null): Window[] {
  const out: Window[] = [];
  for (const item of arr(dte.windows)) {
    const w = rec(item);
    const from = toMs(pick(w, ['start', 'start_time', 'start_hour', 'start_h', 'from', 'begin']), landingMs);
    const to = toMs(pick(w, ['end', 'end_time', 'end_hour', 'end_h', 'to', 'finish']), landingMs);
    if (from !== null && to !== null) out.push([from, to]);
  }
  return out;
}

const HORIZON_AZ = ['azimuth_deg', 'azimuths_deg', 'az_deg', 'azimuth', 'azimuths', 'az'];
const HORIZON_EL = [
  'elevation_deg',
  'elevations_deg',
  'horizon_elevation_deg',
  'el_deg',
  'elevation',
  'elevations',
  'height_deg',
  'el',
];
const HORIZON_LISTS = ['points', 'profile', 'samples', 'data', 'mask', 'values', 'skyline'];
const HORIZON_NAMES = [...HORIZON_KEYS, 'horizon_elevation_profile', 'terrain_horizon', 'skyline'];

const wrapAz = (az: number): number => ((az % 360) + 360) % 360;

function pointsFromList(list: unknown[]): HorizonPoint[] {
  const points: HorizonPoint[] = [];
  list.forEach((item, i) => {
    const el = num(item);
    if (el !== null) {
      points.push({ azDeg: (i * 360) / list.length, elDeg: el });
      return;
    }
    if (Array.isArray(item)) {
      const az = num(item[0]);
      const e = num(item[1]);
      if (az !== null && e !== null) points.push({ azDeg: wrapAz(az), elDeg: e });
      return;
    }
    const r = rec(item);
    const az = num(pick(r, HORIZON_AZ));
    const e = num(pick(r, HORIZON_EL));
    if (az !== null && e !== null) points.push({ azDeg: wrapAz(az), elDeg: e });
  });
  return points;
}

function horizonFrom(source: unknown): HorizonPoint[] {
  if (Array.isArray(source)) return pointsFromList(source);
  const r = rec(source);
  const azs = pick(r, HORIZON_AZ);
  const els = pick(r, HORIZON_EL);
  if (Array.isArray(azs) && Array.isArray(els)) {
    const points: HorizonPoint[] = [];
    els.forEach((value, i) => {
      const az = num(azs[i]);
      const e = num(value);
      if (az !== null && e !== null) points.push({ azDeg: wrapAz(az), elDeg: e });
    });
    return points;
  }
  if (Array.isArray(els)) return pointsFromList(els);
  for (const key of HORIZON_LISTS) {
    if (Array.isArray(r[key])) return pointsFromList(r[key] as unknown[]);
  }
  return Object.entries(r).flatMap(([key, value]) => {
    const az = Number(key);
    const e = num(value);
    return key.trim() !== '' && Number.isFinite(az) && e !== null ? [{ azDeg: wrapAz(az), elDeg: e }] : [];
  });
}

function findHorizonSource(node: unknown, depth = 0): unknown {
  if (depth > 3 || typeof node !== 'object' || node === null || Array.isArray(node)) return undefined;
  const r = rec(node);
  for (const [key, value] of Object.entries(r)) {
    if (/horizon|skyline/i.test(key) && value !== null && typeof value === 'object') return value;
  }
  for (const value of Object.values(r)) {
    const found = findHorizonSource(value, depth + 1);
    if (found !== undefined) return found;
  }
  return undefined;
}

function horizonOf(raw: Rec): HorizonPoint[] {
  const containers = [raw, rec(raw.terrain), rec(raw.landing_zone), rec(raw.site), rec(raw.forecast)];
  let source: unknown;
  for (const container of containers) {
    source = pick(container, HORIZON_NAMES);
    if (source !== undefined && horizonFrom(source).length > 0) break;
    source = undefined;
  }
  source ??= findHorizonSource(raw);
  const byAz = new Map<number, HorizonPoint>();
  for (const point of horizonFrom(source)) byAz.set(point.azDeg, point);
  return [...byAz.values()].sort((a, b) => a.azDeg - b.azDeg);
}

function failureOf(
  status: string,
  codes: string[],
  batteryPct: number[],
  minSoc: number | null,
): { failure: Failure | null; reason: FailureReason | null } {
  if (status !== 'FAIL') return { failure: null, reason: null };
  const reason: FailureReason = codes.some((c) => BATTERY_CODES.has(c))
    ? 'battery'
    : codes.some((c) => TERRAIN_CODES.has(c))
      ? 'terrain'
      : 'other';
  let hour = 0;
  if (reason === 'battery' && minSoc !== null) {
    const found = batteryPct.findIndex((v) => v < minSoc);
    hour = found < 0 ? 0 : found;
  }
  return { failure: { hour, reason, codes }, reason };
}

export function buildSim(body: Rec, status: string, landingIso: string | null): {
  sim: Result | null;
  reason: FailureReason | null;
  marginPct: number | null;
} {
  const limits = limitsOf(body);
  const summary = rec(body.summary);
  const power = rec(body.power);
  const dte = rec(body.dte);
  const codes = arr(body.failure_reasons).filter((r): r is string => typeof r === 'string');
  const landingMs = landingIso && Number.isFinite(Date.parse(landingIso)) ? Date.parse(landingIso) : null;
  const windows = windowsOf(dte, landingMs);
  const availableH = num(dte.available_hours);

  const rows = arr(rec(body.forecast).timeline)
    .map(rec)
    .filter((r) => num(r.battery_soc_percent) !== null);

  const batteryPct = rows.map((r) => num(r.battery_soc_percent) as number);
  const minSoc = num(power.minimum_soc_percent) ?? (batteryPct.length > 0 ? Math.min(...batteryPct) : null);
  const marginPct = minSoc !== null && limits.minSocPct !== null ? minSoc - limits.minSocPct : null;
  const { failure, reason } = failureOf(status, codes, batteryPct, limits.minSocPct);

  if (rows.length === 0) return { sim: null, reason, marginPct };

  const hours: HourSample[] = rows.map((r, i) => {
    const insolation = num(r.insolation_percent);
    const generation = num(r.generation_w);
    const sunEl = angleOf(r, SUN_EL, 'sun', HORIZON_EL);
    const shadowed = bool(r.is_shadowed);
    const sun =
      shadowed !== null
        ? !shadowed
        : insolation !== null
          ? insolation > 0
          : generation !== null
            ? generation > 0
            : sunEl !== null && sunEl > 0;

    const flag = EARTH_FLAG.map((k) => bool(r[k])).find((v) => v !== null) ?? null;
    let earth: boolean | null = flag;
    if (earth === null) {
      const hour = num(r.hour) ?? i;
      const rowTime = toMs(pick(r, ROW_TIME), landingMs) ?? (landingMs === null ? null : landingMs + hour * 3_600_000);
      if (windows.length > 0 && rowTime !== null) earth = windows.some(([a, b]) => rowTime >= a && rowTime <= b);
      else if (availableH === 0) earth = false;
      else if (availableH !== null && limits.durationH !== null && availableH >= limits.durationH) earth = true;
    }
    return {
      sun,
      earth,
      sunAzDeg: angleOf(r, SUN_AZ, 'sun', HORIZON_AZ),
      sunElDeg: sunEl,
      earthAzDeg: angleOf(r, EARTH_AZ, 'earth', HORIZON_AZ),
      earthElDeg: angleOf(r, EARTH_EL, 'earth', HORIZON_EL),
      temperatureC: num(r.temperature_c),
      generationW: generation,
      insolationPct: insolation,
    };
  });

  const duration = limits.durationH ?? Math.max(1, hours.length - 1);
  const sunlitH = num(summary.sunlit_hours);
  const kpi: Kpi = {
    minBatteryPct: minSoc,
    longestShadowH: num(summary.longest_shadow_h),
    earthHours: availableH,
    sunlitPct: sunlitH === null ? null : (sunlitH / duration) * 100,
  };

  return {
    sim: { hours, batteryPct, failure, kpi, limits, horizon: horizonOf(body) },
    reason,
    marginPct,
  };
}

export interface MissionAnswer {
  result: SurvivalResult;
  destination: Suggestion | null;
}

function lunarView(raw: Rec): Rec {
  return { ...raw, ...rec(raw.surface) };
}

export function parseMission(raw: RawResponse, landingIso: string | null = null): MissionAnswer {
  const body = lunarView(raw as Rec);
  const destination = rec(rec(body.safe_haven).destination);
  const latitude = num(destination.latitude);
  const longitude = num(destination.longitude);
  const { sim, reason, marginPct } = buildSim(body, raw.status, landingIso);
  return {
    result: {
      survives: raw.status === 'SUCCESS',
      assumptions: reasons(body),
      sections: sections(body),
      sim,
      reason,
      marginPct,
    },
    destination: latitude !== null && longitude !== null ? { latitude, longitude } : null,
  };
}
