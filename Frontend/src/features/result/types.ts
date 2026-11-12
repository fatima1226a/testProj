export type FailureReason = 'battery' | 'terrain' | 'other';

export interface HourSample {
  sun: boolean;
  earth: boolean | null;
  sunAzDeg: number | null;
  sunElDeg: number | null;
  earthAzDeg: number | null;
  earthElDeg: number | null;
  temperatureC: number | null;
  generationW: number | null;
  insolationPct: number | null;
}

export interface Failure {
  hour: number;
  reason: FailureReason;
  codes: string[];
}

export interface Limits {
  durationH: number | null;
  stepH: number | null;
  minSocPct: number | null;
  initialSocPct: number | null;
  capacityWh: number | null;
  panelW: number | null;
  systemsW: number | null;
  heaterW: number | null;
  maxSlopeDeg: number | null;
}

export interface Kpi {
  minBatteryPct: number | null;
  longestShadowH: number | null;
  earthHours: number | null;
  sunlitPct: number | null;
}

export interface HorizonPoint {
  azDeg: number;
  elDeg: number;
}

export interface Result {
  hours: HourSample[];
  batteryPct: number[];
  failure: Failure | null;
  kpi: Kpi;
  limits: Limits;
  horizon: HorizonPoint[];
}

export const lastHour = (result: Result | null): number =>
  result ? Math.max(0, result.hours.length - 1) : 0;
