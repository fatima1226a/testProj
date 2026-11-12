import { getLang, t, type MsgKey } from '../i18n';

export const networkMessage = (): string => t('err.network');

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;

const MAX_DEPTH = 4;

function firstText(value: unknown, depth = 0): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = firstText(item, depth + 1);
      if (text) return text;
    }
  }
  if (isRecord(value) && depth < MAX_DEPTH) {
    for (const key of GENERIC_KEYS) {
      const text = firstText(value[key], depth + 1);
      if (text) return text;
    }
    for (const item of Object.values(value)) {
      const text = firstText(item, depth + 1);
      if (text) return text;
    }
  }
  return null;
}

const GENERIC_KEYS = ['error', 'detail', 'message', 'non_field_errors'];

export function fieldMessages(error: unknown): Record<string, string> {
  if (!isRecord(error) || !isRecord(error.data)) return {};
  const body = isRecord(error.data.errors) ? error.data.errors : error.data;
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(body)) {
    if (GENERIC_KEYS.includes(key)) continue;
    const text = firstText(value);
    if (text) out[key] = text;
  }
  return out;
}

const CYRILLIC = /[А-Яа-яЁё]/;
const FIELD_TAKEN: Record<string, MsgKey> = { username: 'srv.usernameTaken', email: 'srv.emailTaken' };
const FIELD_REQUIRED: Record<string, MsgKey> = {
  username: 'auth.v.usernameRequired',
  email: 'auth.v.emailRequired',
  password: 'auth.v.passwordRequired',
};
const FIELD_FALLBACK: Record<string, MsgKey> = {
  username: 'srv.fieldUsername',
  email: 'srv.fieldEmail',
  password: 'srv.fieldPassword',
};

export function localizeServerText(text: string, field?: string, strict = false): string {
  const num = (re: RegExp, fallback: number) => Number(re.exec(text)?.[1] ?? fallback);
  if (/already exists|already taken|already registered|already in use/i.test(text)) {
    return t((field && FIELD_TAKEN[field]) || 'srv.alreadyExists');
  }
  if (/unable to log in|invalid credentials|invalid username or password|no active account|incorrect (username|password)/i.test(text)) {
    return t('srv.badCredentials');
  }
  if (/csrf/i.test(text)) return t('srv.csrf');
  if (/throttled|too many requests/i.test(text)) return t('srv.throttled');
  if (/authentication credentials were not provided|not authenticated/i.test(text)) return t('srv.notAuthed');
  if (/may not be (blank|null)|field is required/i.test(text)) {
    return t((field && FIELD_REQUIRED[field]) || 'srv.required');
  }
  if (/valid email/i.test(text)) return t('auth.v.emailInvalid');
  if (/valid username|may contain only/i.test(text)) return t('auth.v.usernameFormat');
  if (/too short|at least \d+ characters/i.test(text)) {
    return t('auth.v.passwordShort', { n: num(/(\d+) characters/i, 8) });
  }
  if (/too common|commonly used/i.test(text)) return t('srv.passwordCommon');
  if (/entirely numeric/i.test(text)) return t('auth.v.passwordNumeric');
  if (/too similar/i.test(text)) return t('srv.passwordSimilar');
  if (/no more than \d+ characters/i.test(text)) {
    return field === 'username' ? t('auth.v.usernameLong', { n: num(/no more than (\d+)/i, 150) }) : t('srv.tooLong');
  }
  if (!strict) return text;
  if (getLang() === 'ru' && CYRILLIC.test(text)) return text;
  return t((field && FIELD_FALLBACK[field]) || 'srv.unknown');
}

export function detailedMessage(error: unknown): string {
  const fields = Object.entries(fieldMessages(error));
  if (fields.length === 0) return messageOf(error);
  return fields.map(([name, text]) => `${name}: ${localizeServerText(text, name)}`).join('; ');
}

export function errorText(e: unknown): string {
  if (isRecord(e) && typeof e.error === 'string' && e.error) return e.error;
  return messageOf(e);
}

export function messageOf(error: unknown, strict = false): string {
  if (!isRecord(error)) return t('err.noReply');
  const { status, data } = error;
  if (status === 'FETCH_ERROR' || status === 'TIMEOUT_ERROR') return networkMessage();
  if (status === 'PARSING_ERROR') return t('err.notJson');
  const text = firstText(data);
  if (text) return localizeServerText(text, undefined, strict);
  if (status === 400) return t('err.badRequest');
  if (status === 401 || status === 403) return t('err.session');
  if (typeof status === 'number') return t('err.status', { status });
  if (typeof error.error === 'string') return error.error;
  return t('err.noReply');
}
