import { useSyncExternalStore } from 'react';
import { formatNumber } from '../lib/format';
import { en } from './en';
import { getLang, subscribeLang, type Lang } from './lang';
import { ru } from './ru';

export { getLang, localeOf, setLang, type Lang } from './lang';

export type MsgKey = keyof typeof ru;
export type MsgParams = Record<string, number | string | null | undefined>;

export interface Msg {
  msg: MsgKey;
  params?: MsgParams;
}
export type Say = string | Msg;

const DICTS: Record<Lang, Record<MsgKey, string>> = { ru, en };

export const msg = (key: MsgKey, params?: MsgParams): Msg => (params ? { msg: key, params } : { msg: key });

export const hasKey = (key: string): key is MsgKey => key in ru;

export function isMsg(value: unknown): value is Msg {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    typeof (value as { msg?: unknown }).msg === 'string' &&
    (value as { msg: string }).msg in ru
  );
}

function interpolate(template: string, params?: MsgParams): string {
  return template.replace(/\{(\w+)(?::(\d+))?\}/g, (_, name: string, digits?: string) => {
    const value = params?.[name];
    if (value === undefined) return '';
    if (value === null) return '—';
    if (typeof value === 'number') return formatNumber(value, digits ? Number(digits) : 0);
    return value;
  });
}

export function t(key: MsgKey, params?: MsgParams): string {
  return interpolate(DICTS[getLang()][key], params);
}

export function tm(text: Say): string;
export function tm(text: Say | null | undefined): string | null;
export function tm(text: Say | null | undefined): string | null {
  if (text === null || text === undefined) return null;
  return typeof text === 'string' ? text : t(text.msg, text.params);
}

export function resolveMsgs(value: unknown): unknown {
  if (isMsg(value)) return tm(value);
  if (Array.isArray(value)) return value.map(resolveMsgs);
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, resolveMsgs(v)]));
  }
  return value;
}

export function useLang(): Lang {
  return useSyncExternalStore(subscribeLang, getLang, getLang);
}
