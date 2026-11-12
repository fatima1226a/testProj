import { Button as AriaButton, type ButtonProps as AriaButtonProps } from 'react-aria-components';
import styles from './Button.module.css';

interface ButtonProps extends Omit<AriaButtonProps, 'className'> {
  variant?: 'default' | 'primary' | 'ghost';
  size?: 'm' | 's';
  wide?: boolean;
}

export function Button({ variant = 'default', size = 'm', wide = false, ...props }: ButtonProps) {
  const className = [styles.root, styles[variant], styles[size], wide && styles.wide]
    .filter(Boolean)
    .join(' ');
  return <AriaButton {...props} className={className} />;
}
