import type { ReactNode } from 'react';
import styles from './Badge.module.css';

export type BadgeTone = 'demo' | 'neutral' | 'ok' | 'fail' | 'earth';

export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`${styles.root} ${styles[tone]}`}>{children}</span>;
}
