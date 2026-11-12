import { createListenerMiddleware, isAnyOf } from '@reduxjs/toolkit';
import { loggedIn, loggedOut, storeUser } from '../features/auth/authSlice';
import { baseApi } from '../shared/api/baseApi';
import {
  planPatched,
  selectPlan,
  selectPlanRevision,
  selectPlanValid,
} from '../features/plan/planSlice';
import { calendarRequests, type CalendarCellData } from '../features/result/calendar';
import {
  calendarReceived,
  recalculationRequested,
  resultReceived,
} from '../features/result/resultSlice';
import { isOutsideRegion } from '../features/survival/coords';
import { argsFor, survivalApi } from '../features/survival/survivalApi';
import type { SurvivalResult } from '../features/survival/types';
import type { AppDispatch, RootState } from './store';

export const listenerMiddleware = createListenerMiddleware();
const startAppListening = listenerMiddleware.startListening.withTypes<RootState, AppDispatch>();

const DEBOUNCE_MS = 350;
const CALENDAR_PARALLEL = 4;

startAppListening({
  matcher: isAnyOf(planPatched, recalculationRequested),
  effect: async (_action, api) => {
    api.cancelActiveListeners();
    const state = api.getState();
    const revision = selectPlanRevision(state);
    const plan = selectPlan(state);

    if (!selectPlanValid(state) || isOutsideRegion(plan.coord)) {
      api.dispatch(resultReceived({ revision, result: null }));
      api.dispatch(calendarReceived({ revision, calendar: [] }));
      return;
    }

    await api.delay(DEBOUNCE_MS);

    const calc = async (args: ReturnType<typeof argsFor>): Promise<SurvivalResult | null> => {
      const sub = api.dispatch(survivalApi.endpoints.checkSurvival.initiate(args));
      try {
        const reply = await api.pause(sub);
        return reply.data?.result ?? null;
      } finally {
        sub.unsubscribe();
      }
    };

    const main = await calc(argsFor(plan));
    api.dispatch(resultReceived({ revision, result: main?.sim ?? null }));

    const requests = calendarRequests(plan);
    const cells: CalendarCellData[] = [];
    for (let i = 0; i < requests.length; i += CALENDAR_PARALLEL) {
      const batch = requests.slice(i, i + CALENDAR_PARALLEL);
      const answers = await Promise.all(
        batch.map(async ({ landing, start }) => {
          const answer = await calc({ ...argsFor(plan), start, landing });
          return answer
            ? ({
                landing,
                status: answer.survives ? 'ok' : (answer.reason ?? 'other'),
                marginPct: answer.marginPct,
              } satisfies CalendarCellData)
            : null;
        }),
      );
      for (const cell of answers) if (cell) cells.push(cell);
      api.dispatch(calendarReceived({ revision, calendar: [...cells] }));
    }
  },
});

startAppListening({
  matcher: isAnyOf(loggedIn, loggedOut),
  effect: (action, api) => {
    storeUser(loggedIn.match(action) ? action.payload : null);
    api.dispatch(baseApi.util.invalidateTags(['Runs']));
  },
});
