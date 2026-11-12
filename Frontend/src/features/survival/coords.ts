import { t } from '../../shared/i18n';
import { formatNumber } from '../../shared/lib/format';
import type { Coord } from '../plan/types';

export const LAT_RANGE = { min: -90, max: 90 } as const;
export const LON_RANGE = { min: -180, max: 180 } as const;

export function isFiniteCoord(coord: Coord): boolean {
  return (
    Number.isFinite(coord.latDeg) &&
    Number.isFinite(coord.lonDeg) &&
    coord.latDeg >= LAT_RANGE.min &&
    coord.latDeg <= LAT_RANGE.max &&
    coord.lonDeg >= LON_RANGE.min &&
    coord.lonDeg <= LON_RANGE.max
  );
}

export const REGION_MAX_LAT = -60;

export function isOutsideRegion(coord: Coord): boolean {
  return coord.latDeg > REGION_MAX_LAT;
}

export const outsideMessage = (): string => t('coord.outside');

export function formatCoord(coord: Coord): string {
  const ns = t(coord.latDeg < 0 ? 'coord.s' : 'coord.n');
  const ew = t(coord.lonDeg < 0 ? 'coord.w' : 'coord.e');
  return `${formatNumber(Math.abs(coord.latDeg), 2)}° ${ns}, ${formatNumber(Math.abs(coord.lonDeg), 2)}° ${ew}`;
}
