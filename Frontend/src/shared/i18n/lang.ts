export type Lang = 'ru' | 'en';

const STORAGE_KEY = 'last-light:lang';

function readStored(): Lang {
  try {
    const value = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    if (value === 'ru' || value === 'en') return value;
  } catch {
  }
  return 'ru';
}

let current: Lang = readStored();
const listeners = new Set<() => void>();

export const getLang = (): Lang => current;

export function setLang(next: Lang): void {
  if (next === current) return;
  current = next;
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, next);
  } catch {
  }
  if (typeof document !== 'undefined') document.documentElement.lang = next;
  listeners.forEach((listener) => listener());
}

export function subscribeLang(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const localeOf = (lang: Lang = current): string => (lang === 'en' ? 'en-GB' : 'ru-RU');
