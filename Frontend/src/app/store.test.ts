import { expect, test } from 'vitest';
import {
  csrfReceived,
  loggedIn,
  loggedOut,
  selectIsAuthenticated,
  selectUsername,
} from '../features/auth/authSlice';
import { makeStore } from './store';

test('auth slice keeps the user name for the session and clears it on logout', () => {
  const store = makeStore();
  expect(selectIsAuthenticated(store.getState())).toBe(false);
  store.dispatch(loggedIn('pilot'));
  expect(selectIsAuthenticated(store.getState())).toBe(true);
  expect(selectUsername(store.getState())).toBe('pilot');
  store.dispatch(loggedOut());
  expect(selectIsAuthenticated(store.getState())).toBe(false);
});

test('csrf token is kept for unsafe requests, never the password', () => {
  const store = makeStore();
  store.dispatch(csrfReceived('abc'));
  expect(store.getState().auth.csrfToken).toBe('abc');
  expect(Object.keys(store.getState().auth)).toEqual(['username', 'csrfToken']);
});
