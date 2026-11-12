import { t } from '../../../shared/i18n';
import { formatNumber } from '../../../shared/lib/format';
import { NumText } from '../../../shared/ui/NumText';
import { formatScalar, isRecord, isScalar } from '../dataFormat';
import { AXIS_KEYS, keyLabel } from '../labels';
import { Sparkline } from './Sparkline';
import styles from './DataView.module.css';

const MAX_DEPTH = 3;
const MAX_SERIES = 4;

function numericSeries(items: Record<string, unknown>[]): [string, number[]][] {
  const first = items[0];
  if (!first) return [];
  return Object.keys(first)
    .filter((key) => !AXIS_KEYS.has(key.toLowerCase()))
    .filter((key) => items.every((item) => typeof item[key] === 'number' && Number.isFinite(item[key])))
    .slice(0, MAX_SERIES)
    .map((key) => [key, items.map((item) => item[key] as number)]);
}

const hasLatLon = (item: Record<string, unknown>) =>
  ['lat', 'latitude'].some((k) => typeof item[k] === 'number') &&
  ['lon', 'lng', 'longitude'].some((k) => typeof item[k] === 'number');

function ArrayView({ items, depth }: { items: unknown[]; depth: number }) {
  if (items.length === 0) return <span>—</span>;

  if (items.every((v) => typeof v === 'number') && items.length >= 3) {
    return <Sparkline label={t('data.series')} values={items as number[]} />;
  }

  if (items.every(isRecord)) {
    const records = items as Record<string, unknown>[];
    if (records.every(hasLatLon)) {
      return <NumText>{t('data.route', { n: formatNumber(records.length) })}</NumText>;
    }
    const series = records.length >= 3 ? numericSeries(records) : [];
    if (series.length > 0) {
      return (
        <div className={styles.series}>
          {series.map(([key, values]) => (
            <Sparkline key={key} label={keyLabel(key)} values={values} />
          ))}
          <span className={styles.count}>
            <NumText>{t('data.points', { n: formatNumber(records.length) })}</NumText>
          </span>
        </div>
      );
    }
  }

  if (items.every(isScalar)) return <NumText>{items.map(formatScalar).join(', ')}</NumText>;

  return (
    <ol className={styles.list}>
      {items.map((item, i) => (
        <li key={i}>
          <DataView value={item} depth={depth + 1} />
        </li>
      ))}
    </ol>
  );
}

export function DataView({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (Array.isArray(value)) return <ArrayView items={value} depth={depth} />;
  if (isRecord(value)) {
    if (depth >= MAX_DEPTH) return <code className={styles.raw}>{JSON.stringify(value)}</code>;
    const entries = Object.entries(value);
    if (entries.length === 0) return <span>—</span>;
    return (
      <dl className={styles.dl}>
        {entries.map(([key, v]) => (
          <div key={key} className={isScalar(v) ? styles.row : styles.block}>
            <dt>{keyLabel(key)}</dt>
            <dd>
              <DataView value={v} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  if (typeof value === 'number') return <span className={styles.value}>{formatScalar(value)}</span>;
  return <span>{formatScalar(value)}</span>;
}
