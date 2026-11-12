import { t } from '../../../shared/i18n';
import { formatNumber } from '../../../shared/lib/format';
import { NumText } from '../../../shared/ui/NumText';
import styles from './Sparkline.module.css';

interface SparklineProps {
  label: string;
  values: number[];
}

const W = 100;
const H = 28;

export function Sparkline({ label, values }: SparklineProps) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - 2 - ((v - min) / span) * (H - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  const digits = Number.isInteger(min) && Number.isInteger(max) ? 0 : 1;
  const summary = t('spark.range', { min: formatNumber(min, digits), max: formatNumber(max, digits) });
  return (
    <figure className={styles.root}>
      <figcaption className={styles.caption}>
        <span>{label}</span>
        <span className={styles.range}>
          <NumText>{summary}</NumText>
        </span>
      </figcaption>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={t('spark.aria', { label, summary, n: values.length })}
      >
        <polyline points={points} />
      </svg>
    </figure>
  );
}
