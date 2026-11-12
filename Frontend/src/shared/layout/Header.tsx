import type { ReactNode } from 'react';
import styles from './Header.module.css';

export function Header({ children }: { children?: ReactNode }) {
  return (
    <header className={styles.root}>
      <h1 className={styles.brand}>
        LAST <span className={styles.accent}>LIGHT</span>
      </h1>
      <p className={styles.strap}>
        CLPS Lunar Mission Browser
        <br />
        NASA Space Apps 2026
      </p>
      {children && <div className={styles.slot}>{children}</div>}
    </header>
  );
}
