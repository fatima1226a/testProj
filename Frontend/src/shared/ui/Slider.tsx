import { Slider as AriaSlider, SliderThumb, SliderTrack } from 'react-aria-components';
import styles from './Slider.module.css';

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  minValue: number;
  maxValue: number;
  step?: number;
  isDisabled?: boolean;
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

export function Slider({ value, onChange, step = 1, ...props }: SliderProps) {
  return (
    <AriaSlider {...props} value={value} step={step} onChange={onChange} className={styles.root ?? ''}>
      <SliderTrack className={styles.track ?? ''}>
        {({ state }) => (
          <>
            <div className={styles.fill} style={{ width: `${state.getThumbPercent(0) * 100}%` }} />
            <SliderThumb className={styles.thumb ?? ''} />
          </>
        )}
      </SliderTrack>
    </AriaSlider>
  );
}
