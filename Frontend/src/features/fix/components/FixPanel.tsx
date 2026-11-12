import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { t } from '../../../shared/i18n';
import { formatUtc } from '../../../shared/lib/format';
import { Button } from '../../../shared/ui/Button';
import { Panel } from '../../../shared/ui/Panel';
import { formatCoord } from '../../survival/coords';
import { needsFix, type CoordinateFix, type DateOffer } from '../../survival/useSurvival';
import type { SiteSurvival } from '../../survival/types';
import styles from './FixPanel.module.css';

interface FixPanelProps {
  site: SiteSurvival;
  coordsKey: string;
  fix: CoordinateFix;
}

const MAX_LIFT = 1.3;
const MARGIN = 32;
const FLIGHT_MS = 420;
const EASE = 'cubic-bezier(0.2, 0.7, 0.2, 1)';

interface Size {
  w: number;
  h: number;
}

function liftScale({ w, h }: Size): number {
  if (w <= 0 || h <= 0) return 1;
  return Math.max(1, Math.min(MAX_LIFT, (window.innerWidth - MARGIN) / w, (window.innerHeight - MARGIN) / h));
}

const shiftText = ({ shiftDays }: DateOffer): string =>
  t(shiftDays > 0 ? 'fix.shiftLater' : 'fix.shiftEarlier', { n: Math.abs(shiftDays) });

const noteText = (note: NonNullable<CoordinateFix['note']>): string =>
  note.landing
    ? t('fix.noteDate', { date: formatUtc(note.landing), coord: formatCoord(note.coord) })
    : t('fix.noteCoords', { coord: formatCoord(note.coord) });

const searchLabel = (progress: CoordinateFix['progress']): string => {
  if (!progress || progress.total === 0) return t('fix.searching');
  const args = { done: progress.done, total: progress.total };
  return t(progress.stage === 'dates' ? 'fix.searchingDates' : 'fix.searchingCoords', args);
};

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function FixPanel({ site, coordsKey, fix }: FixPanelProps) {
  const bad = needsFix(site);
  const [dismissedKey, setDismissedKey] = useState<string | null>(null);
  const [size, setSize] = useState<Size>({ w: 0, h: 0 });
  const slotRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const wasLifted = useRef(false);

  const measure = useCallback((el: HTMLDivElement | null) => {
    cardRef.current = el;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      const box = entry?.borderBoxSize?.[0];
      if (entry) {
        setSize({
          w: Math.round(box?.inlineSize ?? entry.contentRect.width),
          h: Math.round(box?.blockSize ?? entry.contentRect.height),
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const wanted = bad && dismissedKey !== coordsKey;
  const lifted = wanted && size.w > 0;

  useLayoutEffect(() => {
    const card = cardRef.current;
    const slot = slotRef.current;
    if (!card || !slot) return;
    const was = wasLifted.current;
    wasLifted.current = lifted;
    const scale = liftScale(size);
    card.style.setProperty('--lift', String(scale));
    if (was === lifted || typeof card.animate !== 'function' || prefersReducedMotion()) return;

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const timing = { duration: FLIGHT_MS, easing: EASE };
    if (lifted) {
      const home = slot.getBoundingClientRect();
      const dx = home.left + home.width / 2 - vw / 2;
      const dy = home.top + home.height / 2 - vh / 2;
      card.animate(
        [
          { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(1)` },
          { transform: `translate(-50%, -50%) scale(${scale})` },
        ],
        timing,
      );
    } else {
      const home = card.getBoundingClientRect();
      const dx = vw / 2 - (home.left + home.width / 2);
      const dy = vh / 2 - (home.top + home.height / 2);
      card.animate(
        [{ transform: `translate(${dx}px, ${dy}px) scale(${scale})` }, { transform: 'none' }],
        timing,
      );
    }
  }, [lifted, size]);

  useEffect(() => {
    if (!lifted) return;
    const onResize = () => cardRef.current?.style.setProperty('--lift', String(liftScale(size)));
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDismissedKey(coordsKey);
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('keydown', onKey);
    };
  }, [lifted, size, coordsKey]);

  const loading = site.status === 'loading';
  const failedCheck = site.status === 'error';

  return (
    <>
      <div className={styles.backdrop} data-on={lifted ? '' : undefined} aria-hidden="true" />
      <div ref={slotRef} className={styles.slot} style={lifted ? { minHeight: size.h } : undefined}>
        <div
          ref={measure}
          className={styles.card}
          data-lifted={lifted ? '' : undefined}
          style={lifted ? { width: size.w } : undefined}
        >
          <Panel
            num="04"
            title={t('fix.title')}
            accent
            aside={
              lifted ? (
                <Button size="s" variant="ghost" onPress={() => setDismissedKey(coordsKey)}>
                  {t('fix.collapse')}
                </Button>
              ) : undefined
            }
          >
            <div className={styles.body}>
              {bad ? (
                <>
                  <p className={styles.alert} role="alert">
                    {t('fix.bad')}
                  </p>
                  {fix.offer ? (
                    <div className={styles.offer} role="status">
                      <p className={styles.text}>
                        {t('fix.offerIntro')}
                      </p>
                      <p className={styles.offerDate}>
                        <span>{formatUtc(fix.offer.landing)}</span>
                        <span>{shiftText(fix.offer)}</span>
                      </p>
                      <p className={styles.note}>
                        {t('fix.coords')}{' '}
                        {formatCoord({ latDeg: fix.offer.latitude, lonDeg: fix.offer.longitude })}
                      </p>
                      <div className={styles.actions}>
                        <Button variant="primary" onPress={fix.acceptOffer}>
                          {t('fix.accept')}
                        </Button>
                        <Button variant="ghost" onPress={fix.dismissOffer}>
                          {t('fix.decline')}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className={styles.text}>{t('fix.pressHint')}</p>
                      <ul className={styles.reasons}>
                        <li>
                          <strong>{t('fix.reasonLabel')}</strong> {site.message}
                        </li>
                      </ul>
                      <Button variant="primary" wide isDisabled={fix.searching} onPress={fix.run}>
                        {fix.searching ? searchLabel(fix.progress) : t('fix.find')}
                      </Button>
                      {fix.searching && fix.progress && fix.progress.total > 0 && (
                        <progress
                          className={styles.progress}
                          max={fix.progress.total}
                          value={fix.progress.done}
                          aria-label={t('fix.searching')}
                        />
                      )}
                      {fix.error && (
                        <p className={styles.error} role="alert">
                          {fix.error}
                        </p>
                      )}
                    </>
                  )}
                </>
              ) : failedCheck ? (
                <p className={styles.text}>
                  {t('fix.checkFailed', { message: site.message })}
                </p>
              ) : loading ? (
                <p className={styles.text} aria-live="polite">
                  {t('fix.checking')}
                </p>
              ) : (
                <p className={styles.good} aria-live="polite">
                  {t('fix.good')}
                </p>
              )}
              {!bad && fix.note && <p className={styles.note}>{t('fix.changed', { note: noteText(fix.note) })}</p>}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
