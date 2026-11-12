import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';
import { planPatched } from '../plan/planSlice';
import { selectResult } from '../result/resultSlice';
import { lastHour } from '../result/types';

export const SPEEDS = [1, 4, 12] as const;
export type Speed = (typeof SPEEDS)[number];

interface ViewState {
  selectedHour: number;
  playing: boolean;
  speed: Speed;
}

const initialState: ViewState = {
  selectedHour: 0,
  playing: false,
  speed: 4,
};

const viewSlice = createSlice({
  name: 'view',
  initialState,
  reducers: {
    hourSelected(state, action: PayloadAction<number>) {
      state.selectedHour = Math.max(0, Math.round(action.payload));
      state.playing = false;
    },
    playTicked(state, action: PayloadAction<number>) {
      if (state.selectedHour >= action.payload) state.playing = false;
      else state.selectedHour += 1;
    },
    playToggled(state, action: PayloadAction<number>) {
      if (!state.playing && state.selectedHour >= action.payload) state.selectedHour = 0;
      state.playing = !state.playing;
    },
    speedSet(state, action: PayloadAction<Speed>) {
      state.speed = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase(planPatched, (state, action) => {
      state.playing = false;
      if (action.payload.landing !== undefined || action.payload.start !== undefined) {
        state.selectedHour = 0;
      }
    });
  },
});

export const { hourSelected, playTicked, playToggled, speedSet } = viewSlice.actions;
export const viewReducer = viewSlice.reducer;

export const selectSelectedHour = (state: RootState): number => {
  const result = selectResult(state);
  return result ? Math.min(state.view.selectedHour, lastHour(result)) : state.view.selectedHour;
};
export const selectPlaying = (state: RootState): boolean => state.view.playing;
export const selectSpeed = (state: RootState): Speed => state.view.speed;
