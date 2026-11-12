import { t } from '../../../shared/i18n';
import { stateLabel, type SceneSnapshot } from '../sceneState';
import styles from './StateBadge.module.css';

const ICON = {
  working: '●',
  charging: '◐',
  danger: '▲',
  fading: '○',
  noEarth: '⌀',
} as const;

export function StateBadge({ snapshot }: { snapshot: SceneSnapshot }) {
  const { state, onBattery, batteryFailed } = snapshot;
  let label: string = stateLabel(state);
  if (state === 'fading' && batteryFailed) label = t('state.fadingBattery');
  if (state === 'working' && onBattery) label = t('state.onBattery');
  return (
    <span className={styles.root} data-state={state}>
      <span aria-hidden="true">{ICON[state]}</span> {label}
    </span>
  );
}
