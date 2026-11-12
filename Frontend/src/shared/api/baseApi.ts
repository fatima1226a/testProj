import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { BaseQueryFn, FetchArgs, FetchBaseQueryError } from '@reduxjs/toolkit/query/react';
import { loggedOut } from '../../features/auth/authSlice';
import type { RootState } from '../../app/store';

const API_URL = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/+$/, '');

export function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

const rawBaseQuery = fetchBaseQuery({
  baseUrl: API_URL,
  credentials: 'include',
  prepareHeaders: (headers, { getState }) => {
    const token = readCsrfCookie() ?? (getState() as RootState).auth.csrfToken;
    if (token) headers.set('X-CSRFToken', token);
    return headers;
  },
});

const baseQuery: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extra,
) => {
  const result = await rawBaseQuery(args, api, extra);
  const data = result.error?.data;
  const unauthenticated =
    result.error?.status === 401 ||
    (result.error?.status === 403 &&
      typeof data === 'object' &&
      data !== null &&
      /credentials were not provided|not authenticated/i.test(String((data as { detail?: unknown }).detail ?? '')));
  if (unauthenticated && (api.getState() as RootState).auth.username !== null) {
    api.dispatch(loggedOut());
  }
  return result;
};

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery,
  tagTypes: ['Dataset', 'Runs', 'Auth'],
  endpoints: () => ({}),
});
