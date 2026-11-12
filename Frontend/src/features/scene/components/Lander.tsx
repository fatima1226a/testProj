import type { SceneState } from '../sceneState';
import styles from './Lander.module.css';

export function Lander({ state }: { state: SceneState }) {
  return (
    <g className={styles.root} data-state={state}>
      <defs>
        <linearGradient id="lander-body" x2="1" y2="1">
          <stop offset="0" stopColor="#e6b8ff" />
          <stop offset=".45" stopColor="#9a4dff" />
          <stop offset="1" stopColor="#3a1a9a" />
        </linearGradient>
      </defs>
      <path className={styles.leg} d="M329 217l-22 49m63-49 24 49" />
      <path className={styles.foot} d="M295 269h24m64 0h24" />

      <g className={styles.panels}>
        <path d="M325 210l-69-19-8 29 71 15m57-25 67-18 9 27-71 16" />
        <path className={styles.cells} d="M270 196l-7 28m23-23-7 28m24-23-7 27m98-28 7 25m10-29 7 25m10-30 7 26" />
      </g>
      <g className={styles.particles} aria-hidden="true">
        <circle cx="262" cy="206" r="2" />
        <circle cx="440" cy="206" r="2" />
        <circle cx="290" cy="214" r="1.6" />
        <circle cx="412" cy="214" r="1.6" />
      </g>

      <path d="M328 206h43v37h-43z" fill="url(#lander-body)" stroke="#f0d0ff" />
      <path className={styles.top} d="M322 207l12-16h31l13 16z" />
      <path className={styles.mast} d="M348 191v-27" />
      <path className={styles.dish} d="M338 162q16 14 26-3" />

      <g className={styles.signal}>
        <path d="M365 148q12-12 24 0" />
        <path d="M371 141q7-7 15 0" />
      </g>
      <g className={styles.noSignal}>
        <path d="M366 140l18 14m0-14l-18 14" />
      </g>

      <g className={styles.lights}>
        <circle cx="336" cy="232" r="2.2" />
        <circle cx="344" cy="232" r="2.2" />
        <circle cx="352" cy="232" r="2.2" />
        <circle cx="360" cy="232" r="2.2" />
      </g>
      <circle className={styles.led} cx="349" cy="219" r="4" />

      <g className={styles.warning}>
        <path d="M349 112l13 22h-26z" />
        <path className={styles.mark} d="M349 120v7m0 3v1" />
      </g>
    </g>
  );
}
