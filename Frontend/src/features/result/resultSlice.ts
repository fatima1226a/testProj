import { createAction, createSelector, createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { selectPlan, selectPlanRevision, selectPlanValid } from '../plan/planSlice';
import type { Site } from '../plan/types';
import type { CalendarCellData } from './calendar';
import type { Result } from './types';

interface ResultState {
  revision: number | null;
  result: Result | null;
  calendarRevision: number | null;
  calendar: CalendarCellData[];
}

const initialState: ResultState = {
  revision: null,
  result: null,
  calendarRevision: null,
  calendar: [],
};

export const recalculationRequested = createAction('result/recalculationRequested');

const resultSlice = createSlice({
  name: 'result',
  initialState,
  reducers: {
    resultReceived(state, action: PayloadAction<{ revision: number; result: Result | null }>) {
      if (state.revision !== null && action.payload.revision < state.revision) return;
      state.revision = action.payload.revision;
      state.result = action.payload.result;
    },
    calendarReceived(
      state,
      action: PayloadAction<{ revision: number; calendar: CalendarCellData[] }>,
    ) {
      if (state.calendarRevision !== null && action.payload.revision < state.calendarRevision) return;
      state.calendarRevision = action.payload.revision;
      state.calendar = action.payload.calendar;
    },
  },
});

export const { resultReceived, calendarReceived } = resultSlice.actions;
export const resultReducer = resultSlice.reducer;

const selectResultState = (state: RootState) => state.result;

const selectIsCurrent = createSelector(
  [selectResultState, selectPlanRevision],
  (result, revision) => result.revision === revision,
);

export const selectResult = (state: RootState): Result | null =>
  selectIsCurrent(state) ? state.result.result : null;

const EMPTY: CalendarCellData[] = [];

export const selectCalendar = (state: RootState): CalendarCellData[] =>
  state.result.calendarRevision === selectPlanRevision(state) ? state.result.calendar : EMPTY;

export const selectRecalculating = (state: RootState): boolean =>
  selectPlanValid(state) && !selectIsCurrent(state);

export const selectSite = createSelector(
  [selectPlan, selectResult],
  (plan, result): Site => ({
    latDeg: plan.coord.latDeg,
    lonDeg: plan.coord.lonDeg,
    horizon: result?.horizon ?? [],
  }),
);
