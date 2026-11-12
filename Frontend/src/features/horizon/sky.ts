import type { HorizonPoint } from '../result/types';
import type { SkyTrack } from '../datasets/types';

const HOUR_MS = 3_600_000;

export interface SkyPoint {
  sunAz: number | null;
  sunEl: number | null;
  earthAz: number | null;
  earthEl: number | null;
}

export function horizonPoints(elevations: readonly number[]): HorizonPoint[] {
  const n = elevations.length;
  return elevations.map((elDeg, i) => ({ azDeg: (i * 360) / n, elDeg }));
}

export function horizonAt(elevations: readonly number[], az: number): number {
  const n = elevations.length;
  if (n === 0) return 0;
  const pos = ((((az % 360) + 360) % 360) / 360) * n;
  const i = Math.floor(pos);
  const a = elevations[i % n] ?? 0;
  const b = elevations[(i + 1) % n] ?? a;
  return a + (b - a) * (pos - i);
}

export function skyAt(track: SkyTrack, ms: number): { point: SkyPoint; cyclic: boolean } | null {
  const n = track.sunAz.length;
  if (n === 0) return null;
  const raw = Math.round((ms - track.startMs) / track.stepMs);
  const i = ((raw % n) + n) % n;
  return {
    cyclic: raw < 0 || raw >= n,
    point: {
      sunAz: track.sunAz[i] ?? null,
      sunEl: track.sunEl[i] ?? null,
      earthAz: track.earthAz[i] ?? null,
      earthEl: track.earthEl[i] ?? null,
    },
  };
}

export function skyRange(track: SkyTrack, fromMs: number, durationH: number): SkyPoint[] {
  const count = Math.max(1, Math.floor((durationH * HOUR_MS) / track.stepMs)) + 1;
  const out: SkyPoint[] = [];
  for (let k = 0; k < count; k++) {
    const hit = skyAt(track, fromMs + k * track.stepMs);
    if (hit) out.push(hit.point);
  }
  return out;
}

export function trackPath(
  points: readonly { az: number | null; el: number | null }[],
  x: (v: number) => number,
  y: (v: number) => number,
): string {
  let prev: number | null = null;
  return points
    .map((p) => {
      if (p.az === null || p.el === null) {
        prev = null;
        return '';
      }
      const jump = prev === null || Math.abs(prev - p.az) > 180;
      prev = p.az;
      return `${jump ? 'M' : 'L'}${x(p.az).toFixed(1)},${y(p.el).toFixed(1)}`;
    })
    .join('');
}
