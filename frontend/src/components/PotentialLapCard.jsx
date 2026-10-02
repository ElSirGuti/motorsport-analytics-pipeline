import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import styles from './Analysis.module.css';
import { cleanLabel } from './analysisKit';

const PotentialLapCard = ({ tiempoPotencial, xgboostPred, historySamples }) => {
  const { t } = useLanguage();
  if (!tiempoPotencial) return null;

  const { theoretical_best_delta_s, potential_gain_s, use_reachable, sectors } = tiempoPotencial;
  const gainColor = potential_gain_s > 1.0 ? 'var(--bad)' : potential_gain_s > 0.3 ? 'var(--warn)' : 'var(--ok)';
  const modeLabel = use_reachable ? t.potentialReachable : t.potentialTheoretical;

  const STATUS_CONFIG = {
    consistente: { label: cleanLabel(t.potentialStatusConsistent), tone: 'ok' },
    optimizable: { label: cleanLabel(t.potentialStatusOptimizable), tone: 'warn' },
    critico: { label: cleanLabel(t.potentialStatusCritical), tone: 'bad' },
  };

  const actions = (
    <>
      {historySamples != null && <Badge>{historySamples} obs.</Badge>}
      {xgboostPred && <Badge tone="accent">{t.potentialXGBoost}</Badge>}
      {use_reachable && <Badge tone="accent">{t.potentialP10}</Badge>}
    </>
  );

  return (
    <Panel icon="target" title={`${t.potentialTitle} ${modeLabel}`} actions={actions}>
      <p className={styles.desc}>
        {use_reachable ? t.potentialDescReachable : t.potentialDescTheoretical}
        {xgboostPred
          ? ` ${t.potentialDescXGBoost(xgboostPred.training_samples)}`
          : historySamples != null && historySamples < 30
            ? ` ${t.potentialDescXGBoostPending(historySamples)}`
            : ''}
      </p>

      <div className={styles.hero}>
        <div className={`${styles.heroCard} ${styles.heroMain}`}>
          <div className={styles.mLabel}>{t.potentialImprovement}</div>
          <div className={styles.mValue} style={{ fontSize: 'var(--fs-2xl)', color: gainColor, margin: '4px 0' }}>
            {potential_gain_s > 0 ? `-${potential_gain_s.toFixed(3)} s` : t.potentialOptimal}
          </div>
          <div className={styles.sub}>{t.potentialRecoverable(use_reachable)}</div>
        </div>

        {xgboostPred && (
          <div className={styles.heroCard}>
            <div className={styles.mLabel}>XGBoost</div>
            <div className={styles.mValue} style={{ fontSize: 'var(--fs-xl)', color: 'var(--accent)', margin: '4px 0' }}>
              -{xgboostPred.predicted_gain_s.toFixed(3)} s
            </div>
            <div className={styles.sub}>{t.potentialMLImprovement}</div>
          </div>
        )}

        <div className={styles.heroCard}>
          <div className={styles.mLabel}>{t.potentialDeltaVsReference}</div>
          <div className={styles.mValue}
            style={{ fontSize: 'var(--fs-xl)', color: theoretical_best_delta_s < 0 ? 'var(--ok)' : 'var(--ink-1)', margin: '4px 0' }}>
            {theoretical_best_delta_s >= 0 ? '+' : ''}{theoretical_best_delta_s.toFixed(3)} s
          </div>
          <div className={styles.sub}>{t.potentialVsFastLap}</div>
        </div>
      </div>

      {sectors && sectors.length > 0 && (
        <div className={styles.tableWrap}>
          <table className="ui-table">
            <thead>
              <tr>
                <th>{t.potentialSector}</th>
                <th>{t.potentialZone}</th>
                <th className="is-num">{t.potentialCurrentDelta}</th>
                <th className="is-num">{t.potentialReachableP(use_reachable)}</th>
                {use_reachable && <th className="is-num">{t.potentialConsistency}</th>}
                <th>{t.potentialStatus}</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map((s) => {
                const st = STATUS_CONFIG[s.estado] || STATUS_CONFIG.optimizable;
                const gainVal = use_reachable ? s.reachable_s : s.gain_posible_s;
                const cons = s.consistency_pct;
                return (
                  <tr key={s.sector}>
                    <td className="num">{s.sector}</td>
                    <td>{s.zona || '—'}</td>
                    <td className="is-num" style={{ color: s.delta_actual_s > 0 ? 'var(--bad)' : 'var(--ok)' }}>
                      {s.delta_actual_s > 0 ? '+' : ''}{s.delta_actual_s.toFixed(3)} s
                    </td>
                    <td className="is-num" style={{ color: gainVal > 0 ? 'var(--warn)' : 'var(--ink-3)' }}>
                      {gainVal > 0 ? `-${gainVal.toFixed(3)} s` : '—'}
                    </td>
                    {use_reachable && (
                      <td className="is-num"
                        style={{ color: cons == null ? 'var(--ink-3)' : cons >= 80 ? 'var(--ok)' : cons >= 50 ? 'var(--warn)' : 'var(--bad)' }}>
                        {cons != null ? `${cons.toFixed(0)}%` : '—'}
                      </td>
                    )}
                    <td><Badge tone={st.tone}>{st.label}</Badge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
};

export default PotentialLapCard;
