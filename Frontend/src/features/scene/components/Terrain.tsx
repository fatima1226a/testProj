import styles from './Terrain.module.css';

export function Terrain() {
  return (
    <g>
      <defs>
        <linearGradient id="scene-ridge" x2="0" y2="1">
          <stop offset="0" stopColor="#6a45c0" />
          <stop offset="1" stopColor="#26125e" />
        </linearGradient>
        <linearGradient id="scene-ground" x2="0" y2="1">
          <stop offset="0" stopColor="#7650d0" />
          <stop offset="1" stopColor="#1f0f52" />
        </linearGradient>
      </defs>
      <path
        className={styles.far}
        d="M0 205L70 146 125 177 194 152 253 194 324 154 370 190 445 122 492 154 552 117 622 157 700 135V300H0Z"
      />
      <path
        fill="url(#scene-ridge)"
        d="M0 228L76 185 131 205 205 167 265 218 340 194 395 225 472 166 522 196 598 163 700 201V300H0Z"
      />
      <path fill="url(#scene-ground)" d="M0 254Q145 211 312 246T700 226V300H0Z" />
      <ellipse cx="357" cy="267" rx="99" ry="10" className={styles.shadow} />
    </g>
  );
}
