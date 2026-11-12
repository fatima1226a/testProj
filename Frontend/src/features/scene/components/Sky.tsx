import type { HourSample } from '../../result/types';
import styles from './Sky.module.css';

const STARS: [number, number, number][] = [
  [40, 30, 1.1], [96, 72, 0.7], [170, 24, 0.9], [232, 58, 0.6], [290, 18, 1], [338, 84, 0.7],
  [402, 40, 0.8], [455, 14, 0.6], [508, 92, 0.9], [612, 28, 0.7], [662, 76, 1], [138, 112, 0.6],
  [372, 120, 0.6], [690, 130, 0.7], [20, 140, 0.8], [250, 104, 0.5],
];

export function Sky({ sample }: { sample: HourSample }) {
  const sunX = sample.sunAzDeg === null ? 350 : 70 + (sample.sunAzDeg / 360) * 560;
  const sunY = sample.sunElDeg === null ? 120 : 170 - Math.max(-2, sample.sunElDeg) * 28;
  return (
    <g>
      {STARS.map(([x, y, r]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={r} className={styles.star} />
      ))}
      <g className={`${styles.sun} ${sample.sun ? '' : styles.hidden}`}>
        <circle cx={sunX} cy={sunY} r={30} className={styles.halo} />
        <circle cx={sunX} cy={sunY} r={18} className={styles.disc} />
      </g>
      <g className={`${styles.earth} ${sample.earth === false ? styles.hidden : ''}`}>
        <circle cx={590} cy={66} r={14} className={styles.earthDisc} />
        <path d="M583 55l8 4-3 5 7 3-4 7-6-3-3-7z" className={styles.land} />
      </g>
    </g>
  );
}
