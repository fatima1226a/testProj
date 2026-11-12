import { useState } from 'react';
import { Dialog, DialogTrigger, Heading, Modal, ModalOverlay } from 'react-aria-components';
import { errorText } from '../../../shared/api/errors';
import { resolveMsgs, t } from '../../../shared/i18n';
import { Button } from '../../../shared/ui/Button';
import { pickSite } from '../../datasets/parse';
import type { DatasetInfo, SiteInfo } from '../../datasets/types';
import type { Plan } from '../../plan/types';
import type { SiteSurvival } from '../../survival/types';
import { planFromSnapshot, planSnapshot, RUN_SITE_ID } from '../snapshot';
import { useSaveRunMutation, type SavedRun } from '../runsApi';
import { RunHistory } from './RunHistory';
import styles from './RunsDialog.module.css';

interface RunsDialogProps {
  plan: Plan;
  survival: SiteSurvival;
  dataset: DatasetInfo | null;
  sites: SiteInfo[] | null;
  sitesSettled: boolean;
  onOpenRun: (patch: Partial<Plan>) => void;
}

export function RunsDialog({ plan, survival, dataset, sites, sitesSettled, onOpenRun }: RunsDialogProps) {
  const [label, setLabel] = useState('');
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [save, { isLoading }] = useSaveRunMutation();

  const result = survival.result;
  const site = sites ? pickSite(sites, plan.coord) : null;
  const siteId = sitesSettled ? (site?.id ?? RUN_SITE_ID) : null;
  const blocker = !dataset
    ? t('runs.noDataset')
    : siteId === null
      ? t('runs.loadingSites')
      : !result
        ? t('runs.waitVerdict')
        : null;

  const submit = async () => {
    if (!dataset || !result || siteId === null) return;
    setError(null);
    setSaved(false);
    try {
      await save({
        dataset_id: dataset.id,
        site_id: siteId,
        plan: planSnapshot(plan, { datasetId: dataset.id, siteId }),
        result: {
          survives: result.survives,
          assumptions: resolveMsgs(result.assumptions),
          sections: resolveMsgs(result.sections),
        },
        ...(label.trim() ? { label: label.trim() } : {}),
      }).unwrap();
      setSaved(true);
      setLabel('');
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <DialogTrigger>
      <Button>{t('runs.button')}</Button>
      <ModalOverlay className={styles.overlay ?? ''} isDismissable>
        <Modal className={styles.drawer ?? ''}>
          <Dialog className={styles.dialog ?? ''}>
            {({ close }) => (
              <>
                <header className={styles.head}>
                  <Heading slot="title" className={styles.title ?? ''}>
                    {t('runs.button')}
                  </Heading>
                  <Button variant="ghost" aria-label={t('common.close')} onPress={close}>
                    ✕
                  </Button>
                </header>

                <section className={styles.section}>
                  <h3 className={styles.subtitle}>{t('runs.saveTitle')}</h3>
                  <label className={styles.field}>
                    <span>{t('runs.name')}</span>
                    <input
                      className={styles.input}
                      value={label}
                      maxLength={200}
                      onChange={(e) => setLabel(e.target.value)}
                    />
                  </label>
                  <Button variant="primary" wide isDisabled={blocker !== null || isLoading} onPress={() => void submit()}>
                    {isLoading ? t('runs.saving') : t('runs.saveRun')}
                  </Button>
                  {blocker && <p className={styles.hint}>{blocker}</p>}
                  {saved && (
                    <p className={styles.ok} aria-live="polite">
                      {t('runs.saved')}
                    </p>
                  )}
                  {error && (
                    <p className={styles.error} role="alert">
                      {error}
                    </p>
                  )}
                </section>

                <section className={styles.section}>
                  <h3 className={styles.subtitle}>{t('runs.myTitle')}</h3>
                  <RunHistory
                    onOpen={(run: SavedRun) => {
                      onOpenRun(planFromSnapshot(run.plan));
                      close();
                    }}
                  />
                </section>
              </>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}
