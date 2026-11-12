import { t, type MsgKey } from '../../../shared/i18n';
import { Badge, type BadgeTone } from '../../../shared/ui/Badge';
import { LAT_RANGE, LON_RANGE } from '../../survival/coords';
import type { SiteStatus, SiteSurvival } from '../../survival/types';
import type { Coord, Plan } from '../types';
import { CoordField } from './CoordField';
import styles from './CoordsSection.module.css';

interface CoordsSectionProps {
  plan: Plan;
  survival: SiteSurvival | null;
  onCoordChange: (coord: Coord) => void;
}

const BADGE: Record<SiteStatus, { tone: BadgeTone; label: MsgKey }> = {
  loading: { tone: 'neutral', label: 'badge.loading' },
  ok: { tone: 'ok', label: 'badge.ok' },
  fail: { tone: 'fail', label: 'badge.fail' },
  north: { tone: 'fail', label: 'badge.fail' },
  error: { tone: 'neutral', label: 'badge.error' },
};

export function CoordsSection({ plan, survival, onCoordChange }: CoordsSectionProps) {
  const coord = plan.coord;
  const bad = survival?.status === 'fail' || survival?.status === 'north';
  const badge = survival ? BADGE[survival.status] : null;

  return (
    <fieldset className={styles.root}>
      <legend className={styles.legend}>{t('plan.coordsLegend')}</legend>
      <div className={styles.box} data-bad={bad ? '' : undefined}>
        {badge && (
          <div className={styles.head}>
            <span className={styles.label}>{t('plan.calc')}</span>
            <Badge tone={badge.tone}>{t(badge.label)}</Badge>
          </div>
        )}
        <div className={styles.fields}>
          <CoordField
            label={t('plan.lat')}
            value={coord.latDeg}
            minValue={LAT_RANGE.min}
            maxValue={LAT_RANGE.max}
            invalid={survival?.status === 'north'}
            onChange={(latDeg) => onCoordChange({ ...coord, latDeg })}
          />
          <CoordField
            label={t('plan.lon')}
            value={coord.lonDeg}
            minValue={LON_RANGE.min}
            maxValue={LON_RANGE.max}
            onChange={(lonDeg) => onCoordChange({ ...coord, lonDeg })}
          />
        </div>
        {survival?.status === 'north' && (
          <p className={styles.problem} role="alert">
            {survival.message}
          </p>
        )}
        {survival?.status === 'error' && <p className={styles.problem}>{survival.message}</p>}
      </div>
      <p className={styles.hint}>{t('plan.coordsHint')}</p>
    </fieldset>
  );
}
