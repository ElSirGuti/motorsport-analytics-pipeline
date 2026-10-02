import { useLanguage } from '../context/LanguageContext';
import { Icon } from './ui';
import styles from './Analysis.module.css';

const OVERALL = {
  ok: { key: 'ok', cls: 'Ok', icon: 'check' },
  warning: { key: 'warning', cls: 'Warn', icon: 'alert' },
  critical: { key: 'critical', cls: 'Bad', icon: 'alert' },
};
const DOT = { ok: styles.dotOk, warning: styles.dotWarn };
const MODULES = ['thermal', 'setup', 'tyre_degradation', 'racing_line', 'slip', 'corners'];

export default function HealthDashboard({ health_summary }) {
  const { t } = useLanguage();
  if (!health_summary) return null;
  const o = OVERALL[health_summary.overall] ?? OVERALL.critical;

  return (
    <div className={`${styles.health} ${styles[`health${o.cls}`]}`} role="status" aria-label={t.healthAria}>
      <div className={styles.hStatus}>
        <span className={`${styles.hIcon} ${styles[`hIcon${o.cls}`]}`}><Icon name={o.icon} size={16} /></span>
        <div className={styles.hText}>
          <span className={styles.hTitle}>{t[`health_${o.key}`]}</span>
          <span className={styles.hSub}>{t[`health_${o.key}Sub`]}</span>
        </div>
      </div>

      <ul className={styles.modules}>
        {MODULES.map((key) => {
          const status = health_summary[key] ?? 'unavailable';
          const state = t[`healthState_${status}`] ?? t.healthState_unavailable;
          return (
            <li key={key} className={styles.module}>
              <span className={`${styles.dot} ${DOT[status] ?? styles.dotNa}`} aria-hidden="true" />
              {t[`healthMod_${key}`]}
              <span className={styles.modState}>{state}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
