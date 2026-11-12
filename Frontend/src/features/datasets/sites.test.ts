import { expect, test } from 'vitest';
import { planSnapshot } from '../runs/snapshot';
import { parseDatasets, parseSites, pickSite } from './parse';

test('sites are read from an array or a wrapper object', () => {
  const list = [{ id: 'shackleton', name: 'Shackleton', latitude: -89.9, longitude: 0 }];
  expect(parseSites(list)).toEqual([{ id: 'shackleton', label: 'Shackleton', latitude: -89.9, longitude: 0 }]);
  expect(parseSites({ results: [{ site_id: 7, coordinates: { lat: '-85', lon: '45' } }] })).toEqual([
    { id: '7', label: '7', latitude: -85, longitude: 45 },
  ]);
  expect(parseSites({})).toEqual([]);
});

test('the site nearest to the landing point is chosen; without coordinates the first one', () => {
  const sites = parseSites([
    { id: 'a', latitude: -89.9, longitude: 0 },
    { id: 'b', latitude: -85.4, longitude: 31 },
  ]);
  expect(pickSite(sites, { latDeg: -85.5, lonDeg: 30 })?.id).toBe('b');
  expect(pickSite(parseSites([{ id: 'x' }, { id: 'y' }]), { latDeg: -89, lonDeg: 0 })?.id).toBe('x');
  expect(pickSite([], { latDeg: -89, lonDeg: 0 })).toBeNull();
});

test('the saved plan carries the dataset and site ids the server checks', () => {
  const plan = { coord: { latDeg: -89.4, lonDeg: 12 }, start: '2026-11-12T00:00:00Z', landing: '2026-11-16T00:00:00Z' };
 expect(planSnapshot(plan, { datasetId: 'ds1', siteId: 'site7' })).toMatchObject({
  datasetId: 'ds1',
  siteId: 'site7',
  latitude: -89.4,
  longitude: 12,
});
});

test('a site carries its horizon and the Sun/Earth track from the dataset', () => {
  const raw = {
    window: { start: '2026-01-01T00:00:00Z', stepMinutes: 10, count: 2 },
    sites: [
      {
        id: 'A',
        name: 'DEMO Site A',
        lat: -89,
        lon: 0,
        horizon: [0, 5, 0, 0],
        hours: [
          { t: '2026-01-01T00:00:00Z', sunAz: 10, sunEl: 25, earthAz: 0, earthEl: 5 },
          { t: '2026-01-01T00:10:00Z', sunAz: 20, sunEl: 24 },
        ],
      },
      { id: 'B', lat: -89.5, lon: 45, horizon: [1, 'x'] },
    ],
  };
  const [a, b] = parseSites(raw);
  expect(a?.horizon).toEqual([0, 5, 0, 0]);
  expect(a?.sky).toEqual({
    startMs: Date.parse('2026-01-01T00:00:00Z'),
    stepMs: 600_000,
    sunAz: [10, 20],
    sunEl: [25, 24],
    earthAz: [0, null],
    earthEl: [5, null],
  });
  expect(b?.horizon).toBeNull();
  expect(b?.sky).toBeNull();
});

test('the dataset id comes from datasetId, not from the format version', () => {
  const release = { version: 2, datasetId: 'demo-mini-v2', sites: [] };
  expect(parseDatasets(release)).toEqual([{ id: 'demo-mini-v2', label: 'demo-mini-v2', mode: null }]);
  expect(parseDatasets([{ id: 'x', version: 3 }])[0]?.id).toBe('x');
});
