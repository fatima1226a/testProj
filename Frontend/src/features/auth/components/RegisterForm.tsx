import { useRef, useState } from 'react';
import { t, useLang } from '../../../shared/i18n';
import { Button } from '../../../shared/ui/Button';
import { useRegisterMutation } from '../authApi';
import {
  serverFieldErrors,
  validateRegistration,
  type FieldErrors,
  type RegisterField,
} from '../validate';
import styles from './AuthForm.module.css';

interface RegisterFormProps {
  onDone: () => void;
  onSwitch: () => void;
}

const FIELDS: RegisterField[] = ['username', 'email', 'password'];

export function RegisterForm({ onDone, onSwitch }: RegisterFormProps) {
  useLang();
  const [values, setValues] = useState<Record<RegisterField, string>>({ username: '', email: '', password: '' });
  const [touched, setTouched] = useState<Partial<Record<RegisterField, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [server, setServer] = useState<FieldErrors>({});
  const inputs = useRef<Partial<Record<RegisterField, HTMLInputElement | null>>>({});
  const [register, { isLoading, error }] = useRegisterMutation();

  const local = validateRegistration(values);
  const shown = (field: RegisterField): string | undefined =>
    (touched[field] || submitted ? local[field] : undefined) ?? server[field];
  const hasServerField = FIELDS.some((field) => server[field]);
  const generic =
    !hasServerField && error && 'error' in error && typeof error.error === 'string' ? error.error : null;

  const change = (field: RegisterField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setServer((prev) => ({ ...prev, [field]: undefined }));
  };

  const submit = async () => {
    setSubmitted(true);
    const firstBad = FIELDS.find((field) => local[field]);
    if (firstBad) {
      inputs.current[firstBad]?.focus();
      return;
    }
    try {
      await register({
        username: values.username.trim(),
        email: values.email.trim(),
        password: values.password,
      }).unwrap();
      onDone();
    } catch (e) {
      const fields = serverFieldErrors(e);
      setServer(fields);
      const first = FIELDS.find((field) => fields[field]);
      if (first) inputs.current[first]?.focus();
    }
  };

  const field = (name: RegisterField, label: string, props: { type?: string; autoComplete: string }) => {
    const message = shown(name);
    const errorId = `register-${name}-error`;
    return (
      <label className={styles.field}>
        <span>{label}</span>
        <input
          ref={(el) => {
            inputs.current[name] = el;
          }}
          className={styles.input}
          type={props.type}
          value={values[name]}
          autoComplete={props.autoComplete}
          required
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          onChange={(e) => change(name, e.target.value)}
          onBlur={() => setTouched((prev) => ({ ...prev, [name]: true }))}
        />
        {message && (
          <span id={errorId} className={styles.fieldError} role="alert">
            {message}
          </span>
        )}
      </label>
    );
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
      {field('username', t('auth.username'), { autoComplete: 'username' })}
      {field('email', t('auth.email'), { type: 'email', autoComplete: 'email' })}
      {field('password', t('auth.password'), { type: 'password', autoComplete: 'new-password' })}
      {generic && (
        <p className={styles.error} role="alert">
          {generic}
        </p>
      )}
      <Button type="submit" variant="primary" wide isDisabled={isLoading}>
        {isLoading ? t('auth.creating') : t('auth.create')}
      </Button>
      <p className={styles.switch}>
        {t('auth.haveAccount')}{' '}
        <Button variant="ghost" size="s" onPress={onSwitch}>
          {t('auth.signIn')}
        </Button>
      </p>
    </form>
  );
}
