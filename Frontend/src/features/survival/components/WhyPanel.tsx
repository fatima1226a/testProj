import { t, tm } from '../../../shared/i18n';
import { NumText } from '../../../shared/ui/NumText';
import { Panel } from '../../../shared/ui/Panel';
import { outsideMessage } from '../coords';
import type { SiteSurvival } from '../types';
import { previewOf } from '../dataFormat';
import { DataView } from './DataView';
import styles from './WhyPanel.module.css';

interface WhyPanelProps {
  site: SiteSurvival;
}

export function WhyPanel({ site }: WhyPanelProps) {
  return (
    <Panel num="03" title={t('why.title')}>
      <SiteWhy site={site} />
    </Panel>
  );
}

function SiteWhy({ site }: { site: SiteSurvival }) {
  if (site.status === 'loading') return <p className={styles.empty}>{t('why.wait')}</p>;
  if (site.status === 'error') return <p className={styles.empty}>{site.message}</p>;
  if (site.status === 'north') {
    return (
      <ol className={styles.list}>
        <li className={styles.item}>
          <span className={styles.count}>01</span>
          <span className={styles.content}>
            <strong className={styles.title}>{t('why.outside')}</strong>
            <span className={styles.text}>{outsideMessage()}</span>
          </span>
        </li>
      </ol>
    );
  }
  const result = site.result;
  if (!result) return <p className={styles.empty}>{t('why.noExplain')}</p>;

  return (
    <div className={styles.body}>
      <p className={result.survives ? styles.ok : styles.fail}>
        {t(result.survives ? 'why.survives' : 'why.fails')}
      </p>

      {result.assumptions.length === 0 ? (
        <p className={styles.empty}>{t('why.none')}</p>
      ) : (
        <ol className={styles.list}>
          {result.assumptions.map((item, i) => (
            <li key={i} className={styles.item}>
              <span className={styles.count}>{String(i + 1).padStart(2, '0')}</span>
              <span className={styles.content}>
                {item.title && <strong className={styles.title}>{tm(item.title)}</strong>}
                <span className={styles.text}>
                  <NumText>{tm(item.text)}</NumText>
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}

      {result.sections.length > 0 && (
        <div className={styles.more}>
          <h3 className={styles.moreTitle}>{t('why.data')}</h3>
          {result.sections.map((section, i) => (
            <details key={`${section.id}-${i}`} className={styles.section}>
              <summary className={styles.summary}>
                <span>{tm(section.title)}</span>
                <span className={styles.preview}>
                  <NumText>{previewOf(section.data)}</NumText>
                </span>
              </summary>
              <div className={styles.data}>
                <DataView value={section.data} />
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
