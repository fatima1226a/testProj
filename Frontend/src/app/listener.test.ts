import { expect, test } from 'vitest';
import { planPatched, selectPlanRevision } from '../features/plan/planSlice';
import { calendarReceived, resultReceived, selectCalendar, selectResult } from '../features/result/resultSlice';
import type { Result } from '../features/result/types';
import {
  hourSelected,
  playTicked,
  playToggled,
  selectPlaying,
  selectSelectedHour,
} from '../features/timeline/viewSlice';
import { makeStore } from './store';

const sample = {
  sun: true,
  earth: true,
  sunAzDeg: null,
  sunElDeg: null,
  earthAzDeg: null,
  earthElDeg: null,
  temperatureC: null,
  generationW: null,
  insolationPct: null,
};

const result24: Result = {
  hours: Array.from({ length: 25 }, () => sample),
  batteryPct: Array.from({ length: 25 }, () => 80),
  failure: null,
  kpi: { minBatteryPct: 80, longestShadowH: 0, earthHours: 24, sunlitPct: 100 },
  limits: {
    durationH: 24,
    stepH: 1,
    minSocPct: 20,
    initialSocPct: 90,
    capacityWh: 2400,
    panelW: 180,
    systemsW: 75,
    heaterW: 0,
    maxSlopeDeg: 15,
  },
  horizon: [],
};

test('nothing is shown until the server answers', () => {
  const store = makeStore();
  expect(selectResult(store.getState())).toBeNull();
  expect(selectCalendar(store.getState())).toHaveLength(0);
});

test('plan change bumps revision and stops play; a new start resets the cursor', () => {
  const store = makeStore();
  store.dispatch(hourSelected(5));
  store.dispatch(playToggled(24));
  store.dispatch(planPatched({ coord: { latDeg: -88, lonDeg: 10 } }));
  expect(selectPlanRevision(store.getState())).toBe(1);
  expect(selectPlaying(store.getState())).toBe(false);

  store.dispatch(planPatched({ start: '2026-11-15T00:00:00Z' }));
  expect(selectSelectedHour(store.getState())).toBe(0);
});

test('server answer is kept only for the current plan revision', () => {
  const store = makeStore();
  store.dispatch(resultReceived({ revision: 0, result: result24 }));
  expect(selectResult(store.getState())).toBe(result24);

  store.dispatch(planPatched({ coord: { latDeg: -88, lonDeg: 10 } }));
  expect(selectResult(store.getState())).toBeNull();

  store.dispatch(resultReceived({ revision: 1, result: result24 }));
  store.dispatch(resultReceived({ revision: 0, result: null }));
  expect(selectResult(store.getState())).toBe(result24);
});

test('calendar is tied to the plan revision', () => {
  const store = makeStore();
  const cell = { landing: '2026-11-01T00:00:00Z', status: 'ok' as const, marginPct: 12 };
  store.dispatch(calendarReceived({ revision: 0, calendar: [cell] }));
  expect(selectCalendar(store.getState())).toEqual([cell]);
  store.dispatch(planPatched({ coord: { latDeg: -88, lonDeg: 10 } }));
  expect(selectCalendar(store.getState())).toHaveLength(0);
});

test('the cursor and play stop at the last hour of the server calculation', () => {
  const store = makeStore();
  store.dispatch(resultReceived({ revision: 0, result: result24 }));
  store.dispatch(hourSelected(23));
  store.dispatch(playToggled(24));
  store.dispatch(playTicked(24));
  store.dispatch(playTicked(24));
  expect(selectSelectedHour(store.getState())).toBe(24);
  expect(selectPlaying(store.getState())).toBe(false);
});
