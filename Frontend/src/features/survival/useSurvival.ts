import { useState, useSyncExternalStore } from 'react';
import { useAppDispatch } from '../../app/store';
import { t, tm } from '../../shared/i18n';
import { useDebouncedValue } from '../../shared/lib/hooks';
import { planPatched } from '../plan/planSlice';
import type { Coord, Plan } from '../plan/types';
import { validatePlan } from '../plan/validatePlan';
import { isOutsideRegion, outsideMessage } from './coords';
import {
  argsFor,
  getSearchProgress,
  subscribeSearchProgress,
  useCheckSurvivalQuery,
  useSuggestFixMutation,
  type SearchProgress,
} from './survivalApi';
import type { DateSuggestion, SiteSurvival } from './types';

const DEBOUNCE_MS = 350;

const datesInvalid = (plan: Plan): boolean => {
  const errors = validatePlan(plan);
  return errors.start !== undefined || errors.landing !== undefined;
};

export function useSurvival(plan: Plan): SiteSurvival {
  const settled = useDebouncedValue(plan, DEBOUNCE_MS);
  const pending = settled !== plan;
  const outside = isOutsideRegion(plan.coord);
  const invalidDates = datesInvalid(plan);
  const query = useCheckSurvivalQuery(argsFor(settled), {
    skip: isOutsideRegion(settled.coord) || datesInvalid(settled),
  });
  const base = { result: null, survives: null, message: null };

  if (outside) return { ...base, status: 'north', survives: false, message: outsideMessage() };
  if (invalidDates) {
    const errors = validatePlan(plan);
    return { ...base, status: 'error', message: errors.landing ?? errors.start ?? t('surv.checkDates') };
  }
  if (pending || query.isFetching) return { ...base, status: 'loading' };
  if (query.isError) {
    const err = query.error as { error?: unknown } | undefined;
    const message = typeof err?.error === 'string' ? err.error : t('surv.checkFail');
    return { ...base, status: 'error', message };
  }
  const outcome = query.currentData;
  if (!outcome) return { ...base, status: 'loading' };
  const { result } = outcome;
  return {
    status: result.survives ? 'ok' : 'fail',
    survives: result.survives,
    result,
    message: result.survives ? null : (tm(result.assumptions[0]?.text) ?? t('surv.wontSurvive')),
  };
}

export const needsFix = (site: SiteSurvival): boolean =>
  site.status === 'fail' || site.status === 'north';

const round4 = (value: number) => Math.round(value * 10_000) / 10_000;
const DAY_MS = 86_400_000;

export interface DateOffer extends DateSuggestion {
  shiftDays: number;
}

export interface FixNote {
  coord: Coord;
  landing?: string;
}

export interface CoordinateFix {
  run: () => void;
  searching: boolean;
  progress?: SearchProgress | null;
  error: string | null;
  note: FixNote | null;
  offer: DateOffer | null;
  acceptOffer: () => void;
  dismissOffer: () => void;
}

const planKey = (plan: Plan): string =>
  `${plan.coord.latDeg},${plan.coord.lonDeg},${plan.start},${plan.landing}`;

export function useCoordinateFix(plan: Plan, site: SiteSurvival): CoordinateFix {
  const dispatch = useAppDispatch();
  const [suggest, { isLoading }] = useSuggestFixMutation();
  const progress = useSyncExternalStore(subscribeSearchProgress, getSearchProgress);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<FixNote | null>(null);
  const [stored, setStored] = useState<{ key: string; offer: DateOffer } | null>(null);
  const key = planKey(plan);
  const offer = stored && stored.key === key ? stored.offer : null;

  const run = async () => {
    if (!needsFix(site)) return;
    setError(null);
    setStored(null);
    try {
      const found = await suggest(argsFor(plan)).unwrap();
      if (found.kind === 'coords') {
        const next: Coord = { latDeg: round4(found.coord.latitude), lonDeg: round4(found.coord.longitude) };
        setNote({ coord: next });
        dispatch(planPatched({ coord: next }));
        return;
      }
      const shiftDays = Math.round((Date.parse(found.offer.landing) - Date.parse(plan.landing)) / DAY_MS);
      setStored({ key, offer: { ...found.offer, shiftDays } });
    } catch (e) {
      const rec = e as { error?: unknown };
      setError(typeof rec.error === 'string' ? rec.error : t('surv.fixFail'));
    }
  };

  const acceptOffer = () => {
    if (!offer) return;
    const next: Coord = { latDeg: round4(offer.latitude), lonDeg: round4(offer.longitude) };
    setNote({ coord: next, landing: offer.landing });
    setStored(null);
    dispatch(planPatched({ coord: next, start: offer.start, landing: offer.landing }));
  };

  return {
    run: () => void run(),
    searching: isLoading,
    progress: isLoading ? progress : null,
    error,
    note,
    offer,
    acceptOffer,
    dismissOffer: () => setStored(null),
  };
}
