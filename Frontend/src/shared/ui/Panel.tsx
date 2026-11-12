import { useId, type ReactNode } from 'react';
import styles from './Panel.module.css';

interface PanelProps {
  num?: string;
  title: string;
  aside?: ReactNode;
  accent?: boolean;
  flush?: boolean;
  children: ReactNode;
}

export function Panel({ num, title, aside, accent = false, flush = false, children }: PanelProps) {
  const id = useId();
  const className = [styles.root, accent && styles.accent, flush && styles.flush]
    .filter(Boolean)
    .join(' ');
  return (
    <section className={className} aria-labelledby={id}>
      <header className={styles.head}>
        <h2 id={id} className={styles.title}>
          {num && <span className={styles.num}>{num}</span>}
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  );
}
