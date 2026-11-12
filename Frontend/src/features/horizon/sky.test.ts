import { expect, test } from 'vitest';
import type { SkyTrack } from '../datasets/types';
import { horizonAt, horizonPoints, skyAt, skyRange } from './sky';

const track: SkyTrack = {
  startMs: Date.parse('2026-01-01T00:00:00Z'),
  stepMs: 600_000,
  sunAz: [10, 20, 30],
  sunEl: [25, 24, 23],
  earthAz: [0, 0, 0],
  earthEl: [5, 5, 5],
};

test('horizon heights are spread evenly over the circle and interpolated between samples', () => {
  expect(horizonPoints([0, 1, 2, 3])).toEqual([
    { azDeg: 0, elDeg: 0 },
    { azDeg: 90, elDeg: 1 },
    { azDeg: 180, elDeg: 2 },
    { azDeg: 270, elDeg: 3 },
  ]);
  expect(horizonAt([0, 10], 90)).toBe(5);
  expect(horizonAt([0, 10], 270)).toBe(5);
  expect(horizonAt([], 10)).toBe(0);
});

test('inside the dataset window the exact sample is used; outside it the window repeats', () => {
  expect(skyAt(track, track.startMs + 600_000)).toMatchObject({ cyclic: false, point: { sunAz: 20 } });
  expect(skyAt(track, track.startMs + 3 * 600_000)).toMatchObject({ cyclic: true, point: { sunAz: 10 } });
  expect(skyAt(track, track.startMs - 600_000)).toMatchObject({ cyclic: true, point: { sunAz: 30 } });
});

test('the range covers the whole calculation window including its end', () => {
  expect(skyRange(track, track.startMs, 1)).toHaveLength(7);
});
