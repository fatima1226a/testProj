import { useId } from 'react';
import { t } from '../../../shared/i18n';
import { datePart, hourPart, isoFromParts } from '../../../shared/lib/format';
import styles from './DateField.module.css';

interface DateFieldProps {
  label: string;
  value: string;
  onChange: (iso: string) => void;
  minDate: string;
  maxDate: string;
  error?: string | undefined;
}

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export function DateField({ label, value, onChange, minDate, maxDate, error }: DateFieldProps) {
  const dateId = useId();
  const hourId = useId();
  const errorId = useId();
  const date = datePart(value);
  const hour = hourPart(value);

  return (
    <div className={styles.root}>
      <div className={styles.row}>
        <div className={styles.cell}>
          <label htmlFor={dateId} className={styles.label}>
            {label}
          </label>
          <input
            id={dateId}
            type="date"
            className={styles.input}
            value={date}
            min={minDate}
            max={maxDate}
            required
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            onChange={(e) => {
              if (e.target.value) onChange(isoFromParts(e.target.value, hour));
            }}
          />
        </div>
        <div className={styles.cell}>
          <label htmlFor={hourId} className={styles.label}>
            {t('plan.hourUtc')}
          </label>
          <select
            id={hourId}
            className={styles.input}
            value={hour}
            onChange={(e) => onChange(isoFromParts(date, Number(e.target.value)))}
          >
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, '0')}:00
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
