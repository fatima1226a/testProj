import { useState } from 'react';
import { t } from '../../../shared/i18n';
import { Badge } from '../../../shared/ui/Badge';
import { Button } from '../../../shared/ui/Button';
import { formatUtc } from '../../../shared/lib/format';
import { errorText, messageOf } from '../../../shared/api/errors';
import {
  useDeleteRunMutation,
  useListRunsQuery,
  useRenameRunMutation,
  type SavedRun,
} from '../runsApi';
import styles from './RunHistory.module.css';

interface RunHistoryProps {
  onOpen: (run: SavedRun) => void;
}

export function RunHistory({ onOpen }: RunHistoryProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error } = useListRunsQuery(page);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [rename] = useRenameRunMutation();
  const [remove] = useDeleteRunMutation();

  if (isLoading) return <p className={styles.empty}>{t('runs.loading')}</p>;
  if (error) return <p className={styles.error}>{messageOf(error)}</p>;
  const runs = data?.runs ?? [];

  const fail = (e: unknown) => setMessage(errorText(e));

  const commitRename = async (id: number) => {
    setMessage(null);
    try {
      await rename({ id, label: draft.trim() }).unwrap();
      setRenaming(null);
    } catch (e) {
      fail(e);
    }
  };

  const dropRun = async (id: number) => {
    setMessage(null);
    try {
      await remove(id).unwrap();
      if (runs.length === 1 && page > 1) setPage(page - 1);
    } catch (e) {
      fail(e);
    }
  };

  return (
    <div className={styles.root} aria-busy={isFetching}>
      {runs.length === 0 ? (
        <p className={styles.empty}>{t('runs.empty')}</p>
      ) : (
        <ul className={styles.list}>
          {runs.map((run) => (
            <li key={run.id} className={styles.item}>
              <div className={styles.head}>
                {renaming === run.id ? (
                  <input
                    className={styles.input}
                    value={draft}
                    maxLength={200}
                    aria-label={t('runs.nameAria')}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void commitRename(run.id);
                      if (e.key === 'Escape') setRenaming(null);
                    }}
                  />
                ) : (
                  <strong className={styles.label}>{run.label || t('runs.untitled', { id: run.id })}</strong>
                )}
                {run.survives !== null && (
                  <Badge tone={run.survives ? 'ok' : 'fail'}>
                    {t(run.survives ? 'badge.ok' : 'badge.fail')}
                  </Badge>
                )}
              </div>
              {run.createdAt && Number.isFinite(Date.parse(run.createdAt)) && (
                <p className={styles.meta}>{t('runs.savedAt', { date: formatUtc(run.createdAt) })}</p>
              )}
              <div className={styles.actions}>
                <Button size="s" onPress={() => onOpen(run)}>
                  {t('runs.open')}
                </Button>
                {renaming === run.id ? (
                  <>
                    <Button size="s" variant="primary" onPress={() => void commitRename(run.id)}>
                      {t('runs.save')}
                    </Button>
                    <Button size="s" variant="ghost" onPress={() => setRenaming(null)}>
                      {t('runs.cancel')}
                    </Button>
                  </>
                ) : (
                  <Button
                    size="s"
                    variant="ghost"
                    onPress={() => {
                      setRenaming(run.id);
                      setDraft(run.label);
                    }}
                  >
                    {t('runs.rename')}
                  </Button>
                )}
                <Button size="s" variant="ghost" onPress={() => void dropRun(run.id)}>
                  {t('runs.delete')}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {message && (
        <p className={styles.error} role="alert">
          {message}
        </p>
      )}
      {(data?.hasPrev || data?.hasNext) && (
        <div className={styles.pager}>
          <Button size="s" isDisabled={!data?.hasPrev} onPress={() => setPage(page - 1)}>
            {t('runs.prev')}
          </Button>
          <span>{t('runs.page', { n: page })}</span>
          <Button size="s" isDisabled={!data?.hasNext} onPress={() => setPage(page + 1)}>
            {t('runs.next')}
          </Button>
        </div>
      )}
    </div>
  );
}
