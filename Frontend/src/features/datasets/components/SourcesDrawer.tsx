import { Dialog, DialogTrigger, Heading, Modal, ModalOverlay } from 'react-aria-components';
import { t } from '../../../shared/i18n';
import { SURVIVAL_DAYS } from '../../plan/defaults';
import { Badge, type BadgeTone } from '../../../shared/ui/Badge';
import { Button } from '../../../shared/ui/Button';
import type { CheckItem, Provenance, Validation } from '../types';
import styles from './SourcesDrawer.module.css';

const CHECK_TONE: Record<CheckItem['status'], BadgeTone> = {
  pass: 'ok',
  fail: 'fail',
  pending: 'neutral',
};

interface SourcesDrawerProps {
  provenance?: Provenance | null;
  validation?: Validation | null;
}

export function SourcesDrawer({ provenance = null, validation = null }: SourcesDrawerProps) {
  const checks = validation?.checks ?? [];
  const sources = provenance?.sources ?? [];
  const final = provenance?.mode === 'final';
  return (
    <DialogTrigger>
      <Button>{t('src.button')}</Button>
      <ModalOverlay className={styles.overlay ?? ''} isDismissable>
        <Modal className={styles.drawer ?? ''}>
          <Dialog className={styles.dialog ?? ''}>
            {({ close }) => (
              <>
                <header className={styles.head}>
                  <Heading slot="title" className={styles.title ?? ''}>
                    {t('src.button')}
                  </Heading>
                  <Button variant="ghost" aria-label={t('common.close')} onPress={close}>
                    ✕
                  </Button>
                </header>

                <section className={styles.section}>
                  <h3 className={styles.subtitle}>{t('src.modeTitle')}</h3>
                  <p>
                    {final ? <Badge tone="ok">FINAL</Badge> : <Badge tone="demo">DEMO DATA</Badge>}
                  </p>
                  <p>
                    {t('src.modeNote')}
                  </p>
                </section>

                {final && sources.length > 0 && (
                  <section className={styles.section}>
                    <h3 className={styles.subtitle}>{t('src.sourcesTitle')}</h3>
                    <ul>
                      {sources.map((src) => (
                        <li key={src.title}>
                          {src.title}
                          {src.text ? ` — ${src.text}` : ''}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                <section className={styles.section}>
                  <h3 className={styles.subtitle}>{t('src.assumptionsTitle')}</h3>
                  <ul>
                    <li>{t('src.a1')}</li>
                    <li>
                      {t('src.a2')}
                    </li>
                    <li>{t('src.a3')}</li>
                    <li>{t('src.a4')}</li>
                    <li>{t('src.a5', { days: SURVIVAL_DAYS })}</li>
                  </ul>
                </section>

                {checks.length > 0 && (
                  <section className={styles.section}>
                    <h3 className={styles.subtitle}>{t('src.checksTitle')}</h3>
                    <ul className={styles.checks}>
                      {checks.map((check) => (
                        <li key={check.name}>
                          <span>{check.name}</span>
                          <Badge tone={CHECK_TONE[check.status]}>{check.status}</Badge>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}
