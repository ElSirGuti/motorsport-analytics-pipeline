const SummaryCard = ({ summary, metadata }) => {
  if (!summary) return null;

  const { total_time_delta, worst_corner, worst_corner_loss, num_corners_analyzed } = summary;
  const isPositive = total_time_delta > 0;
  const isNegative = total_time_delta < 0;

  const labelB = metadata?.label_b || 'Piloto B';

  return (
    <div className="fade-up">
      {/* Identity header */}
      {metadata && (
        <div className="identity-bar">
          <div className="identity-card identity-card--a">
            <div className="identity-card__badge">◉ Vuelta A · Referencia</div>
            <div className="identity-card__driver">{metadata.driver_a || '—'}</div>
            <div className="identity-card__vehicle">{metadata.vehicle_a || '—'}</div>
            {metadata.venue && (
              <div className="identity-card__venue">▶ {metadata.venue}</div>
            )}
          </div>

          <div className="identity-vs">VS</div>

          <div className="identity-card identity-card--b">
            <div className="identity-card__badge">◉ Vuelta B · Comparación</div>
            <div className="identity-card__driver">{metadata.driver_b || '—'}</div>
            <div className="identity-card__vehicle">{metadata.vehicle_b || '—'}</div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {metadata && !metadata.same_vehicle && (
        <div className="alert-banner alert-banner--warning">
          <span className="alert-banner__icon">⚠</span>
          <span>
            <strong>Vehículos distintos:</strong> {metadata.vehicle_a} vs {metadata.vehicle_b}.
            Los deltas reflejan diferencias mecánicas además del pilotaje.
          </span>
        </div>
      )}

      {metadata && !metadata.same_driver && metadata.same_vehicle && (
        <div className="alert-banner alert-banner--info">
          <span className="alert-banner__icon">ℹ</span>
          <span>
            Comparando <strong>{metadata.driver_a}</strong> vs <strong>{metadata.driver_b}</strong> en el mismo vehículo.
          </span>
        </div>
      )}

      {/* KPI cards */}
      <div className="kpi-grid">
        <div className={`kpi-card ${isPositive ? 'kpi-card--positive' : isNegative ? 'kpi-card--negative' : 'kpi-card--neutral'}`}>
          <div className="kpi-card__label">Delta Total</div>
          <div className={`kpi-card__value ${isPositive ? 'kpi-card__value--positive' : isNegative ? 'kpi-card__value--negative' : 'kpi-card__value--neutral'}`}>
            {total_time_delta > 0 ? '+' : ''}{total_time_delta.toFixed(3)}s
          </div>
          <div className="kpi-card__sub">
            {isPositive
              ? `${labelB} más lento`
              : isNegative
              ? `${labelB} más rápido`
              : 'Tiempos idénticos'}
          </div>
        </div>

        <div className="kpi-card kpi-card--info">
          <div className="kpi-card__label">Peor Curva</div>
          <div className="kpi-card__value kpi-card__value--positive">#{worst_corner}</div>
          <div className="kpi-card__sub">Pérdida: {worst_corner_loss.toFixed(3)}s</div>
        </div>

        <div className="kpi-card kpi-card--info">
          <div className="kpi-card__label">Curvas Analizadas</div>
          <div className="kpi-card__value kpi-card__value--neutral">{num_corners_analyzed}</div>
          <div className="kpi-card__sub">Detectadas automáticamente</div>
        </div>

        {metadata?.air_temp !== undefined && (
          <div className="kpi-card kpi-card--info">
            <div className="kpi-card__label">Temperatura</div>
            <div className="kpi-card__value kpi-card__value--info" style={{ fontSize: '1.5rem' }}>
              {metadata.air_temp.toFixed(1)}°C
            </div>
            <div className="kpi-card__sub">
              Pista: {metadata.road_temp ? `${metadata.road_temp.toFixed(1)}°C` : 'N/D'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SummaryCard;
