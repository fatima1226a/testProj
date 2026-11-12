import { useRef, useState } from 'react';
import { t, useLang } from '../../../shared/i18n';
import { Button } from '../../../shared/ui/Button';
import { useLoginMutation } from '../authApi';
import { validateLogin } from '../validate';
import styles from './AuthForm.module.css';

interface LoginFormProps {
  onDone: () => void;
  onSwitch: () => void;
}

export function LoginForm({ onDone, onSwitch }: LoginFormProps) {
  useLang();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const userRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);
  const [login, { isLoading, error }] = useLoginMutation();
  const message = error && 'error' in error && typeof error.error === 'string' ? error.error : null;
  const local = submitted ? validateLogin({ username, password }) : {};

  const submit = async () => {
    setSubmitted(true);
    const problems = validateLogin({ username, password });
    if (problems.username) return userRef.current?.focus();
    if (problems.password) return passRef.current?.focus();
    try {
      await login({ username: username.trim(), password }).unwrap();
      onDone();
    } catch {
    }
  };

  return (
    <form
      className={styles.form}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label className={styles.field}>
        <span>{t('auth.username')}</span>
        <input
          ref={userRef}
          className={styles.input}
          value={username}
          autoComplete="username"
          required
          aria-invalid={local.username ? true : undefined}
          aria-describedby={local.username ? 'login-username-error' : undefined}
          onChange={(e) => setUsername(e.target.value)}
        />
        {local.username && (
          <span id="login-username-error" className={styles.fieldError} role="alert">
            {local.username}
          </span>
        )}
      </label>
      <label className={styles.field}>
        <span>{t('auth.password')}</span>
        <input
          ref={passRef}
          className={styles.input}
          type="password"
          value={password}
          autoComplete="current-password"
          required
          aria-invalid={local.password ? true : undefined}
          aria-describedby={local.password ? 'login-password-error' : undefined}
          onChange={(e) => setPassword(e.target.value)}
        />
        {local.password && (
          <span id="login-password-error" className={styles.fieldError} role="alert">
            {local.password}
          </span>
        )}
      </label>
      {message && (
        <p className={styles.error} role="alert">
          {message}
        </p>
      )}
      <Button type="submit" variant="primary" wide isDisabled={isLoading}>
        {isLoading ? t('auth.signingIn') : t('auth.signIn')}
      </Button>
      <p className={styles.switch}>
        {t('auth.noAccount')}{' '}
        <Button variant="ghost" size="s" onPress={onSwitch}>
          {t('auth.signUp')}
        </Button>
      </p>
    </form>
  );
}
