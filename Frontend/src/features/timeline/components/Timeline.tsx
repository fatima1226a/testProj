import { useEffect, useId } from 'react';
import { ToggleButton, ToggleButtonGroup } from 'react-aria-components';
import { scaleLinear } from 'd3-scale';
import { t } from '../../../shared/i18n';
import { addHours, formatNumber, formatUtc } from '../../../shared/lib/format';
import { useElementWidth } from '../../../shared/lib/hooks';
import { Button } from '../../../shared/ui/Button';
import { Panel } from '../../../shared/ui/Panel';
import { Slider } from '../../../shared/ui/Slider';
import type { Plan } from '../../plan/types';
import { lastHour, type Result } from '../../result/types';
import { SPEEDS, type Speed } from '../viewSlice';
import styles from './Timeline.module.css';

const LEFT = 64;
const RIGHT = 10;
const SUN_Y = 4;
const EARTH_Y = 32;
const LANE_H = 20;
const BAT_TOP = 66;
const BAT_BOTTOM = 160;
const HEIGHT = 184;

interface TimelineProps {
  plan: Plan;
  result: Result | null;
  hour: number;
  playing: boolean;
  speed: Speed;
  onHourSelect: (hour: number) => void;
  onPlayToggle: (lastHour: number) => void;
  onTick: (lastHour: number) => void;
  onSpeedChange: (speed: Speed) => void;
}

function runs(flags: boolean[], value: boolean, max: number): [number, number][] {
  const out: [number, number][] = [];
  flags.forEach((flag, i) => {
    if (flag !== value || i >= max) return;
    const last = out[out.length - 1];
    if (last && last[1] === i) last[1] = i + 1;
    else out.push([i, i + 1]);
  });
  return out;
}

function tickStep(n: number): number {
  for (const step of [1, 2, 3, 4, 6, 12, 24, 48]) if (n / step <= 8) return step;
  return 24;
}

export function Timeline({
  plan,
  result,
  hour,
  playing,
  speed,
  onHourSelect,
  onPlayToggle,
  onTick,
  onSpeedChange,
}: TimelineProps) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');

  const N = Math.max(1, lastHour(result));
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => onTick(N), 1000 / speed);
    return () => clearTimeout(timer);
  }, [playing, hour, speed, onTick, N]);

  const x = scaleLinear().domain([0, N]).range([LEFT, Math.max(LEFT + 1, width - RIGHT)]);
  const y = scaleLinear().domain([0, 100]).range([BAT_BOTTOM, BAT_TOP]);
  const failure = result?.failure?.reason === 'battery' ? result.failure : null;
  const minPct = result?.limits.minSocPct ?? null;
  const batteryPath = result?.batteryPct
    .map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join('');

  return (
    <Panel
      num="02"
      title={t('tl.title')}
      aside={
        <span className={styles.readout}>
          {t('tl.readout', { hour, utc: formatUtc(addHours(plan.landing, hour)) })}
        </span>
      }
    >
      <div ref={ref} className={styles.chart}>
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={t('tl.aria', { n: N })}
          className={styles.svg}
        >
          <defs>
            <pattern id={`hatch-${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" className={styles.hatchBg} />
              <line x1="0" y1="0" x2="0" y2="6" className={styles.hatchLine} />
            </pattern>
          </defs>

          <text x={0} y={SUN_Y + 14} className={styles.label}>{t('scene.sun')}</text>
          <text x={0} y={EARTH_Y + 14} className={styles.label}>{t('scene.earth')}</text>
          <text x={0} y={BAT_TOP + 12} className={styles.label}>{t('scene.battery')}</text>
          <text x={0} y={BAT_TOP + 28} className={styles.label}>%</text>

          {result && (
            <>
              {runs(result.hours.map((h) => h.sun), true, N).map(([a, b]) => (
                <rect key={`s${a}`} x={x(a)} y={SUN_Y} width={x(b) - x(a)} height={LANE_H} className={styles.sun} />
              ))}
              {runs(result.hours.map((h) => h.sun), false, N).map(([a, b]) => (
                <rect key={`d${a}`} x={x(a)} y={SUN_Y} width={x(b) - x(a)} height={LANE_H} fill={`url(#hatch-${uid})`} />
              ))}
              {runs(result.hours.map((h) => h.earth === true), true, N).map(([a, b]) => (
                <rect key={`e${a}`} x={x(a)} y={EARTH_Y} width={x(b) - x(a)} height={LANE_H} className={styles.earthLane} />
              ))}
              {runs(result.hours.map((h) => h.earth === false), true, N).map(([a, b]) => (
                <rect key={`g${a}`} x={x(a) + 0.5} y={EARTH_Y + 0.5} width={x(b) - x(a) - 1} height={LANE_H - 1} className={styles.gap} />
              ))}
            </>
          )}

          {Array.from({ length: Math.floor(N / tickStep(N)) + 1 }, (_, d) => d * tickStep(N)).map((tick) => (
            <g key={tick}>
              <line x1={x(tick)} x2={x(tick)} y1={BAT_TOP - 4} y2={BAT_BOTTOM} className={styles.grid} />
              <text x={x(tick)} y={HEIGHT - 6} className={styles.tick} textAnchor={tick === 0 ? 'start' : tick === N ? 'end' : 'middle'}>
                {tick === N ? t('tl.tickEnd', { n: N }) : tick}
              </text>
            </g>
          ))}

          {minPct !== null && (
            <>
              <line x1={LEFT} x2={x(N)} y1={y(minPct)} y2={y(minPct)} className={styles.min} />
              <text x={LEFT + 4} y={y(minPct) - 4} className={styles.minLabel}>
                {t('tl.min', { n: formatNumber(minPct) })}
              </text>
            </>
          )}

          {batteryPath && <path d={batteryPath} className={styles.battery} />}

          {failure && (
            <g>
              <rect x={x(failure.hour)} y={0} width={x(N) - x(failure.hour)} height={BAT_BOTTOM} className={styles.after} />
              <line x1={x(failure.hour)} x2={x(failure.hour)} y1={0} y2={BAT_BOTTOM} className={styles.failLine} />
              <text
                x={x(failure.hour) + (failure.hour > N * 0.8 ? -4 : 4)}
                y={BAT_BOTTOM - 6}
                textAnchor={failure.hour > N * 0.8 ? 'end' : 'start'}
                className={styles.failLabel}
              >
                {t('tl.failure', { hour: failure.hour })}
              </text>
            </g>
          )}

          {result && (
            <g className={styles.cursor}>
              <line x1={x(hour)} x2={x(hour)} y1={0} y2={BAT_BOTTOM + 2} />
              <circle cx={x(hour)} cy={y(result.batteryPct[hour] ?? 0)} r={4} />
            </g>
          )}
        </svg>
      </div>

      <div className={styles.transport}>
        <Button
          aria-label={playing ? t('tl.pause') : t('tl.play')}
          isDisabled={!result}
          onPress={() => onPlayToggle(N)}
        >
          <span aria-hidden="true">{playing ? '❚❚' : '▶'}</span>
        </Button>
        <ToggleButtonGroup
          aria-label={t('tl.speed')}
          className={styles.speeds ?? ''}
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={[String(speed)]}
          onSelectionChange={(keys) => {
            const next = SPEEDS.find((s) => String(s) === [...keys][0]);
            if (next) onSpeedChange(next);
          }}
        >
          {SPEEDS.map((s) => (
            <ToggleButton key={s} id={String(s)} className={styles.speed ?? ''}>
              {s}×
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <div className={styles.scrub}>
          <Slider
            aria-label={t('tl.hourAria')}
            value={hour}
            onChange={onHourSelect}
            minValue={0}
            maxValue={N}
            isDisabled={!result}
          />
        </div>
        <output className={styles.count}>{t('tl.count', { hour, n: N })}</output>
      </div>
      {failure && (
        <p className={styles.note}>{t('tl.afterFail')}</p>
      )}
      {!result && <p className={styles.note}>{t('tl.pending')}</p>}
    </Panel>
  );
}
