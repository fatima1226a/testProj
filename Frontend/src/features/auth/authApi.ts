import type { FetchArgs } from '@reduxjs/toolkit/query';
import { baseApi, readCsrfCookie } from '../../shared/api/baseApi';
import { fieldMessages, messageOf } from '../../shared/api/errors';
import { t } from '../../shared/i18n';
import { csrfReceived, loggedIn, loggedOut } from './authSlice';

export interface Credentials {
  username: string;
  password: string;
}

export interface Registration extends Credentials {
  email: string;
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;

interface Reply {
  data?: unknown;
  error?: unknown;
}
type Query = (arg: string | FetchArgs) => Reply | PromiseLike<Reply>;

async function ensureCsrf(query: Query, dispatch: (a: ReturnType<typeof csrfReceived>) => unknown) {
  const reply = await query('/auth/csrf/');
  if (isRecord(reply.data)) {
    for (const key of ['csrfToken', 'csrf_token', 'token']) {
      const value = reply.data[key];
      if (typeof value === 'string' && value) dispatch(csrfReceived(value));
    }
  }
  return readCsrfCookie();
}

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    login: build.mutation<string, Credentials>({
      queryFn: async (credentials, api, _extra, baseQuery) => {
        await ensureCsrf(baseQuery, api.dispatch);
        const reply = await baseQuery({ url: '/auth/login/', method: 'POST', body: credentials });
        if (reply.error !== undefined) {
          return { error: { status: 'CUSTOM_ERROR' as const, error: messageOf(reply.error, true) } };
        }
        const name =
          isRecord(reply.data) && typeof reply.data.username === 'string'
            ? reply.data.username
            : credentials.username;
        api.dispatch(loggedIn(name));
        return { data: name };
      },
      invalidatesTags: ['Runs'],
    }),

    register: build.mutation<string, Registration>({
      queryFn: async (form, api, _extra, baseQuery) => {
        await ensureCsrf(baseQuery, api.dispatch);
        const created = await baseQuery({ url: '/auth/register/', method: 'POST', body: form });
        if (created.error !== undefined) {
          return {
            error: {
              status: 'CUSTOM_ERROR' as const,
              error: messageOf(created.error, true),
              data: { errors: fieldMessages(created.error) },
            },
          };
        }
        const login = await baseQuery({
          url: '/auth/login/',
          method: 'POST',
          body: { username: form.username, password: form.password },
        });
        if (login.error !== undefined) {
          return {
            error: {
              status: 'CUSTOM_ERROR' as const,
              error: t('auth.createdButLogin', { error: messageOf(login.error, true) }),
            },
          };
        }
        api.dispatch(loggedIn(form.username));
        return { data: form.username };
      },
      invalidatesTags: ['Runs'],
    }),

    logout: build.mutation<null, void>({
      queryFn: async (_arg, api, _extra, baseQuery) => {
        await baseQuery({ url: '/auth/logout/', method: 'POST' });
        api.dispatch(loggedOut());
        return { data: null };
      },
      invalidatesTags: ['Runs'],
    }),
  }),
});

export const { useLoginMutation, useRegisterMutation, useLogoutMutation } = authApi;
