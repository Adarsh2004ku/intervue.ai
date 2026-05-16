import styles from './ImmersiveBackground.module.css';

type ImmersiveBackgroundProps = {
  variant?: 'hero' | 'ambient';
  className?: string;
};

export function ImmersiveBackground({ variant = 'hero', className = '' }: ImmersiveBackgroundProps) {
  return (
    <div className={`${styles.backdrop} ${styles[variant]} ${className}`} aria-hidden="true">
      <div className={styles.wash} />
      <div className={styles.lightSweep} />
      <div className={styles.grid} />
      <div className={styles.vignette} />
    </div>
  );
}
