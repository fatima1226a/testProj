import { configureStore } from '@reduxjs/toolkit';
import { useDispatch, useSelector, type TypedUseSelectorHook } from 'react-redux';
import { authReducer } from '../features/auth/authSlice';
import { planReducer } from '../features/plan/planSlice';
import { recalculationRequested, resultReducer } from '../features/result/resultSlice';
import { viewReducer } from '../features/timeline/viewSlice';
import { baseApi } from '../shared/api/baseApi';
import { listenerMiddleware } from './listener';

export function makeStore() {
  const store = configureStore({
    reducer: {
      auth: authReducer,
      plan: planReducer,
      view: viewReducer,
      result: resultReducer,
      [baseApi.reducerPath]: baseApi.reducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().prepend(listenerMiddleware.middleware).concat(baseApi.middleware),
  });
  store.dispatch(recalculationRequested());
  return store;
}

export const store = makeStore();

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];

export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
