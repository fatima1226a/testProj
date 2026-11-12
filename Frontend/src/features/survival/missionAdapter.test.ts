import { expect, test } from 'vitest';
import { msg, tm } from '../../shared/i18n';
import { parseMission } from './missionAdapter';

const failing = {
  status: 'FAIL' as const,
  failure_reasons: ['LOW_BATTERY'],
  latitude: -89.45,
  longitude: -136.5,
  slope_deg: 4.01,
  assumptions: { max_slope_deg: 15, min_soc_percent: 20, duration_h: 24, step_h: 1 },
  power: { minimum_soc_percent: 4, final_soc_percent: 4 },
  summary: { sunlit_hours: 0, shadow_hours: 24, longest_shadow_h: 24 },
  safe_haven: {
    status: 'FOUND',
    destination: { latitude: -89.4269, longitude: -137.1594, distance_m: 728 },
  },
};

test('FAIL: not survived, the reason comes first, safe haven gives a destination', () => {
  const { result, destination } = parseMission(failing);
  expect(result.survives).toBe(false);
  expect(result.assumptions[0]).toEqual({
    title: msg('reason.battery'),
    text: msg('reason.batteryFailLimit', { min: 4, limit: 20 }),
  });
  expect(tm(result.assumptions[0]?.title)).toBe('Батарея');
  expect(tm(result.assumptions[0]?.text)).toBe('Заряд опускается до 4,0 % при пороге 20 %.');
  expect(destination).toEqual({ latitude: -89.4269, longitude: -137.1594 });
});

test('SUCCESS: survives, no destination, subsystems are in the screen order', () => {
  const { result, destination } = parseMission({
    ...failing,
    status: 'SUCCESS',
    failure_reasons: [],
    safe_haven: { status: 'NOT_NEEDED', destination: null },
  });
  expect(result.survives).toBe(true);
  expect(destination).toBeNull();
  const ids = result.sections.map((section) => section.id);
  expect(ids.indexOf('coordinates')).toBeLessThan(ids.indexOf('slope'));
  expect(ids.indexOf('slope')).toBeLessThan(ids.indexOf('safeHaven'));
});

test('a response with only a status does not break the parser', () => {
  const { result, destination } = parseMission({ status: 'SUCCESS' });
  expect(result.survives).toBe(true);
  expect(result.sections).toEqual([]);
  expect(destination).toBeNull();
});

test('lunar results are read from surface, not from the top level', () => {
  const { result } = parseMission({
    status: 'FAIL',
    power: { minimum_soc_percent: 90 },
    surface: {
      failure_reasons: ['LOW_BATTERY'],
      power: { minimum_soc_percent: 4 },
      assumptions: { min_soc_percent: 20 },
    },
  });
  expect(result.survives).toBe(false);
  expect(tm(result.assumptions[0]?.text)).toBe('Заряд опускается до 4,0 % при пороге 20 %.');
});

const timeline = [
  { hour: 0, battery_soc_percent: 90, temperature_c: -20, insolation_percent: 40, generation_w: 70 },
  { hour: 1, battery_soc_percent: 60, temperature_c: -90, insolation_percent: 0, generation_w: 0 },
  { hour: 2, battery_soc_percent: 15, temperature_c: -120, insolation_percent: 0, generation_w: 0 },
];

test('the whole screen is built from the server timeline, nothing is invented', () => {
  const { result } = parseMission(
    {
      status: 'FAIL',
      surface: {
        failure_reasons: ['LOW_BATTERY'],
        assumptions: { min_soc_percent: 20, duration_h: 2, battery_capacity_wh: 2400, systems_w: 75 },
        power: { minimum_soc_percent: 15 },
        summary: { sunlit_hours: 1, longest_shadow_h: 2 },
        dte: { available_hours: 1 },
        forecast: { timeline },
      },
    },
    '2026-11-18T00:00:00Z',
  );
  const sim = result.sim;
  expect(sim?.batteryPct).toEqual([90, 60, 15]);
  expect(sim?.hours.map((h) => h.sun)).toEqual([true, false, false]);
  expect(sim?.hours[0]?.sunAzDeg).toBeNull();
  expect(sim?.failure).toEqual({ hour: 2, reason: 'battery', codes: ['LOW_BATTERY'] });
  expect(sim?.kpi).toEqual({ minBatteryPct: 15, longestShadowH: 2, earthHours: 1, sunlitPct: 50 });
  expect(sim?.horizon).toEqual([]);
  expect(result.reason).toBe('battery');
  expect(result.marginPct).toBe(-5);
});

test('earth visibility is read from the dte windows', () => {
  const { result } = parseMission(
    {
      status: 'SUCCESS',
      surface: {
        dte: { available_hours: 1, windows: [{ start: '2026-11-18T00:00:00Z', end: '2026-11-18T01:00:00Z' }] },
        forecast: { timeline },
      },
    },
    '2026-11-18T00:00:00Z',
  );
  expect(result.sim?.hours.map((h) => h.earth)).toEqual([true, true, false]);
});

test('without a timeline there is no scale', () => {
  expect(parseMission({ status: 'SUCCESS' }).result.sim).toBeNull();
});

const row = { hour: 0, battery_soc_percent: 90, temperature_c: -20, insolation_percent: 40, generation_w: 70 };
const withHorizon = (horizon: Record<string, unknown>) =>
  parseMission({ status: 'SUCCESS', surface: { forecast: { timeline: [row] }, ...horizon } }).result.sim?.horizon;

test('the horizon profile is read from any shape the server may use', () => {
  const expected = [
    { azDeg: 0, elDeg: 1 },
    { azDeg: 90, elDeg: 2 },
  ];
  expect(withHorizon({ horizon_profile: [{ azimuth_deg: 0, elevation_deg: 1 }, { azimuth_deg: 90, elevation_deg: 2 }] })).toEqual(expected);
  expect(withHorizon({ horizon: { points: [[0, 1], [90, 2]] } })).toEqual(expected);
  expect(withHorizon({ horizon_profile: { azimuth_deg: [0, 90], elevation_deg: [1, 2] } })).toEqual(expected);
  expect(withHorizon({ terrain: { horizon_profile: { '0': 1, '90': 2 } } })).toEqual(expected);
  expect(withHorizon({ landing_zone: { horizon_mask_deg: { profile: [{ az: 0, el: 1 }, { az: 90, el: 2 }] } } })).toEqual(expected);
  expect(withHorizon({ horizon_profile: [1, 2, 3, 4] })?.map((p) => p.azDeg)).toEqual([0, 90, 180, 270]);
  expect(withHorizon({})).toEqual([]);
});

test('sun and earth angles may be nested in the timeline row', () => {
  const { result } = parseMission({
    status: 'SUCCESS',
    surface: { forecast: { timeline: [{ ...row, sun: { azimuth_deg: 120, elevation_deg: 3.5 }, earth_azimuth_deg: 10, earth_elevation_deg: 2 }] } },
  });
  expect(result.sim?.hours[0]).toMatchObject({ sunAzDeg: 120, sunElDeg: 3.5, earthAzDeg: 10, earthElDeg: 2 });
});
