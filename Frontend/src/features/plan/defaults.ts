import type { Plan } from './types';

export const DATE_MIN = '2010-01-01';
export const DATE_MAX = '2035-12-31';
export const DATE_MIN_ISO = `${DATE_MIN}T00:00:00Z`;
export const DATE_MAX_ISO = `${DATE_MAX}T23:00:00Z`;

export const DEFAULT_TRANSIT_DAYS = 4;

export const SURVIVAL_DAYS = 7;

export const DEFAULT_PLAN: Plan = {
  coord: { latDeg: -89.45, lonDeg: -136.5 },
  start: '2026-11-14T00:00:00Z',
  landing: '2026-11-18T00:00:00Z',
};
