import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../../app/store';

interface AuthState {
  username: string | null;
  csrfToken: string | null;
}

const STORAGE_KEY = 'last-light:user';

function readStoredUser(): string | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeUser(username: string | null): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (username) localStorage.setItem(STORAGE_KEY, username);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
  }
}

const initialState: AuthState = {
  username: readStoredUser(),
  csrfToken: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    loggedIn(state, action: PayloadAction<string>) {
      state.username = action.payload;
    },
    loggedOut(state) {
      state.username = null;
    },
    csrfReceived(state, action: PayloadAction<string>) {
      state.csrfToken = action.payload;
    },
  },
});

export const { loggedIn, loggedOut, csrfReceived } = authSlice.actions;
export const authReducer = authSlice.reducer;

export const selectUsername = (state: RootState): string | null => state.auth.username;
export const selectIsAuthenticated = (state: RootState): boolean => state.auth.username !== null;
