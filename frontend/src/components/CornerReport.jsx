
const CLUSTER_COLOR = {
  'Ataque Limpio':         '#00E676',
  'Entrada Agresiva':      '#FF8C42',
  'Conservador':           '#00D4FF',
  'Salida Tardía':         '#FFB300',
  'Conducción Errática':   '#FF3D3D',
  'Ejecución Consistente': '#7C3AED',
};

const CornerReport = ({ corners, onCornerClick, activeCorner, dynamicEvents, cornerClusters, xgboostPred }) => {
  if (!corners || corners.length === 0) return null;

  const eventsByCorner = {};
  if (dynamicEvents && dynamicEvents.length > 0) {
    dynamicEvents.forEach((ev) => {
      if (!eventsByCorner[ev.curva]) eventsByCorner[ev.curva] = [];
      eventsByCorner[ev.curva].push(ev);
    });
  }

  const clusterByCorner = {};
  if (cornerClusters && cornerClusters.length > 0) {
    cornerClusters.forEach((c) => { clusterByCorner[c.corner_number] = c; });
  }

  const xgbByCorner = {};
  if (xgboostPred?.corner_predictions) {
    xgboostPred.corner_predictions.forEach((p) => { xgbByCorner[p.corner_number] = p; });
  }

  return (
    <div className="corners-section fade-up fade-up--d4">
      <div className="section-header">
        <div className="section-heading">
          <span>⬡</span>
          Análisis Detallado por Curva
        </div>
        {activeCorner != null && (
          <span className="active-corner-badge">Curva {activeCorner} seleccionada</span>
        )}
      </div>

      <div className="corner-grid">
        {corners.map((corner) => {
          const isLoss    = corner.time_loss_seconds > 0.01;
          const isGain    = corner.time_loss_seconds < -0.01;
          const isActive  = activeCorner === corner.corner_number;
          const hasZoom   = corner.start_distance != null && corner.end_distance != null;

          const cardType  = isLoss ? 'corner-card--loss' : isGain ? 'corner-card--gain' : 'corner-card--neutral';
          const deltaType = isLoss ? 'corner-card__delta--loss' : isGain ? 'corner-card__delta--gain' : 'corner-card__delta--neutral';

          const brakeDelta = corner.braking_delta_meters;
          const apexDelta  = corner.apex_speed_delta_kmh;
          const throttleDelta = corner.throttle_delta_meters;

          return (
            <div
              key={corner.corner_number}
              className={`corner-card ${cardType} ${hasZoom ? 'corner-card--clickable' : ''} ${isActive ? 'corner-card--active' : ''}`}
              onClick={() => {
                if (!onCornerClick || !hasZoom) return;
                onCornerClick(
                  isActive ? null : [Math.max(0, corner.start_distance - 50), corner.end_distance + 50],
                  isActive ? null : corner.corner_number
                );
              }}
              role={hasZoom ? 'button' : undefined}
              aria-label={hasZoom ? `Zoom en Curva ${corner.corner_number}` : undefined}
              tabIndex={hasZoom ? 0 : undefined}
              onKeyDown={hasZoom ? (e) => { if (e.key === 'Enter' || e.key === ' ') e.currentTarget.click(); } : undefined}
              title={hasZoom ? (isActive ? 'Clic para quitar zoom' : 'Clic para zoom') : ''}
            >
              {hasZoom && (
                <div className="corner-card__zoom-badge">
                  {isActive ? 'ZOOM ✕' : '⊕'}
                </div>
              )}

              <div className="corner-card__header">
                <div>
                  <div className="corner-card__name">Curva {corner.corner_number}</div>
                  {corner.start_distance != null && (
                    <div className="corner-card__zone">
                      {corner.start_distance.toFixed(0)}m – {corner.end_distance.toFixed(0)}m
                    </div>
                  )}
                </div>
                <div className={`corner-card__delta ${deltaType}`}>
                  {corner.time_loss_seconds > 0 ? '+' : ''}{corner.time_loss_seconds.toFixed(3)}s
                </div>
              </div>

              <div className="corner-metrics">
                <div className="corner-metric">
                  <span className="corner-metric__label">Punto de frenado</span>
                  <span className={`corner-metric__value ${brakeDelta < -2 ? 'corner-metric__value--bad' : brakeDelta > 2 ? 'corner-metric__value--good' : 'corner-metric__value--neutral'}`}>
                    {brakeDelta < 0
                      ? `${Math.abs(brakeDelta).toFixed(0)}m antes`
                      : brakeDelta > 0
                      ? `${brakeDelta.toFixed(0)}m después`
                      : 'Similar'}
                  </span>
                </div>

                <div className="corner-metric">
                  <span className="corner-metric__label">Velocidad apex</span>
                  <span className={`corner-metric__value ${apexDelta < -1 ? 'corner-metric__value--bad' : apexDelta > 1 ? 'corner-metric__value--good' : 'corner-metric__value--neutral'}`}>
                    {apexDelta > 0 ? '+' : ''}{apexDelta.toFixed(1)} km/h
                  </span>
                </div>

                <div className="corner-metric">
                  <span className="corner-metric__label">Aceleración</span>
                  <span className={`corner-metric__value ${throttleDelta > 2 ? 'corner-metric__value--bad' : throttleDelta < -2 ? 'corner-metric__value--good' : 'corner-metric__value--neutral'}`}>
                    {throttleDelta > 0
                      ? `${throttleDelta.toFixed(0)}m después`
                      : throttleDelta < 0
                      ? `${Math.abs(throttleDelta).toFixed(0)}m antes`
                      : 'Similar'}
                  </span>
                </div>
              </div>

              {eventsByCorner[corner.corner_number] && (
                <div className="corner-events">
                  {eventsByCorner[corner.corner_number].map((ev, ei) => (
                    <span key={ei} className={`corner-event-badge corner-event-badge--${ev.tipo}`}
                      title={ev.diagnostico}>
                      {ev.tipo === 'subviraje' ? 'SUB' : 'OVER'} · {ev.severidad}
                    </span>
                  ))}
                </div>
              )}

              {clusterByCorner[corner.corner_number] && (
                <div className="corner-cluster-badge" style={{
                  color: CLUSTER_COLOR[clusterByCorner[corner.corner_number].perfil] || 'var(--text-2)',
                  borderColor: (CLUSTER_COLOR[clusterByCorner[corner.corner_number].perfil] || '#4A5578') + '44',
                  background: (CLUSTER_COLOR[clusterByCorner[corner.corner_number].perfil] || '#4A5578') + '14',
                }}>
                  ◈ {clusterByCorner[corner.corner_number].perfil}
                </div>
              )}

              {/* Capa 2: Consistency badge */}
              {corner.consistency_pct != null && corner.n_hist_samples >= 3 && (
                <div className="corner-consistency">
                  <div className="corner-consistency__bar">
                    <div
                      className="corner-consistency__fill"
                      style={{
                        width: `${corner.consistency_pct}%`,
                        background: corner.consistency_pct >= 80
                          ? 'var(--green)' : corner.consistency_pct >= 50
                          ? 'var(--amber)' : 'var(--red)',
                      }}
                    />
                  </div>
                  <span className="corner-consistency__label" style={{
                    color: corner.consistency_pct >= 80
                      ? 'var(--green)' : corner.consistency_pct >= 50
                      ? 'var(--amber)' : 'var(--red)',
                  }}>
                    {corner.consistency_pct.toFixed(0)}% consistente
                  </span>
                  <span className="corner-consistency__n">({corner.n_hist_samples} vueltas)</span>
                </div>
              )}

              {/* Capa 3: XGBoost explanation chips */}
              {xgbByCorner[corner.corner_number]?.explanations?.length > 0 && (
                <div className="corner-xgb-chips">
                  {xgbByCorner[corner.corner_number].explanations.map((exp, ei) => (
                    <div key={ei} className="corner-xgb-chip">
                      <span className="corner-xgb-chip__feature">{exp.feature}</span>
                      <span className="corner-xgb-chip__gap" style={{ color: 'var(--red)' }}>
                        {exp.gap > 0 ? '+' : ''}{exp.gap.toFixed(1)}{exp.unit}
                      </span>
                      <span className="corner-xgb-chip__optimal" style={{ color: 'var(--text-3)' }}>
                        óptimo: {exp.optimal.toFixed(1)}{exp.unit}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {corner.description && (
                <div className="corner-card__description">{corner.description}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CornerReport;
