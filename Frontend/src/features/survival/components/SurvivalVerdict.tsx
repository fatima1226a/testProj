import { t } from '../../../shared/i18n';
import type { SiteSurvival } from '../types';
import styles from './SurvivalVerdict.module.css';

const WORD = {
  loading: 'verdict.loading',
  ok: 'verdict.ok',
  fail: 'verdict.fail',
  north: 'verdict.fail',
  error: 'verdict.error',
} as const;

export function SurvivalVerdict({ site }: { site: SiteSurvival }) {
  const loading = site.status === 'loading';
  const bad = site.status === 'fail' || site.status === 'north';

  let tone: 'ok' | 'fail' | 'wait' = 'wait';
  let title = t('verdict.checking');
  if (bad) {
    tone = 'fail';
    title = t('verdict.bad');
  } else if (site.status === 'ok') {
    tone = 'ok';
    title = t('verdict.good');
  } else if (!loading) {
    title = t('verdict.noReply');
  }

  return (
    <div key={tone} className={`${styles.root} ${styles[tone]}`} aria-live="polite" aria-busy={loading}>
      <p className={styles.title}>
        <span aria-hidden="true">{tone === 'ok' ? '●' : tone === 'fail' ? '✕' : '…'}</span>
        {title}
      </p>
      <ul className={styles.sites}>
        <li data-status={site.status}>
          {t('verdict.lander')} <strong>{t(WORD[site.status])}</strong>
        </li>
      </ul>
    </div>
  );
}
