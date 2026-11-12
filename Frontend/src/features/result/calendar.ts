import { addHours } from '../../shared/lib/format';
import { inDateRange, transitHours } from '../plan/dates';
import type { Plan } from '../plan/types';
import type { FailureReason } from './types';

export const CALENDAR_DAYS = 30;

export type CalendarStatus = 'ok' | FailureReason;

export interface CalendarCellData {
  landing: string;
  status: CalendarStatus;
  marginPct: number | null;
}

export function calendarStart(landing: string): string {
  const d = new Date(landing);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1, d.getUTCHours()))
    .toISOString()
    .replace('.000Z', 'Z');
}

export interface CalendarRequest {
  landing: string;
  start: string;
}

export function calendarRequests(plan: Plan): CalendarRequest[] {
  const gap = transitHours(plan.start, plan.landing);
  if (gap === null || gap <= 0) return [];
  const first = calendarStart(plan.landing);
  const out: CalendarRequest[] = [];
  for (let day = 0; day < CALENDAR_DAYS; day++) {
    const landing = addHours(first, day * 24);
    const start = addHours(landing, -gap);
    if (inDateRange(landing) && inDateRange(start)) out.push({ landing, start });
  }
  return out;
}

