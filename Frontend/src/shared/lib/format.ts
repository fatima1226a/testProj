import { getLang, localeOf } from '../i18n/lang';

const HOUR_MS = 3_600_000;

export function addHours(iso: string, hours: number): string {
  return new Date(Date.parse(iso) + hours * HOUR_MS).toISOString().replace('.000Z', 'Z');
}

export function hoursBetween(fromIso: string, toIso: string): number {
  return Math.round((Date.parse(toIso) - Date.parse(fromIso)) / HOUR_MS);
}

export function toWireIso(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  return new Date(t).toISOString().replace(/\.\d{3}Z$/, '+00:00');
}

export function isoFromParts(date: string, hour: number): string {
  return `${date}T${String(hour).padStart(2, '0')}:00:00Z`;
}

export function datePart(iso: string): string {
  return iso.slice(0, 10);
}

export function hourPart(iso: string): number {
  return new Date(iso).getUTCHours();
}

const dayFormats = new Map<string, Intl.DateTimeFormat>();
const timeFormats = new Map<string, Intl.DateTimeFormat>();

function dayFormatter(): Intl.DateTimeFormat {
  const locale = localeOf();
  let format = dayFormats.get(locale);
  if (!format) {
    format = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', timeZone: 'UTC' });
    dayFormats.set(locale, format);
  }
  return format;
}

function timeFormatter(): Intl.DateTimeFormat {
  const locale = localeOf();
  let format = timeFormats.get(locale);
  if (!format) {
    format = new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
      timeZone: 'UTC',
    });
    timeFormats.set(locale, format);
  }
  return format;
}

export function formatDay(iso: string): string {
  return dayFormatter().format(new Date(iso));
}

export function formatUtc(iso: string): string {
  const date = new Date(iso);
  return `${dayFormatter().format(date)} ${timeFormatter().format(date)} UTC`;
}

export function formatMonth(iso: string): string {
  const locale = localeOf();
  return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso));
}

const numberFormats = new Map<string, Intl.NumberFormat>();

export function formatNumber(value: number, digits = 0): string {
  const cacheKey = `${getLang()}:${digits}`;
  let format = numberFormats.get(cacheKey);
  if (!format) {
    format = new Intl.NumberFormat(localeOf(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    numberFormats.set(cacheKey, format);
  }
  return format.format(value);
}
