import { t } from '../../shared/i18n';
import { fieldMessages, localizeServerText } from '../../shared/api/errors';

export type RegisterField = 'username' | 'email' | 'password';
export type FieldErrors = Partial<Record<RegisterField, string>>;

export const USERNAME_MAX = 150;
export const PASSWORD_MIN = 8;

const USERNAME_PATTERN = /^[\p{L}\p{N}_.@+-]+$/u;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function validateRegistration(form: Record<RegisterField, string>): FieldErrors {
  const errors: FieldErrors = {};
  const username = form.username.trim();
  const email = form.email.trim();
  const { password } = form;

  if (!username) errors.username = t('auth.v.usernameRequired');
  else if (username.length > USERNAME_MAX) errors.username = t('auth.v.usernameLong', { n: USERNAME_MAX });
  else if (!USERNAME_PATTERN.test(username)) errors.username = t('auth.v.usernameFormat');

  if (!email) errors.email = t('auth.v.emailRequired');
  else if (email.length > 254 || !EMAIL_PATTERN.test(email)) errors.email = t('auth.v.emailInvalid');

  if (!password) errors.password = t('auth.v.passwordRequired');
  else if (password.length < PASSWORD_MIN) errors.password = t('auth.v.passwordShort', { n: PASSWORD_MIN });
  else if (/^\d+$/.test(password)) errors.password = t('auth.v.passwordNumeric');
  else if (username && password.toLowerCase() === username.toLowerCase()) {
    errors.password = t('auth.v.passwordSameAsName');
  }
  return errors;
}

export function serverFieldErrors(error: unknown): FieldErrors {
  const all = fieldMessages(error);
  const out: FieldErrors = {};
  for (const field of ['username', 'email', 'password'] as const) {
    const text = all[field];
    if (text) out[field] = localizeServerText(text, field, true);
  }
  return out;
}

export function validateLogin(form: { username: string; password: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (!form.username.trim()) errors.username = t('auth.v.usernameRequired');
  if (!form.password) errors.password = t('auth.v.passwordRequired');
  return errors;
}
