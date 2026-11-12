import { useCallback, useEffect } from 'react';
import { I18nProvider } from 'react-aria-components';
import { useAppDispatch, useAppSelector } from './app/store';
import { Calendar } from './features/calendar/components/Calendar';
import { AuthDialog } from './features/auth/components/AuthDialog';
import { useLogoutMutation } from './features/auth/authApi';
import { selectUsername } from './features/auth/authSlice';
import { DemoBadge } from './features/datasets/components/DemoBadge';
import { SourcesDrawer } from './features/datasets/components/SourcesDrawer';
import { pickSite } from './features/datasets/parse';
import { useDataset } from './features/datasets/useDataset';
import { FixPanel } from './features/fix/components/FixPanel';
import { HorizonProfile } from './features/horizon/components/HorizonProfile';
import { MissionPanel } from './features/plan/components/MissionPanel';
import { startKeepingTransit } from './features/plan/dates';
import { planPatched, selectPlan } from './features/plan/planSlice';
import { validatePlan } from './features/plan/validatePlan';
import { RunsDialog } from './features/runs/components/RunsDialog';
import { KpiRow } from './features/result/components/KpiRow';
import { selectCalendar, selectResult, selectSite } from './features/result/resultSlice';
import { Scene } from './features/scene/components/Scene';
import { selectSceneSnapshot } from './features/scene/sceneState';
import { SurvivalVerdict } from './features/survival/components/SurvivalVerdict';
import { WhyPanel } from './features/survival/components/WhyPanel';
import { useCoordinateFix, useSurvival } from './features/survival/useSurvival';
import { Timeline } from './features/timeline/components/Timeline';
import {
  hourSelected,
  playTicked,
  playToggled,
  selectPlaying,
  selectSelectedHour,
  selectSpeed,
  speedSet,
} from './features/timeline/viewSlice';
import { localeOf, t, useLang } from './shared/i18n';
import { useMediaQuery } from './shared/lib/hooks';
import { LangSwitch } from './shared/layout/LangSwitch';
import { AppShell } from './shared/layout/AppShell';
import { Button } from './shared/ui/Button';
import styles from './App.module.css';

export default function App() {
  const lang = useLang();
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  return (
    <I18nProvider locale={localeOf(lang)}>
      <Screen key={lang} />
    </I18nProvider>
  );
}

function Screen() {
  const dispatch = useAppDispatch();
  const plan = useAppSelector(selectPlan);
  const errors = validatePlan(plan);
  const site = useAppSelector(selectSite);
  const result = useAppSelector(selectResult);
  const calendar = useAppSelector(selectCalendar);
  const snapshot = useAppSelector(selectSceneSnapshot);
  const hour = useAppSelector(selectSelectedHour);
  const playing = useAppSelector(selectPlaying);
  const speed = useAppSelector(selectSpeed);
  const collapsiblePlan = useMediaQuery('(max-width: 1023px)');
  const username = useAppSelector(selectUsername);
  const [logout] = useLogoutMutation();

  const data = useDataset();
  const checks = data.validation?.checks ?? [];
  const passed = checks.filter((c) => c.status === 'pass').length;
  const pending = checks.filter((c) => c.status === 'pending').length;

  const survival = useSurvival(plan);
  const fix = useCoordinateFix(plan, survival);
  const coordsKey = `${plan.coord.latDeg},${plan.coord.lonDeg}`;

  const dataSite = data.horizonSites ? pickSite(data.horizonSites, plan.coord) : null;
  const horizonHint = dataSite?.horizon
    ? null
    : data.loading || data.horizonSites === null
      ? 'hz.loading'
      : !dataSite
        ? 'hz.noSites'
        : 'hz.noHorizon';

  const jumpTo = (h: number) => dispatch(hourSelected(h));
  const tick = useCallback((last: number) => dispatch(playTicked(last)), [dispatch]);

  return (
    <AppShell
        header={
          <>
            <DemoBadge mode={data.provenance?.mode ?? undefined} />
            <span className={styles.checks}>
              {checks.length > 0
                ? `${t('app.checks', { passed, total: checks.length })}${pending > 0 ? t('app.checksPending', { pending }) : ''}`
                : data.loading
                  ? t('app.checksLoading')
                  : t('app.checksNone')}
            </span>
            <LangSwitch />
            <SourcesDrawer provenance={data.provenance} validation={data.validation} />
            {username ? (
              <>
                <RunsDialog
                  plan={plan}
                  survival={survival}
                  dataset={data.dataset}
                  sites={data.sites}
                  sitesSettled={data.sitesSettled}
                  onOpenRun={(patch) => dispatch(planPatched(patch))}
                />
                <span className={styles.checks}>{username}</span>
                <Button variant="ghost" onPress={() => void logout()}>
                  {t('app.logout')}
                </Button>
              </>
            ) : (
              <AuthDialog />
            )}
          </>
        }
      >
        <div className={styles.heading}>
          <div>
            <p className={styles.eyebrow}>{t('app.eyebrow')}</p>
            <h2 className={styles.title}>{t('app.title')}</h2>
          </div>
          <p className={styles.sub}>{t('app.sub')}</p>
        </div>
        <p className={styles.demo}>
          {t('app.demo')}
          {data.error ? t('app.dataError', { error: data.error }) : ''}
        </p>

        <div className={styles.layout}>
          <aside className={styles.plan} aria-label={t('app.planAria')}>
            <MissionPanel
              plan={plan}
              errors={errors}
              onChange={(patch) => dispatch(planPatched(patch))}
              survival={survival}
              collapsible={collapsiblePlan}
            />
          </aside>

          <section className={styles.center} aria-label={t('app.resultAria')}>
            <SurvivalVerdict site={survival} />
            <KpiRow result={result} />
            <Scene hour={hour} snapshot={snapshot} />
            <Timeline
              plan={plan}
              result={result}
              hour={hour}
              playing={playing}
              speed={speed}
              onHourSelect={jumpTo}
              onPlayToggle={(last) => dispatch(playToggled(last))}
              onTick={tick}
              onSpeedChange={(s) => dispatch(speedSet(s))}
            />
            <HorizonProfile
              site={site}
              dataSite={dataSite}
              landing={plan.landing}
              hour={hour}
              result={result}
              sample={snapshot?.sample ?? null}
              hint={horizonHint}
            />
          </section>

          <div className={styles.side}>
            <WhyPanel site={survival} />
            <FixPanel site={survival} coordsKey={coordsKey} fix={fix} />
          </div>
        </div>

        <div className={styles.bottom}>
          <Calendar
            plan={plan}
            cells={calendar}
            onSelect={(landing) =>
              dispatch(planPatched({ landing, start: startKeepingTransit(plan, landing) }))
            }
          />
        </div>

        <footer className={styles.footer}>
          {t('app.footer')}
        </footer>
      </AppShell>
  );
}
