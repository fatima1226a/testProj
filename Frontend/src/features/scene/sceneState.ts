import { createSelector } from '@reduxjs/toolkit';
import { t } from '../../shared/i18n';
import { selectResult } from '../result/resultSlice';
import type { HourSample, Result } from '../result/types';
import { selectSelectedHour } from '../timeline/viewSlice';

export type SceneState = 'working' | 'charging' | 'danger' | 'fading' | 'noEarth';

export interface SceneSnapshot {
  state: SceneState;
  onBattery: boolean;
  batteryFailed: boolean;
  sample: HourSample;
  batteryPct: number;
}

const DANGER_PCT = 40;
const DANGER_RESERVE_H = 6;

const clamp = (k: number, length: number) => Math.min(length - 1, Math.max(0, k));

export function sampleAtBoundary(result: Result, k: number): HourSample {
  const sample = result.hours[clamp(k, result.hours.length)];
  if (!sample) throw new Error('Empty result');
  return sample;
}

export function sceneStateAt(result: Result, k: number): SceneSnapshot {
  const i = clamp(k, result.hours.length);
  const sample = sampleAtBoundary(result, k);
  const pct = result.batteryPct[i] ?? 0;
  const prev = result.batteryPct[Math.max(0, i - 1)] ?? pct;
  const { minSocPct, capacityWh, systemsW } = result.limits;
  const minPct = minSocPct ?? 0;
  const batteryFailed = result.failure?.reason === 'battery' && i >= result.failure.hour;
  const reserveH =
    capacityWh !== null && systemsW !== null && systemsW > 0
      ? (((pct - minPct) / 100) * capacityWh) / systemsW
      : Infinity;

  let state: SceneState = 'working';
  if (batteryFailed || pct < minPct) state = 'fading';
  else if (sample.earth === false) state = 'noEarth';
  else if (pct < DANGER_PCT || (!sample.sun && reserveH <= DANGER_RESERVE_H)) state = 'danger';
  else if (sample.sun && pct > prev) state = 'charging';

  return { state, onBattery: !sample.sun, batteryFailed, sample, batteryPct: pct };
}

export const stateLabel = (state: SceneState): string => t(`state.${state}`);

export const selectSceneSnapshot = createSelector(
  [selectResult, selectSelectedHour],
  (result, hour) => (result && result.hours.length > 0 ? sceneStateAt(result, hour) : null),
);
