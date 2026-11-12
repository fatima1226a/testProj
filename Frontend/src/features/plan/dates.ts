import { t } from '../../shared/i18n';
import { addHours, hoursBetween } from '../../shared/lib/format';
import { DATE_MAX_ISO, DATE_MIN_ISO } from './defaults';

export const isValidIso = (iso: string): boolean => Number.isFinite(Date.parse(iso));

export const inDateRange = (iso: string): boolean =>
  isValidIso(iso) && Date.parse(iso) >= Date.parse(DATE_MIN_ISO) && Date.parse(iso) <= Date.parse(DATE_MAX_ISO);

export function transitHours(start: string, landing: string): number | null {
  if (!isValidIso(start) || !isValidIso(landing)) return null;
  return hoursBetween(start, landing);
}

export function landingKeepingTransit(plan: { start: string; landing: string }, start: string): string {
  const gap = transitHours(plan.start, plan.landing);
  if (gap === null || gap <= 0 || !isValidIso(start)) return plan.landing;
  return addHours(start, gap);
}

export function startKeepingTransit(plan: { start: string; landing: string }, landing: string): string {
  const gap = transitHours(plan.start, plan.landing);
  if (gap === null || gap <= 0 || !isValidIso(landing)) return plan.start;
  return addHours(landing, -gap);
}

export function formatTransit(hours: number | null): string {
  if (hours === null || hours <= 0) return '—';
  const days = Math.floor(hours / 24);
  const rest = hours % 24;
  if (days === 0) return t('time.hours', { n: rest });
  return rest === 0 ? t('time.days', { n: days }) : t('time.daysHours', { d: days, h: rest });
}
