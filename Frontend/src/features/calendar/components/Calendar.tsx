import { t } from '../../../shared/i18n';
import { formatMonth, formatUtc } from '../../../shared/lib/format';
import { useMediaQuery } from '../../../shared/lib/hooks';
import { Panel } from '../../../shared/ui/Panel';
import type { Plan } from '../../plan/types';
import type { CalendarCellData } from '../../result/calendar';
import { CalendarCell } from './CalendarCell';
import styles from './Calendar.module.css';

interface CalendarProps {
  plan: Plan;
  cells: CalendarCellData[];
  onSelect: (landing: string) => void;
}

const monthOf = formatMonth;

export function Calendar({ plan, cells, onSelect }: CalendarProps) {
  const narrow = useMediaQuery('(max-width: 767px)');
  const size = narrow ? 7 : 15;
  const dates = cells.map((c) => c.landing);
  const groups = Array.from({ length: Math.ceil(dates.length / size) }, (_, g) =>
    dates.slice(g * size, (g + 1) * size),
  );
  const hour = String(new Date(plan.landing).getUTCHours()).padStart(2, '0');
  const month = Number.isFinite(Date.parse(plan.landing)) ? monthOf(plan.landing) : '—';

  return (
    <Panel
      num="06"
      title={t('cal.title')}
      aside={<span className={styles.aside}>{t('cal.aside', { month, hour })}</span>}
    >
      <h4 className={styles.siteTitle}>{t('cal.site')}</h4>
      <div className={styles.groups}>
        {groups.map((group) => (
          <div
            key={group[0]}
            className={styles.grid}
            style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}
            role="group"
            aria-label={t('cal.groupAria', {
              from: new Date(group[0] ?? '').getUTCDate(),
              to: new Date(group[group.length - 1] ?? '').getUTCDate(),
              month: monthOf(group[0] ?? plan.landing),
            })}
          >
            {group.map((landing) => (
              <span key={landing} className={styles.day}>
                {new Date(landing).getUTCDate()}
              </span>
            ))}
            {group.map((landing) => {
              const cell = cells.find((c) => c.landing === landing);
              return cell ? (
                <CalendarCell
                  key={landing}
                  cell={cell}
                  selected={plan.landing === landing}
                  onSelect={() => onSelect(landing)}
                />
              ) : (
                <span key={landing} />
              );
            })}
          </div>
        ))}
      </div>
      <ul className={styles.legend}>
        <li>
          <i className={styles.keyOk} /> {t('cal.keyOk')}
        </li>
        <li>
          <i className={styles.keyBattery} /> {t('cal.keyBattery')}
        </li>
        <li>
          <i className={styles.keyEarth} /> {t('cal.keyTerrain')}
        </li>
        <li>
          <i className={styles.keyEarth} /> {t('cal.keyOther')}
        </li>
      </ul>
      {cells.length === 0 && (
        <p className={styles.note} aria-live="polite">
          {t('cal.loading')}
        </p>
      )}
      <p className={styles.note}>
        {t('cal.note', { date: formatUtc(plan.landing) })}
      </p>
    </Panel>
  );
}
