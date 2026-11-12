import { afterEach, expect, test } from 'vitest';
import { errorText, fieldMessages, localizeServerText, messageOf } from '../../shared/api/errors';
import { setLang } from '../../shared/i18n';
import { serverFieldErrors, validateRegistration } from './validate';

const ok = { username: 'neil_1969', email: 'neil@example.com', password: 'moonwalk77' };

test('a correct form has no errors', () => {
  expect(validateRegistration(ok)).toEqual({});
});

test('empty fields are reported', () => {
  expect(Object.keys(validateRegistration({ username: ' ', email: '', password: '' })).sort()).toEqual([
    'email',
    'password',
    'username',
  ]);
});

test('username, email and password rules', () => {
  expect(validateRegistration({ ...ok, username: 'a b' }).username).toBeDefined();
  expect(validateRegistration({ ...ok, username: 'x'.repeat(151) }).username).toBeDefined();
  expect(validateRegistration({ ...ok, username: 'Нил_1969' }).username).toBeUndefined();
  expect(validateRegistration({ ...ok, email: 'neil@example' }).email).toBeDefined();
  expect(validateRegistration({ ...ok, password: 'short1' }).password).toBeDefined();
  expect(validateRegistration({ ...ok, password: '1234567890' }).password).toBeDefined();
  expect(validateRegistration({ ...ok, password: 'NEIL_1969' }).password).toBeDefined();
});

test('server field errors are shown under their fields, including nested bodies', () => {
  const flat = { status: 400, data: { username: ['A user with that username already exists.'] } };
  expect(serverFieldErrors(flat).username).toContain('уже занято');
  const nested = { status: 400, data: { errors: { password: [{ message: 'Too common.', code: 'x' }] } } };
  expect(fieldMessages(nested)).toEqual({ password: 'Too common.' });
});

test('a 400 without readable text is explained, not just numbered', () => {
  expect(messageOf({ status: 400, data: {} })).toContain('Сервер отклонил данные');
  expect(messageOf({ status: 400, data: { errors: { email: ['Enter a valid email address.'] } } })).toContain(
    'name@example.com',
  );
});

afterEach(() => setLang('ru'));

test('server texts follow the page language', () => {
  const taken = 'A user with that username already exists.';
  expect(localizeServerText(taken, 'username')).toContain('уже занято');
  setLang('en');
  expect(localizeServerText(taken, 'username')).toContain('already taken');
  expect(localizeServerText('Unable to log in with provided credentials.')).toContain('Sign up');
  setLang('ru');
  expect(localizeServerText('Unable to log in with provided credentials.')).toContain('Регистрация');
});

test('an unknown English server text never reaches the screen in strict mode', () => {
  expect(localizeServerText('invalid (smth)', 'password', true)).toContain('Проверьте пароль');
  expect(localizeServerText('invalid (smth)', undefined, true)).toContain('Не удалось');
  setLang('en');
  expect(localizeServerText('invalid (smth)', 'email', true)).toContain('Check the email');
  expect(localizeServerText('Посадка разрешена только на Южном полюсе Луны')).toContain('Посадка');
});

test('errorText keeps the readable text a mutation already produced', () => {
  expect(errorText({ status: 'CUSTOM_ERROR', error: 'Площадка не найдена.' })).toBe('Площадка не найдена.');
  expect(errorText({ status: 403, data: {} })).toContain('сессия истекла');
});
