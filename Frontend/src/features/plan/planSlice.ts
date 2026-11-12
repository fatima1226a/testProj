import { createSelector, createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { DEFAULT_PLAN } from './defaults';
import type { Plan } from './types';
import { validatePlan } from './validatePlan';

interface PlanState {
  plan: Plan;
  revision: number;
}

const initialState: PlanState = {
  plan: DEFAULT_PLAN,
  revision: 0,
};

const planSlice = createSlice({
  name: 'plan',
  initialState,
  reducers: {
    planPatched(state, action: PayloadAction<Partial<Plan>>) {
      Object.assign(state.plan, action.payload);
      state.revision += 1;
    },
  },
});

export const { planPatched } = planSlice.actions;
export const planReducer = planSlice.reducer;

export const selectPlan = (state: RootState): Plan => state.plan.plan;
export const selectPlanRevision = (state: RootState): number => state.plan.revision;

export const selectPlanErrors = createSelector([selectPlan], validatePlan);

export const selectPlanValid = createSelector(
  [selectPlanErrors],
  (errors) => Object.keys(errors).length === 0,
);
