import { Input, Label, NumberField } from 'react-aria-components';
import styles from './CoordField.module.css';

interface CoordFieldProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  minValue: number;
  maxValue: number;
  invalid?: boolean;
}

export function CoordField({ label, value, onChange, minValue, maxValue, invalid = false }: CoordFieldProps) {
  return (
    <NumberField
      className={styles.root ?? ''}
      value={value}
      onChange={(next) => {
        if (Number.isFinite(next)) onChange(next);
      }}
      minValue={minValue}
      maxValue={maxValue}
      step={0.01}
      isInvalid={invalid}
      formatOptions={{ maximumFractionDigits: 4 }}
    >
      <Label className={styles.label}>{label}</Label>
      <div className={styles.group}>
        <Input className={styles.input ?? ''} inputMode="decimal" />
        <span className={styles.unit} aria-hidden="true">
          °
        </span>
      </div>
    </NumberField>
  );
}
