import type { ReactNode } from 'react';
import { t, type MsgKey } from '../../../shared/i18n';
import { formatNumber } from '../../../shared/lib/format';
import { NumText } from '../../../shared/ui/NumText';
import { Panel } from '../../../shared/ui/Panel';
import type { SiteSurvival } from '../../survival/types';
import { formatTransit, landingKeepingTransit, transitHours } from '../dates';
import type { Limits } from '../../result/types';
import { DATE_MAX, DATE_MIN, SURVIVAL_DAYS } from '../defaults';
import type { Plan, PlanErrors } from '../types';
import { DateField } from './DateField';
import { CoordsSection } from './CoordsSection';
import styles from './MissionPanel.module.css';

interface MissionPanelProps {
  plan: Plan;
  errors: PlanErrors;
  onChange: (patch: Partial<Plan>) => void;
  survival?: SiteSurvival | null;
  collapsible?: boolean;
}

const DEVICE_ROWS: [keyof Limits, MsgKey, MsgKey | '%' | '°', number][] = [
  ['panelW', 'dev.panelW', 'unit.w', 0],
  ['systemsW', 'dev.systemsW', 'unit.w', 0],
  ['heaterW', 'dev.heaterW', 'unit.w', 0],
  ['capacityWh', 'dev.capacityWh', 'unit.wh', 0],
  ['initialSocPct', 'dev.initialSocPct', '%', 0],
  ['minSocPct', 'dev.minSocPct', '%', 0],
  ['maxSlopeDeg', 'dev.maxSlopeDeg', '°', 0],
];

export function MissionPanel({
  plan,
  errors,
  onChange,
  survival = null,
  collapsible = false,
}: MissionPanelProps) {
  const limits = survival?.result?.sim?.limits ?? null;
  const duration = limits?.durationH ?? null;
  const body = (
    <div className={styles.body}>
      <CoordsSection
        plan={plan}
        survival={survival}
        onCoordChange={(coord) => onChange({ coord })}
      />

      <div className={styles.group}>
        <DateField
          label={t('plan.startDate')}
          value={plan.start}
          onChange={(start) => onChange({ start, landing: landingKeepingTransit(plan, start) })}
          minDate={DATE_MIN}
          maxDate={DATE_MAX}
          error={errors.start}
        />
        <DateField
          label={t('plan.landingDate')}
          value={plan.landing}
          onChange={(landing) => onChange({ landing })}
          minDate={plan.start.slice(0, 10)}
          maxDate={DATE_MAX}
          error={errors.landing}
        />
        <p className={styles.duration}>
          <span>{t('plan.transit')}</span>
          <strong>{formatTransit(transitHours(plan.start, plan.landing))}</strong>
        </p>
        <p className={styles.requirement}>{t('plan.requirement', { days: SURVIVAL_DAYS })}</p>
        <p className={styles.duration}>
          <span>{t('plan.onSurface')}</span>
          <strong>
            {duration === null ? '—' : <NumText>{t('plan.hoursCalc', { n: formatNumber(duration) })}</NumText>}
          </strong>
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.group}>
        <h3 className={styles.groupLabel}>{t('plan.device')}</h3>
        {DEVICE_ROWS.map(([key, labelKey, unitKey, digits]) => {
          const unit = unitKey === '%' || unitKey === '°' ? unitKey : t(unitKey);
          const value = limits?.[key] ?? null;
          return (
            <p key={key} className={styles.duration}>
              <span>{t(labelKey)}</span>
              <strong>
                {value === null ? '—' : <NumText>{`${formatNumber(value, digits)} ${unit}`}</NumText>}
              </strong>
            </p>
          );
        })}
      </div>

      <p className={styles.note}>
        {t('plan.deviceNote')}
      </p>
    </div>
  );

  return collapsible ? <Collapsible>{body}</Collapsible> : (
    <Panel num="01" title={t('plan.title')}>
      {body}
    </Panel>
  );
}

function Collapsible({ children }: { children: ReactNode }) {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        <span className={styles.num}>01</span>
        {t('plan.collapsibleTitle')}
        <span className={styles.hint}>{t('plan.collapsibleHint')}</span>
      </summary>
      {children}
    </details>
  );
}
