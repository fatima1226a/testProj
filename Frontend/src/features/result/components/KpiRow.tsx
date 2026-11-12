import { t } from '../../../shared/i18n';
import { formatNumber } from '../../../shared/lib/format';
import type { Result } from '../types';
import { KpiTile } from './KpiTile';
import styles from './KpiRow.module.css';

const show = (value: number | null | undefined, digits = 0): string | null =>
  value === null || value === undefined ? null : formatNumber(value, digits);

export function KpiRow({ result }: { result: Result | null }) {
  const kpi = result?.kpi;
  const minSoc = result?.limits.minSocPct ?? null;
  const duration = result?.limits.durationH ?? null;
  return (
    <dl className={styles.root}>
      <KpiTile
        label={t('kpi.minBattery')}
        value={show(kpi?.minBatteryPct, 1)}
        unit="%"
        warn={kpi?.minBatteryPct != null && minSoc !== null ? kpi.minBatteryPct < minSoc : false}
      />
      <KpiTile label={t('kpi.longestShadow')} value={show(kpi?.longestShadowH)} unit={t('kpi.unitH')} />
      <KpiTile
        label={t('kpi.earth')}
        value={show(kpi?.earthHours)}
        unit={duration !== null ? t('kpi.hOf', { n: formatNumber(duration) }) : t('kpi.unitH')}
      />
      <KpiTile label={t('kpi.sunlit')} value={show(kpi?.sunlitPct)} unit="%" />
    </dl>
  );
}
