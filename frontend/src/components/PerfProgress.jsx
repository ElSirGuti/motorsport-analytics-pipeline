import { useLanguage } from '../context/LanguageContext';
import css from './PerfProgress.module.css';

/**
 * Real stage progress. `stages`: [{ id, label, state: 'pending'|'running'|'done'|'error', pct?: 0..1 }].
 * The bar is the mean completion of the stages flagged `counts` (the background ones do not hold it back).
 */
export function StageProgress({ stages }) {
  const { t } = useLanguage();
  const counted = stages.filter((s) => s.counts !== false);
  const value = counted.length
    ? counted.reduce((acc, s) => acc + (s.state === 'done' || s.state === 'error' ? 1 : (s.state === 'running' ? (s.pct ?? 0) * 0.9 : 0)), 0) / counted.length
    : 0;
  const pct = Math.round(Math.min(1, value) * 100);
  const stateLabel = { pending: t.perfStatePending, running: t.perfStateRunning, done: t.perfStateDone, error: t.perfStateError };
  return (
    <div className={css.wrap} role="status" aria-live="polite">
      <div className={css.track} role="progressbar" aria-label={t.perfProgressAria} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div className={css.fill} style={{ width: `${pct}%` }} />
      </div>
      <ol className={css.steps}>
        {stages.map((s) => (
          <li key={s.id} className={css.step} data-state={s.state}>
            <span className={css.dot} aria-hidden="true" />
            <span>{s.label}</span>
            {s.state === 'running' && s.pct != null && <span className={css.pct}>{Math.round(s.pct * 100)}%</span>}
            <span className={css.sr}>{stateLabel[s.state]}</span>
          </li>
        ))}
      </ol>
      <div className={css.hint}>{t.shellProgressHint}</div>
    </div>
  );
}

/** Placeholder for the stint sections while /stint/analyze is still running. */
export function StintSkeleton() {
  const { t } = useLanguage();
  return (
    <div className={css.skeleton} aria-busy="true" role="status">
      <div className={css.skTitle}><span className="shell-spin" />{t.perfStintWaitTitle}</div>
      <div className={css.skSub}>{t.perfStintWaitSub}</div>
      <div className={css.skChart} />
      <div className={css.skRow} />
      <div className={css.skRow} />
      <div className={css.skRow} />
    </div>
  );
}
