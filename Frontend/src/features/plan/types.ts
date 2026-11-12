import type { HorizonPoint } from '../result/types';

export interface Coord {
  latDeg: number;
  lonDeg: number;
}

export interface Site {
  latDeg: number;
  lonDeg: number;
  horizon: HorizonPoint[];
}

export interface Plan {
  coord: Coord;
  start: string;
  landing: string;
}

export type PlanField = keyof Plan;
export type PlanErrors = Partial<Record<PlanField, string>>;
