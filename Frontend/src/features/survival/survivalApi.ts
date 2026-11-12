import type { FetchArgs } from '@reduxjs/toolkit/query';
import { baseApi } from '../../shared/api/baseApi';
import { messageOf } from '../../shared/api/errors';
import { t } from '../../shared/i18n';
import { addHours, toWireIso } from '../../shared/lib/format';
import { inDateRange, transitHours } from '../plan/dates';
import type { Plan } from '../plan/types';
import { REGION_MAX_LAT } from './coords';
import { parseMission, type MissionAnswer } from './missionAdapter';
import {
  rawResponseSchema,
  type DateSuggestion,
  type FixResult,
  type Suggestion,
  type SurvivalArgs,
  type SurvivalOutcome,
} from './types';

export const MISSION_URL = '/mission/';

export const SEARCH_PARALLEL = 6;
export const MISSION_TIMEOUT_MS = 30_000;

const LATITUDE_LADDER = [-89.5, -89, -88, -86, -84, -80, -75, -70, -65];

interface Reply {
  data?: unknown;
  error?: unknown;
}
type Post = (arg: FetchArgs) => Reply | PromiseLike<Reply>;

export { messageOf };

export const LAUNCH_FIELD = 'launch_date';
export const LANDING_FIELD = 'landing_date';
export const TIMESTAMP_FIELD = 'timestamp';

export function argsFor(plan: Plan): SurvivalArgs {
  return {
    latitude: plan.coord.latDeg,
    longitude: plan.coord.lonDeg,
    start: plan.start,
    landing: plan.landing,
  };
}

export function missionBody(args: SurvivalArgs): Record<string, unknown> {
  return {
    latitude: args.latitude,
    longitude: args.longitude,
    [TIMESTAMP_FIELD]: toWireIso(args.landing),
    [LAUNCH_FIELD]: toWireIso(args.start),
    [LANDING_FIELD]: toWireIso(args.landing),
  };
}

export async function requestMission(
  post: Post,
  args: SurvivalArgs,
): Promise<{ answer: MissionAnswer } | { message: string }> {
  const reply = await post({
    url: MISSION_URL,
    method: 'POST',
    body: missionBody(args),
    timeout: MISSION_TIMEOUT_MS,
  });
  if (reply.error !== undefined) return { message: messageOf(reply.error) };
  const parsed = rawResponseSchema.safeParse(reply.data);
  if (!parsed.success) return { message: t('api.noResult') };
  return { answer: parseMission(parsed.data, args.landing) };
}

export type NotFound = { message: string; none?: true };

export interface SearchProgress {
  stage: 'coords' | 'dates';
  done: number;
  total: number;
}

export interface SearchOptions {
  signal?: AbortSignal;
  onProgress?: (progress: SearchProgress) => void;
}

type MissionReply = Awaited<ReturnType<typeof requestMission>>;

const isUsable = (reply: MissionReply): boolean =>
  'answer' in reply && (reply.answer.result.survives || reply.answer.destination !== null);

function pointOf(reply: MissionReply, own: Suggestion): Suggestion | null {
  if (!('answer' in reply)) return null;
  if (reply.answer.result.survives) return own;
  return reply.answer.destination;
}

interface Probe<T> {
  item: T;
  reply: MissionReply;
}

async function firstHit<T>(
  items: readonly T[],
  run: (item: T) => Promise<MissionReply>,
  opts: SearchOptions & { onSettled?: (done: number) => void } = {},
): Promise<{ hit: Probe<T> | null; replies: Probe<T>[] }> {
  const slots: (Probe<T> | undefined)[] = items.map(() => undefined);
  const state: { next: number; head: number; done: number; hit: Probe<T> | null } = {
    next: 0,
    head: 0,
    done: 0,
    hit: null,
  };
  let release: () => void = () => undefined;
  const confirmed = new Promise<void>((resolve) => {
    release = resolve;
  });

  const worker = async (): Promise<void> => {
    while (state.hit === null && !opts.signal?.aborted) {
      const index = state.next++;
      const item = items[index];
      if (item === undefined) return;
      const probe: Probe<T> = { item, reply: await run(item) };
      slots[index] = probe;
      state.done += 1;
      opts.onSettled?.(state.done);
      for (let slot = slots[state.head]; slot && state.hit === null; slot = slots[state.head]) {
        if (isUsable(slot.reply)) {
          state.hit = slot;
          release();
        } else {
          state.head += 1;
        }
      }
    }
  };

  const workers = Array.from({ length: Math.min(SEARCH_PARALLEL, items.length) }, worker);
  await Promise.race([Promise.all(workers), confirmed]);
  return { hit: state.hit, replies: slots.filter((slot): slot is Probe<T> => slot !== undefined) };
}

function onlyErrors<T>(replies: Probe<T>[]): string | null {
  if (replies.length === 0) return null;
  const messages: string[] = [];
  for (const { reply } of replies) {
    if (!('message' in reply)) return null;
    messages.push(reply.message);
  }
  return messages[0] ?? null;
}

export async function findSuitable(
  post: Post,
  args: SurvivalArgs,
  opts: SearchOptions = {},
): Promise<{ suggestion: Suggestion } | NotFound> {
  const inRegion = args.latitude <= REGION_MAX_LAT;
  const own: Suggestion = { latitude: args.latitude, longitude: args.longitude };
  const ladder = LATITUDE_LADDER.filter((latitude) => !(inRegion && latitude === args.latitude));
  const total = ladder.length + (inRegion ? 1 : 0);
  opts.onProgress?.({ stage: 'coords', done: 0, total });

  if (inRegion) {
    const first = await requestMission(post, args);
    if ('message' in first) return first;
    const point = pointOf(first, own);
    if (point) return { suggestion: point };
    opts.onProgress?.({ stage: 'coords', done: 1, total });
  }

  const offset = inRegion ? 1 : 0;
  const { hit, replies } = await firstHit(
    ladder,
    (latitude) => requestMission(post, { ...args, latitude }),
    {
      signal: opts.signal,
      onSettled: (done) => opts.onProgress?.({ stage: 'coords', done: offset + done, total }),
    },
  );
  if (hit) {
    const point = pointOf(hit.reply, { latitude: hit.item, longitude: args.longitude });
    if (point) return { suggestion: point };
  }
  const failure = onlyErrors(replies);
  if (failure) return { message: failure };
  return { message: t('api.noCoords'), none: true };
}

export const NEAREST_DATE_DAYS = 30;

export async function findNearestDate(
  post: Post,
  args: SurvivalArgs,
  opts: SearchOptions = {},
): Promise<{ offer: DateSuggestion } | NotFound> {
  const gap = transitHours(args.start, args.landing);
  if (gap === null || gap <= 0) return { message: t('api.checkDates') };

  const candidates: { landing: string; start: string }[] = [];
  for (let day = 1; day <= NEAREST_DATE_DAYS; day++) {
    for (const sign of [1, -1]) {
      const landing = addHours(args.landing, sign * day * 24);
      const start = addHours(landing, -gap);
      if (inDateRange(landing) && inDateRange(start)) candidates.push({ landing, start });
    }
  }

  const latitude = args.latitude <= REGION_MAX_LAT ? args.latitude : (LATITUDE_LADDER[0] ?? -89.5);
  const total = candidates.length;
  opts.onProgress?.({ stage: 'dates', done: 0, total });

  const { hit, replies } = await firstHit(
    candidates,
    (dates) => requestMission(post, { ...args, latitude, ...dates }),
    {
      signal: opts.signal,
      onSettled: (done) => opts.onProgress?.({ stage: 'dates', done, total }),
    },
  );
  if (hit) {
    const point = pointOf(hit.reply, { latitude, longitude: args.longitude });
    if (point) return { offer: { ...point, ...hit.item } };
  }
  const failure = onlyErrors(replies);
  if (failure) return { message: failure };
  return { message: t('api.noDate', { days: NEAREST_DATE_DAYS }), none: true };
}

export async function findFix(
  post: Post,
  args: SurvivalArgs,
  opts: SearchOptions = {},
): Promise<{ fix: FixResult } | { message: string }> {
  const coords = await findSuitable(post, args, opts);
  if ('suggestion' in coords) return { fix: { kind: 'coords', coord: coords.suggestion } };
  if (!coords.none) return { message: coords.message };

  const date = await findNearestDate(post, args, opts);
  if ('offer' in date) return { fix: { kind: 'date', offer: date.offer } };
  if (!date.none) return { message: date.message };
  return {
    message: t('api.noneAtAll', { days: NEAREST_DATE_DAYS }),
  };
}

let currentProgress: SearchProgress | null = null;
const progressListeners = new Set<() => void>();
const setProgress = (next: SearchProgress | null): void => {
  currentProgress = next;
  progressListeners.forEach((listener) => listener());
};
export const getSearchProgress = (): SearchProgress | null => currentProgress;
export const subscribeSearchProgress = (listener: () => void): (() => void) => {
  progressListeners.add(listener);
  return () => progressListeners.delete(listener);
};

export const survivalApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    checkSurvival: build.query<SurvivalOutcome, SurvivalArgs>({
      queryFn: async (args, _api, _extra, baseQuery) => {
        const reply = await requestMission(baseQuery, args);
        if ('message' in reply) {
          return { error: { status: 'CUSTOM_ERROR' as const, error: reply.message } };
        }
        return { data: { result: reply.answer.result } };
      },
    }),

    suggestFix: build.mutation<FixResult, SurvivalArgs>({
      queryFn: async (args, api, _extra, baseQuery) => {
        let found: Awaited<ReturnType<typeof findFix>>;
        try {
          found = await findFix(baseQuery, args, { signal: api.signal, onProgress: setProgress });
        } finally {
          setProgress(null);
        }
        if ('message' in found) {
          return { error: { status: 'CUSTOM_ERROR' as const, error: found.message } };
        }
        return { data: found.fix };
      },
    }),
  }),
});

export const { useCheckSurvivalQuery, useSuggestFixMutation } = survivalApi;
