import { t } from '../../../shared/i18n';
import { formatNumber } from '../../../shared/lib/format';
import { stateLabel, type SceneSnapshot } from '../sceneState';
import { Lander } from './Lander';
import { Sky } from './Sky';
import { StateBadge } from './StateBadge';
import { Terrain } from './Terrain';
import styles from './Scene.module.css';

interface SceneProps {
  hour: number;
  snapshot: SceneSnapshot | null;
}

export function Scene({ hour, snapshot }: SceneProps) {
  const state = snapshot?.state;
  const siteName = t('site.name');
  return (
    <section className={styles.root} aria-label={t('scene.aria')}>
      <div className={styles.stage} data-state={state ?? 'loading'}>
        <svg
          className={styles.svg}
          viewBox="0 0 700 300"
          preserveAspectRatio="xMidYMid slice"
          role="img"
          aria-label={
            snapshot
              ? t('scene.landerAria', { site: siteName, hour, state: stateLabel(snapshot.state) })
              : t('scene.unavailable')
          }
        >
          {snapshot && <Sky sample={snapshot.sample} />}
          <Terrain />
          {snapshot && <Lander state={snapshot.state} />}
        </svg>
        <div className={styles.top}>
          <span>{siteName.toUpperCase()}</span>
          <span className={styles.hour}>{t('scene.hour', { hour: String(hour).padStart(3, '0') })}</span>
        </div>
        <div className={styles.bottom}>
          {snapshot ? <StateBadge snapshot={snapshot} /> : <span className={styles.skeleton} />}
          <span className={styles.caption}>
            {t('scene.caption1')}
            <br />
            {t('scene.caption2')}
          </span>
        </div>
      </div>
      <dl className={styles.footer}>
        <div>
          <dt>{t('scene.sun')}</dt>
          <dd>{snapshot ? t(snapshot.sample.sun ? 'scene.sunLight' : 'scene.sunShade') : '—'}</dd>
        </div>
        <div>
          <dt>{t('scene.earth')}</dt>
          <dd>
            {snapshot
              ? snapshot.sample.earth === null
                ? '—'
                : snapshot.sample.earth
                  ? t('scene.earthVisible')
                  : t('scene.earthHidden')
              : '—'}
          </dd>
        </div>
        <div>
          <dt>{t('scene.temp')}</dt>
          <dd className={styles.value}>
            {snapshot?.sample.temperatureC != null ? `${formatNumber(snapshot.sample.temperatureC, 0)} °C` : '—'}
          </dd>
        </div>
        <div>
          <dt>{t('scene.battery')}</dt>
          <dd className={styles.value}>{snapshot ? `${formatNumber(snapshot.batteryPct, 1)} %` : '—'}</dd>
        </div>
      </dl>
    </section>
  );
}
