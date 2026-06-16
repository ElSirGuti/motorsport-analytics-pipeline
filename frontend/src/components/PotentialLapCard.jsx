import { useLanguage } from '../context/LanguageContext';

const PotentialLapCard = ({ tiempoPotencial, xgboostPred, historySamples }) => {
  const { t } = useLanguage();
  if (!tiempoPotencial) return null;

  const { theoretical_best_delta_s, potential_gain_s, use_reachable, sectors } = tiempoPotencial;
  const gainColor = potential_gain_s > 1.0 ? 'var(--red)' : potential_gain_s > 0.3 ? 'var(--amber)' : 'var(--green)';
  const modeLabel = use_reachable ? t.potentialReachable : t.potentialTheoretical;

  const STATUS_CONFIG = {
    consistente: { label: t.potentialStatusConsistent, color: 'var(--green)' },
    optimizable: { label: t.potentialStatusOptimizable, color: 'var(--amber)' },
    critico:     { label: t.potentialStatusCritical, color: 'var(--red)'   },
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◎</span> {t.potentialTitle} {modeLabel}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {historySamples != null && (
            <span className="chart-zoom-badge" style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>
              {historySamples} obs.
            </span>
          )}
          {xgboostPred && (
            <span className="chart-zoom-badge" style={{ color: 'var(--purple)', borderColor: 'rgba(124,58,237,0.3)', background: 'rgba(124,58,237,0.1)' }}>
              {t.potentialXGBoost}
            </span>
          )}
          {use_reachable && (
            <span className="chart-zoom-badge" style={{ color: 'var(--cyan)', borderColor: 'var(--cyan-border)', background: 'var(--cyan-dim)' }}>
              {t.potentialP10}
            </span>
          )}
        </div>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        {use_reachable
          ? t.potentialDescReachable
          : t.potentialDescTheoretical}
        {xgboostPred
          ? ` ${t.potentialDescXGBoost(xgboostPred.training_samples)}`
          : historySamples != null && historySamples < 30
          ? ` ${t.potentialDescXGBoostPending(historySamples)}`
          : ''}
      </p>

      <div className="summary-grid" style={{ marginBottom: 'var(--s4)' }}>
        <div className="summary-card summary-card--highlight">
          <div className="summary-card__label">{t.potentialImprovement}</div>
          <div className="summary-card__value" style={{ color: gainColor, fontSize: '2rem' }}>
            {potential_gain_s > 0 ? `-${potential_gain_s.toFixed(3)}s` : t.potentialOptimal}
          </div>
          <div className="summary-card__sub">
            {t.potentialRecoverable(use_reachable)}
          </div>
        </div>

        {xgboostPred && (
          <div className="summary-card">
            <div className="summary-card__label">🤖 XGBoost</div>
            <div className="summary-card__value" style={{ color: 'var(--purple)', fontSize: '1.6rem' }}>
              -{xgboostPred.predicted_gain_s.toFixed(3)}s
            </div>
            <div className="summary-card__sub">{t.potentialMLImprovement}</div>
          </div>
        )}

        <div className="summary-card">
          <div className="summary-card__label">{t.potentialDeltaVsReference}</div>
          <div className="summary-card__value" style={{ fontSize: '1.4rem', color: theoretical_best_delta_s < 0 ? 'var(--green)' : 'var(--text-2)' }}>
            {theoretical_best_delta_s >= 0 ? '+' : ''}{theoretical_best_delta_s.toFixed(3)}s
          </div>
          <div className="summary-card__sub">{t.potentialVsFastLap}</div>
        </div>
      </div>

      {sectors && sectors.length > 0 && (
        <div className="sector-table">
          <div className="sector-table__head">
            <span>{t.potentialSector}</span>
            <span>{t.potentialZone}</span>
            <span>{t.potentialCurrentDelta}</span>
            <span>{t.potentialReachableP(use_reachable)}</span>
            {use_reachable && <span>{t.potentialConsistency}</span>}
            <span>{t.potentialStatus}</span>
          </div>
          {sectors.map((s) => {
            const st = STATUS_CONFIG[s.estado] || STATUS_CONFIG.optimizable;
            const gainVal = use_reachable ? s.reachable_s : s.gain_posible_s;
            return (
              <div key={s.sector} className="sector-row">
                <span className="sector-row__num">{s.sector}</span>
                <span className="sector-row__desc">{s.zona || '—'}</span>
                <span className="sector-row__dist" style={{ color: s.delta_actual_s > 0 ? 'var(--red)' : 'var(--green)' }}>
                  {s.delta_actual_s > 0 ? '+' : ''}{s.delta_actual_s.toFixed(3)}s
                </span>
                <span className="sector-row__dist" style={{ color: gainVal > 0 ? 'var(--amber)' : 'var(--text-3)' }}>
                  {gainVal > 0 ? `-${gainVal.toFixed(3)}s` : '—'}
                </span>
                {use_reachable && (
                  <span className="sector-row__dist">
                    {s.consistency_pct != null
                      ? <span style={{ color: s.consistency_pct >= 80 ? 'var(--green)' : s.consistency_pct >= 50 ? 'var(--amber)' : 'var(--red)', fontWeight: 600 }}>
                          {s.consistency_pct.toFixed(0)}%
                        </span>
                      : <span style={{ color: 'var(--text-3)' }}>—</span>
                    }
                  </span>
                )}
                <span className="sector-row__delta" style={{ color: st.color }}>{st.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default PotentialLapCard;
