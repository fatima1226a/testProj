import type { CSSProperties } from 'react';
import { t } from '../../../shared/i18n';
import { formatDay, formatNumber } from '../../../shared/lib/format';
import type { CalendarCellData } from '../../result/calendar';
import styles from './CalendarCell.module.css';

const mark = (status: CalendarCellData['status']): string =>
  status === 'ok' ? '✓' : status === 'battery' ? t('cell.markBattery') : status === 'terrain' ? t('cell.markTerrain') : '✕';

const STATUS_KEY = {
  ok: 'cell.ok',
  battery: 'cell.battery',
  terrain: 'cell.terrain',
  other: 'cell.other',
} as const;

interface CalendarCellProps {
  cell: CalendarCellData;
  selected: boolean;
  onSelect: () => void;
}

export function CalendarCell({ cell, selected, onSelect }: CalendarCellProps) {
  const reserve = Math.max(0, Math.min(1, (cell.marginPct ?? 0) / 70));
  return (
    <button
      type="button"
      className={styles.root}
      data-status={cell.status}
      aria-pressed={selected}
      aria-label={t('cell.aria', {
        day: formatDay(cell.landing),
        status: t(STATUS_KEY[cell.status]),
        margin: cell.marginPct === null ? '' : t('cell.margin', { n: formatNumber(cell.marginPct, 1) }),
      })}
      style={{ '--reserve': `${Math.round(20 + reserve * 60)}%` } as CSSProperties}
      onClick={onSelect}
    >
      {mark(cell.status)}
    </button>
  );
}
