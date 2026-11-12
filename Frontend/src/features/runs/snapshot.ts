import type { Plan } from '../plan/types';

type Rec = Record<string, unknown>;

export function planSnapshot(plan: Plan, ids?: { datasetId: string; siteId: string }): Rec {
  return {
    coord: { latDeg: plan.coord.latDeg, lonDeg: plan.coord.lonDeg },
    latitude: plan.coord.latDeg,
    longitude: plan.coord.lonDeg,
    start: plan.start,
    landing: plan.landing,
    ...(ids ? { datasetId: ids.datasetId, siteId: ids.siteId } : {}),
  };
}

const rec = (v: unknown): Rec =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Rec) : {};
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function planFromSnapshot(snapshot: Rec): Partial<Plan> {
  const patch: Partial<Plan> = {};
  const coord = rec(snapshot.coord);
  if (finite(coord.latDeg) && finite(coord.lonDeg)) {
    patch.coord = { latDeg: coord.latDeg, lonDeg: coord.lonDeg };
  }
  if (typeof snapshot.start === 'string') patch.start = snapshot.start;
  if (typeof snapshot.landing === 'string') patch.landing = snapshot.landing;
  return patch;
}

export const RUN_SITE_ID = 'landing';
