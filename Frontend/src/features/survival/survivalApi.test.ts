import type { FetchArgs } from '@reduxjs/toolkit/query';
import { expect, test } from 'vitest';
import { findFix, findNearestDate, findSuitable, messageOf, MISSION_TIMEOUT_MS } from './survivalApi';

const START = '2026-11-12T00:00:00Z';
const LANDING = '2026-11-16T00:00:00Z';

function fakePost(replies: unknown[]) {
  const bodies: Record<string, unknown>[] = [];
  const post = async (arg: FetchArgs) => {
    bodies.push(arg.body as Record<string, unknown>);
    return { data: replies.shift() };
  };
  return { post, bodies };
}

test('request carries both dates and the timestamp as ISO 8601 with a time zone', async () => {
  const { post, bodies } = fakePost([{ status: 'SUCCESS' }]);
  await findSuitable(post, { latitude: -88.81, longitude: 123.6, start: START, landing: LANDING });
  expect(bodies[0]).toEqual({
    latitude: -88.81,
    longitude: 123.6,
    timestamp: '2026-11-16T00:00:00+00:00',
    launch_date: '2026-11-12T00:00:00+00:00',
    landing_date: '2026-11-16T00:00:00+00:00',
  });
});

test('a point that already survives is kept', async () => {
  const { post } = fakePost([{ status: 'SUCCESS' }]);
  const found = await findSuitable(post, { latitude: -88.81, longitude: 123.6, start: START, landing: LANDING });
  expect(found).toEqual({ suggestion: { latitude: -88.81, longitude: 123.6 } });
});

test('a failing point moves to the safe haven destination', async () => {
  const { post } = fakePost([
    { status: 'FAIL', safe_haven: { destination: { latitude: -89.4, longitude: -137 } } },
  ]);
  const found = await findSuitable(post, { latitude: -89.45, longitude: -136.5, start: START, landing: LANDING });
  expect(found).toEqual({ suggestion: { latitude: -89.4, longitude: -137 } });
});

test('a point outside the region is moved onto the south pole ladder', async () => {
  const { post, bodies } = fakePost([{ status: 'FAIL' }, { status: 'SUCCESS' }]);
  const found = await findSuitable(post, { latitude: 45, longitude: 10, start: START, landing: LANDING });
  expect(bodies.slice(0, 2).map((b) => b.latitude)).toEqual([-89.5, -89]);
  expect(found).toEqual({ suggestion: { latitude: -89, longitude: 10 } });
});

test('server errors become readable messages', () => {
  expect(messageOf({ status: 400, data: { error: 'Посадка разрешена только на Южном полюсе Луны' } })).toBe(
    'Посадка разрешена только на Южном полюсе Луны',
  );
  expect(messageOf({ status: 'FETCH_ERROR', error: 'TypeError' })).toContain('Нет связи');
  expect(messageOf({ status: 500, data: 'oops' })).toBe('Сервер ответил ошибкой 500.');
});

const FAIL = { status: 'FAIL' };
const ARGS = { latitude: -89.45, longitude: -136.5, start: START, landing: LANDING };

test('no suitable coordinates anywhere on the date: findSuitable says so', async () => {
  const { post } = fakePost(Array.from({ length: 10 }, () => FAIL));
  const found = await findSuitable(post, ARGS);
  expect(found).toEqual({ message: 'Подходящих координат на эту дату не нашлось.', none: true });
});

test('the nearest date is found: earlier or later, closest first, same transit length', async () => {
  const { post, bodies } = fakePost([FAIL, { status: 'SUCCESS' }]);
  const found = await findNearestDate(post, ARGS);
  expect(found).toEqual({
    offer: {
      latitude: -89.45,
      longitude: -136.5,
      start: '2026-11-11T00:00:00Z',
      landing: '2026-11-15T00:00:00Z',
    },
  });
  expect(bodies[0]?.landing_date).toBe('2026-11-17T00:00:00+00:00');
  expect(bodies[1]?.landing_date).toBe('2026-11-15T00:00:00+00:00');
});

test('on the nearest date a failing point moves to the safe haven destination', async () => {
  const { post } = fakePost([
    { status: 'FAIL', safe_haven: { destination: { latitude: -89.4, longitude: -137 } } },
  ]);
  const found = await findNearestDate(post, ARGS);
  expect(found).toEqual({
    offer: { latitude: -89.4, longitude: -137, start: '2026-11-13T00:00:00Z', landing: '2026-11-17T00:00:00Z' },
  });
});

test('fix: coordinates first, the nearest date only when the date has none', async () => {
  const same = fakePost([{ status: 'SUCCESS' }]);
  expect(await findFix(same.post, ARGS)).toEqual({
    fix: { kind: 'coords', coord: { latitude: -89.45, longitude: -136.5 } },
  });

  const other = fakePost([...Array.from({ length: 10 }, () => FAIL), { status: 'SUCCESS' }]);
  expect(await findFix(other.post, ARGS)).toEqual({
    fix: {
      kind: 'date',
      offer: {
        latitude: -89.45,
        longitude: -136.5,
        start: '2026-11-13T00:00:00Z',
        landing: '2026-11-17T00:00:00Z',
      },
    },
  });
});

test('fix: a server error is reported as is, without searching dates', async () => {
  const post = async () => ({ error: { status: 500, data: 'oops' } });
  expect(await findFix(post, ARGS)).toEqual({ message: 'Сервер ответил ошибкой 500.' });
});

test('every request has a timeout, so a stuck server cannot cause an endless loading', async () => {
  const seen: FetchArgs[] = [];
  const post = async (arg: FetchArgs) => {
    seen.push(arg);
    return { data: { status: 'SUCCESS' } };
  };
  await findSuitable(post, ARGS);
  expect(seen[0]?.timeout).toBe(MISSION_TIMEOUT_MS);
});

test('the nearest date wins by order, not by which answer arrives first', async () => {
  const post = async (arg: FetchArgs) => {
    const body = arg.body as Record<string, unknown>;
    if (body.landing_date === '2026-11-17T00:00:00+00:00') await new Promise((r) => setTimeout(r, 20));
    return { data: { status: 'SUCCESS' } };
  };
  const found = await findNearestDate(post, ARGS);
  expect(found).toEqual({
    offer: { latitude: -89.45, longitude: -136.5, start: '2026-11-13T00:00:00Z', landing: '2026-11-17T00:00:00Z' },
  });
});

test('one failed latitude does not abort the search for coordinates', async () => {
  const post = async (arg: FetchArgs) => {
    const { latitude } = arg.body as { latitude: number };
    if (latitude === -89.5) return { error: { status: 500, data: 'oops' } };
    return { data: { status: latitude === -89 ? 'SUCCESS' : 'FAIL' } };
  };
  const found = await findSuitable(post, ARGS);
  expect(found).toEqual({ suggestion: { latitude: -89, longitude: -136.5 } });
});

test('when no calculation answered at all, the date search reports the server error', async () => {
  const post = async () => ({ error: { status: 500, data: 'oops' } });
  expect(await findNearestDate(post, ARGS)).toEqual({ message: 'Сервер ответил ошибкой 500.' });
});
