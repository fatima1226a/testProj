import { afterEach, expect, test } from 'vitest';
import { formatNumber, formatUtc } from '../lib/format';
import { en } from './en';
import { hasKey, isMsg, msg, resolveMsgs, setLang, t, tm } from './index';
import { ru } from './ru';

afterEach(() => setLang('ru'));

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)(?::\d+)?\}/g)].map((m) => m[1]).sort();

test('both dictionaries have the same keys and the same placeholders', () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(ru).sort());
  for (const key of Object.keys(ru) as (keyof typeof ru)[]) {
    expect(placeholders(en[key]), key).toEqual(placeholders(ru[key]));
  }
});

test('english text has no Cyrillic letters', () => {
  for (const [key, text] of Object.entries(en)) expect(/[А-Яа-яЁё]/.test(text), key).toBe(false);
});

test('the language switch changes texts, numbers and dates', () => {
  expect(t('app.title')).toBe('Хватит ли света?');
  expect(formatNumber(1234.5, 1)).toBe('1\u00a0234,5');
  setLang('en');
  expect(t('app.title')).toBe('Will the light last?');
  expect(formatNumber(1234.5, 1)).toBe('1,234.5');
  expect(formatUtc('2026-11-03T05:00:00Z')).toBe('3 Nov 05:00 UTC');
});

test('a stored message is translated when it is shown, not when it is created', () => {
  const stored = msg('reason.energyText', { wh: 12.34 });
  expect(tm(stored)).toBe('За сутки не хватает 12,3 Вт·ч.');
  setLang('en');
  expect(tm(stored)).toBe('Short by 12.3 Wh over the day.');
  expect(tm('text from the server')).toBe('text from the server');
});

test('messages are recognised and resolved inside data', () => {
  expect(isMsg(msg('val.region'))).toBe(true);
  expect(isMsg({ msg: 'not a key' })).toBe(false);
  expect(hasKey('risk.LOW')).toBe(true);
  setLang('en');
  expect(resolveMsgs({ region: msg('val.region'), list: [msg('risk.HIGH')], n: 1 })).toEqual({
    region: 'Lunar south pole',
    list: ['high'],
    n: 1,
  });
});

test('the 7-day mission requirement is in both languages', () => {
  expect(t('plan.requirement', { days: 7 })).toBe('Условие миссии: аппарат должен выжить 7 суток на Луне.');
  setLang('en');
  expect(t('plan.requirement', { days: 7 })).toBe('Mission requirement: the lander must survive 7 days on the Moon.');
});
