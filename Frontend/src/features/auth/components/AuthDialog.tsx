import { useState } from 'react';
import { Dialog, DialogTrigger, Heading, Modal, ModalOverlay } from 'react-aria-components';
import { t } from '../../../shared/i18n';
import { Button } from '../../../shared/ui/Button';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';
import styles from './AuthDialog.module.css';

export function AuthDialog() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  return (
    <DialogTrigger>
      <Button>{t('auth.login')}</Button>
      <ModalOverlay className={styles.overlay ?? ''} isDismissable>
        <Modal className={styles.drawer ?? ''}>
          <Dialog className={styles.dialog ?? ''}>
            {({ close }) => (
              <>
                <header className={styles.head}>
                  <Heading slot="title" className={styles.title ?? ''}>
                    {mode === 'login' ? t('auth.login') : t('auth.register')}
                  </Heading>
                  <Button variant="ghost" aria-label={t('common.close')} onPress={close}>
                    ✕
                  </Button>
                </header>
                {mode === 'login' ? (
                  <LoginForm onDone={close} onSwitch={() => setMode('register')} />
                ) : (
                  <RegisterForm onDone={close} onSwitch={() => setMode('login')} />
                )}
              </>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  );
}
