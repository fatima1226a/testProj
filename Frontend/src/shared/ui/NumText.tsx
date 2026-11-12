import { Fragment } from 'react';
import styles from './NumText.module.css';

const NUMBER = /([−-]?\d[\d\u00a0\u202f]*(?:[.,]\d+)*)/g;

export function NumText({ children }: { children: string }) {
  const parts = children.split(NUMBER);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className={styles.num}>
            {part}
          </span>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}
