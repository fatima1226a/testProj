import { expect, test } from 'vitest';
import { formatCoord, isFiniteCoord, isOutsideRegion } from './coords';

test('everything north of -60 is outside the landing region', () => {
  expect(isOutsideRegion({ latDeg: 45, lonDeg: 10 })).toBe(true);
  expect(isOutsideRegion({ latDeg: 0, lonDeg: 10 })).toBe(true);
  expect(isOutsideRegion({ latDeg: -59.9, lonDeg: 10 })).toBe(true);
  expect(isOutsideRegion({ latDeg: -60, lonDeg: 10 })).toBe(false);
  expect(isOutsideRegion({ latDeg: -89.45, lonDeg: -136.5 })).toBe(false);
});

test('coordinates outside the sphere are rejected', () => {
  expect(isFiniteCoord({ latDeg: -89, lonDeg: 120 })).toBe(true);
  expect(isFiniteCoord({ latDeg: -91, lonDeg: 0 })).toBe(false);
  expect(isFiniteCoord({ latDeg: -89, lonDeg: 181 })).toBe(false);
  expect(isFiniteCoord({ latDeg: Number.NaN, lonDeg: 0 })).toBe(false);
});

test('formatCoord uses hemisphere words', () => {
  const text = formatCoord({ latDeg: -89.45, lonDeg: -136.5 });
  expect(text).toContain('ю. ш.');
  expect(text).toContain('з. д.');
});
