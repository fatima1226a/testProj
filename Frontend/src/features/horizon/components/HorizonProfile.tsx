import { scaleLinear } from 'd3-scale';
import { t } from '../../../shared/i18n';
import { addHours } from '../../../shared/lib/format';
import { useElementWidth } from '../../../shared/lib/hooks';
import { Panel } from '../../../shared/ui/Panel';
import type { SiteInfo } from '../../datasets/types';
import type { Site } from '../../plan/types';
import type { HorizonPoint, HourSample, Result } from '../../result/types';
import { horizonAt, horizonPoints, skyAt, skyRange, trackPath, type SkyPoint } from '../sky';
import styles from './HorizonProfile.module.css';

const LEFT = 34;
const RIGHT = 10;
const TOP = 8;
const BOTTOM = 132;
const HEIGHT = 156;
const DEFAULT_DURATION_H = 24;

interface HorizonProfileProps {
  site: Site;
  dataSite: SiteInfo | null;
  landing: string;
  hour: number;
  result: Result | null;
  sample: HourSample | null;
  hint?: string | null;
}

function horizonEdges(horizon: HorizonPoint[]): { left: HorizonPoint; right: HorizonPoint } | null {
  const first = horizon[0];
  const last = horizon[horizon.length - 1];
  if (!first || !last) return null;
  const span = first.azDeg + 360 - last.azDeg;
  const share = span > 0 ? first.azDeg / span : 0;
  const el = first === last ? first.elDeg : last.elDeg + (first.elDeg - last.elDeg) * (1 - share);
  const at = first.azDeg === 0 ? first.elDeg : el;
  const end = last.azDeg === 360 ? last.elDeg : el;
  return { left: { azDeg: 0, elDeg: at }, right: { azDeg: 360, elDeg: end } };
}

export function HorizonProfile({ site, dataSite, landing, hour, result, sample, hint }: HorizonProfileProps) {
  const siteName = dataSite?.label ?? t('site.name');
  const [ref, width] = useElementWidth<HTMLDivElement>(480);
  const heights = dataSite?.horizon ?? null;
  const horizon: HorizonPoint[] = heights ? horizonPoints(heights) : site.horizon;

  const landingMs = Date.parse(landing);
  const track = dataSite?.sky ?? null;
  const durationH = result?.limits.durationH ?? (result ? Math.max(1, result.hours.length - 1) : DEFAULT_DURATION_H);
  const range: SkyPoint[] = track && Number.isFinite(landingMs) ? skyRange(track, landingMs, durationH) : [];
  const now = track && Number.isFinite(landingMs) ? skyAt(track, Date.parse(addHours(landing, hour))) : null;
  const cyclic = now?.cyclic ?? false;

  const sun = now
    ? { az: now.point.sunAz, el: now.point.sunEl }
    : { az: sample?.sunAzDeg ?? null, el: sample?.sunElDeg ?? null };
  const earth = now
    ? { az: now.point.earthAz, el: now.point.earthEl }
    : { az: sample?.earthAzDeg ?? null, el: sample?.earthElDeg ?? null };
  const behind = (p: { az: number | null; el: number | null }): boolean =>
    p.az !== null && p.el !== null && p.el < (heights ? horizonAt(heights, p.az) : 0);
  const sunHidden = now ? behind(sun) : sample ? !sample.sun : false;
  const earthHidden = now ? behind(earth) : sample?.earth === false;

  const sunPoints = range.length > 0
    ? range.map((p) => ({ az: p.sunAz, el: p.sunEl }))
    : (result?.hours ?? []).map((h) => ({ az: h.sunAzDeg, el: h.sunElDeg }));
  const levels = [
    ...horizon.map((p) => p.elDeg),
    ...sunPoints.flatMap((p) => (p.el === null ? [] : [p.el])),
    ...[sun.el, earth.el].flatMap((v) => (v === null ? [] : [v])),
  ];
  const top = Math.ceil(Math.max(...levels, 4));
  const bottom = Math.min(-1, Math.floor(Math.min(...levels, 0)));
  const x = scaleLinear().domain([0, 360]).range([LEFT, Math.max(LEFT + 1, width - RIGHT)]);
  const y = scaleLinear().domain([bottom, top]).range([BOTTOM, TOP]);
  const edges = horizonEdges(horizon);
  const drawn = edges ? [edges.left, ...horizon, edges.right] : [];
  const line = drawn.map((p, i) => `${i ? 'L' : 'M'}${x(p.azDeg).toFixed(1)},${y(p.elDeg).toFixed(1)}`).join('');
  const area = edges ? `${line}L${x(360).toFixed(1)},${y(bottom).toFixed(1)}L${x(0).toFixed(1)},${y(bottom).toFixed(1)}Z` : '';
  const path = trackPath(sunPoints, x, y);

  return (
    <Panel num="05" title={t('hz.title')} aside={<span className={styles.aside}>{siteName}</span>}>
      <div ref={ref} className={styles.chart}>
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={t('hz.aria', { site: siteName })}
          className={styles.svg}
        >
          {y.ticks(4).map((v) => (
            <g key={v}>
              <line x1={LEFT} x2={x(360)} y1={y(v)} y2={y(v)} className={v === 0 ? styles.zero : styles.grid} />
              <text x={LEFT - 6} y={y(v) + 4} textAnchor="end" className={styles.tick}>
                {v}°
              </text>
            </g>
          ))}
          {area && <path d={area} className={styles.area} />}
          {line && <path d={line} className={styles.line} />}
          {path && <path d={path} className={styles.path} />}
          {sun.az !== null && sun.el !== null && (
            <circle cx={x(sun.az)} cy={y(sun.el)} r={5} className={sunHidden ? styles.sunHidden : styles.sun} />
          )}
          {earth.az !== null && earth.el !== null && (
            <circle cx={x(earth.az)} cy={y(earth.el)} r={5} className={earthHidden ? styles.earthHidden : styles.earth} />
          )}
          {[0, 90, 180, 270, 360].map((az) => (
            <text key={az} x={x(az)} y={HEIGHT - 6} textAnchor={az === 0 ? 'start' : az === 360 ? 'end' : 'middle'} className={styles.tick}>
              {az}°
            </text>
          ))}
        </svg>
      </div>
      {horizon.length === 0 && <p className={styles.empty}>{hint ? t(hint) : t('hz.none')}</p>}
      {cyclic && <p className={styles.empty}>{t('hz.cyclic')}</p>}
      <ul className={styles.legend}>
        <li>
          <i className={styles.keyLine} /> {t('hz.terrain')}
        </li>
        <li>
          <i className={styles.keyPath} /> {t('hz.sunPath')}
        </li>
        <li className={styles.legendSun}>{t('hz.sun')}</li>
        <li className={styles.legendEarth}>{t('hz.earth')}</li>
        <li>{t('hz.hidden')}</li>
      </ul>
    </Panel>
  );
}
