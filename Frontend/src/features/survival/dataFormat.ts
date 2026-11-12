import { isMsg, t, tm } from '../../shared/i18n';
import { formatNumber } from '../../shared/lib/format';
import { keyLabel } from './labels';

export const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v) && !isMsg(v);

export function formatScalar(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (isMsg(value)) return tm(value);
  if (typeof value === 'boolean') return t(value ? 'common.yes' : 'common.no');
  if (typeof value === 'number') return formatNumber(value, Number.isInteger(value) ? 0 : 2);
  return String(value);
}

export const isScalar = (v: unknown) =>
  v === null || isMsg(v) || ['string', 'number', 'boolean', 'undefined'].includes(typeof v);

export function previewOf(data: unknown): string {
  if (isRecord(data)) {
    return Object.entries(data)
      .filter(([, v]) => isScalar(v) && v !== null && v !== undefined)
      .slice(0, 2)
      .map(([k, v]) => `${keyLabel(k)}: ${formatScalar(v)}`)
      .join(' · ');
  }
  if (isScalar(data)) return formatScalar(data);
  return '';
}
