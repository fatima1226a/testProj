import { t } from '../../../shared/i18n';
import styles from './KpiTile.module.css';

interface KpiTileProps {
  label: string;
  value: string | null;
  unit: string;
  warn?: boolean;
}

export function KpiTile({ label, value, unit, warn = false }: KpiTileProps) {
  return (
    <div className={`${styles.root} ${warn ? styles.warn : ''}`}>
      <dt className={styles.label}>
        {label}
        {warn && <span className={styles.flag}>{t('kpi.over')}</span>}
      </dt>
      <dd className={styles.value}>
        <span className={styles.number}>{value ?? '—'}</span> <span className={styles.unit}>{unit}</span>
      </dd>
    </div>
  );
}
