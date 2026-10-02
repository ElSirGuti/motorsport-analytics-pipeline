import { useLanguage } from '../context/LanguageContext';
import { Icon } from './ui';
import styles from './Analysis.module.css';

const TEXT = {
  en: {
    ok: 'All systems nominal', warning: 'Review modules', critical: 'Limited data',
    okSub: 'Every analysis module reported data', warningSub: 'Some modules need attention', criticalSub: 'Results may be incomplete',
    states: { ok: 'OK', warning: 'Check', unavailable: 'N/A' },
    modules: { thermal: 'Thermal', setup: 'Setup', tyre_degradation: 'Tyre deg.', racing_line: 'Racing line', slip: 'Slip', corners: 'Corners' },
    aria: 'Analysis health',
  },
  es: {
    ok: 'Todos los sistemas OK', warning: 'Revisar módulos', critical: 'Datos limitados',
    okSub: 'Todos los módulos de análisis reportaron datos', warningSub: 'Algunos módulos requieren atención', criticalSub: 'Los resultados pueden estar incompletos',
    states: { ok: 'OK', warning: 'Revisar', unavailable: 'N/D' },
    modules: { thermal: 'Térmico', setup: 'Setup', tyre_degradation: 'Deg. neumáticos', racing_line: 'Línea de carrera', slip: 'Deslizamiento', corners: 'Curvas' },
    aria: 'Salud del análisis',
  },
};

const OVERALL = {
  ok: { key: 'ok', cls: 'Ok', icon: 'check' },
  warning: { key: 'warning', cls: 'Warn', icon: 'alert' },
  critical: { key: 'critical', cls: 'Bad', icon: 'alert' },
};
const DOT = { ok: styles.dotOk, warning: styles.dotWarn };
const MODULES = ['thermal', 'setup', 'tyre_degradation', 'racing_line', 'slip', 'corners'];

export default function HealthDashboard({ health_summary }) {
  const { lang } = useLanguage();
  if (!health_summary) return null;
  const L = TEXT[lang] || TEXT.en;
  const o = OVERALL[health_summary.overall] ?? OVERALL.critical;

  return (
    <div className={`${styles.health} ${styles[`health${o.cls}`]}`} role="status" aria-label={L.aria}>
      <div className={styles.hStatus}>
        <span className={`${styles.hIcon} ${styles[`hIcon${o.cls}`]}`}><Icon name={o.icon} size={16} /></span>
        <div className={styles.hText}>
          <span className={styles.hTitle}>{L[o.key]}</span>
          <span className={styles.hSub}>{L[`${o.key}Sub`]}</span>
        </div>
      </div>

      <ul className={styles.modules}>
        {MODULES.map((key) => {
          const status = health_summary[key] ?? 'unavailable';
          const state = L.states[status] ?? L.states.unavailable;
          return (
            <li key={key} className={styles.module}>
              <span className={`${styles.dot} ${DOT[status] ?? styles.dotNa}`} aria-hidden="true" />
              {L.modules[key]}
              <span className={styles.modState}>{state}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
