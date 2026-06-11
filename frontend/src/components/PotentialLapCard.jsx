const STATUS_CONFIG = {
  consistente: { label: '✓ Consistente',    color: 'var(--green)' },
  optimizable: { label: '⚠ Optimizable',    color: 'var(--amber)' },
  critico:     { label: '▲ Pérdida Crítica', color: 'var(--red)'   },
};

const PotentialLapCard = ({ tiempoPotencial, xgboostPred, historySamples }) => {
  if (!tiempoPotencial) return null;

  const { theoretical_best_delta_s, potential_gain_s, use_reachable, sectors } = tiempoPotencial;
  const gainColor = potential_gain_s > 1.0 ? 'var(--red)' : potential_gain_s > 0.3 ? 'var(--amber)' : 'var(--green)';
  const modeLabel = use_reachable ? 'Reachable Lap — P10 histórico' : 'Theoretical Best Lap';

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◎</span> Tiempo Potencial — {modeLabel}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {historySamples != null && (
            <span className="chart-zoom-badge" style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>
              {historySamples} obs.
            </span>
          )}
          {xgboostPred && (
            <span className="chart-zoom-badge" style={{ color: 'var(--purple)', borderColor: 'rgba(124,58,237,0.3)', background: 'rgba(124,58,237,0.1)' }}>
              XGBoost activo
            </span>
          )}
          {use_reachable && (
            <span className="chart-zoom-badge" style={{ color: 'var(--cyan)', borderColor: 'var(--cyan-border)', background: 'var(--cyan-dim)' }}>
              P10 histórico
            </span>
          )}
        </div>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        {use_reachable
          ? 'Basado en el percentil-10 de cada curva en tu historial — tiempo que logras en el 10% de tus mejores intentos.'
          : 'Suma de los mejores tiempos parciales disponibles (método F1/DTM).'}
        {xgboostPred
          ? ` XGBoost estima el óptimo con ${xgboostPred.training_samples} observaciones históricas.`
          : historySamples != null && historySamples < 30
          ? ` XGBoost se activa a partir de 30 observaciones (${30 - historySamples} restantes).`
          : ''}
      </p>

      {/* KPIs */}
      <div className="summary-grid" style={{ marginBottom: 'var(--s4)' }}>
        <div className="summary-card summary-card--highlight">
          <div className="summary-card__label">⏱ Potencial de Mejora</div>
          <div className="summary-card__value" style={{ color: gainColor, fontSize: '2rem' }}>
            {potential_gain_s > 0 ? `-${potential_gain_s.toFixed(3)}s` : '≈ Óptimo'}
          </div>
          <div className="summary-card__sub">
            {use_reachable ? 'recuperable (P10 por curva)' : 'tiempo recuperable en vuelta lenta'}
          </div>
        </div>

        {xgboostPred && (
          <div className="summary-card">
            <div className="summary-card__label">🤖 XGBoost</div>
            <div className="summary-card__value" style={{ color: 'var(--purple)', fontSize: '1.6rem' }}>
              -{xgboostPred.predicted_gain_s.toFixed(3)}s
            </div>
            <div className="summary-card__sub">mejora estimada por ML</div>
          </div>
        )}

        <div className="summary-card">
          <div className="summary-card__label">📊 Delta vs Referencia</div>
          <div className="summary-card__value" style={{ fontSize: '1.4rem', color: theoretical_best_delta_s < 0 ? 'var(--green)' : 'var(--text-2)' }}>
            {theoretical_best_delta_s >= 0 ? '+' : ''}{theoretical_best_delta_s.toFixed(3)}s
          </div>
          <div className="summary-card__sub">frente a la vuelta rápida</div>
        </div>
      </div>

      {/* Tabla de sectores */}
      {sectors && sectors.length > 0 && (
        <div className="sector-table">
          <div className="sector-table__head">
            <span>Sector</span>
            <span>Zona</span>
            <span>Delta actual</span>
            <span>{use_reachable ? 'Reachable (P10)' : 'Recuperable'}</span>
            {use_reachable && <span>Consistencia</span>}
            <span>Estado</span>
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
