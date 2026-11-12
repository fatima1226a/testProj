import type { ReactNode } from 'react';
import { Header } from './Header';
import styles from './AppShell.module.css';

export function AppShell({ header, children }: { header?: ReactNode; children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <Header>{header}</Header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
