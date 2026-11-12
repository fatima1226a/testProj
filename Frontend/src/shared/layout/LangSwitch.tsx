import { setLang, t, useLang, type Lang } from '../i18n';
import styles from './LangSwitch.module.css';

const OPTIONS: { lang: Lang; label: string; hint: 'app.langRu' | 'app.langEn' }[] = [
  { lang: 'ru', label: 'RU', hint: 'app.langRu' },
  { lang: 'en', label: 'EN', hint: 'app.langEn' },
];

export function LangSwitch() {
  const current = useLang();
  return (
    <div className={styles.root} role="group" aria-label={t('app.langAria')}>
      {OPTIONS.map(({ lang, label, hint }) => (
        <button
          key={lang}
          type="button"
          className={`${styles.option} ${current === lang ? styles.active : ''}`}
          aria-pressed={current === lang}
          lang={lang}
          title={t(hint)}
          onClick={() => setLang(lang)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
