import React from 'react';

const SummaryCard = ({ summary, metadata }) => {
  if (!summary) return null;

  const { total_time_delta, worst_corner, worst_corner_loss, num_corners_analyzed } = summary;
  const isPositive = total_time_delta > 0;
  const isNegative = total_time_delta < 0;

  const labelA = metadata?.label_a || 'Piloto A';
  const labelB = metadata?.label_b || 'Piloto B';
  const diffVehicle = metadata && !metadata.same_vehicle;
  const diffDriver  = metadata && !metadata.same_driver;

  return (
    <div style={{ marginBottom: '2rem' }}>

      {/* ── Identity header ── */}
      {metadata && (
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '10px',
          marginBottom: '12px', alignItems: 'stretch',
        }}>
          {/* Lap A */}
          <div style={{
            flex: 1, minWidth: 200,
            padding: '12px 16px',
            background: 'rgba(0,212,255,0.07)',
            border: '1px solid rgba(0,212,255,0.25)',
            borderRadius: '10px',
          }}>
            <div style={{ fontSize: '0.7rem', color: '#00D4FF', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
              🔵 Vuelta A — Referencia
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#F1F5F9' }}>{metadata.driver_a || '—'}</div>
            <div style={{ fontSize: '0.8rem', color: '#94A3B8', fontFamily: 'monospace', marginTop: 2 }}>{metadata.vehicle_a || '—'}</div>
            {metadata.venue && <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: 4 }}>📍 {metadata.venue}</div>}
          </div>

          {/* VS divider */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 4px', color: '#64748B', fontWeight: 800, fontSize: '0.9rem',
          }}>VS</div>

          {/* Lap B */}
          <div style={{
            flex: 1, minWidth: 200,
            padding: '12px 16px',
            background: 'rgba(255,68,68,0.07)',
            border: '1px solid rgba(255,68,68,0.25)',
            borderRadius: '10px',
          }}>
            <div style={{ fontSize: '0.7rem', color: '#FF4444', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>
              🔴 Vuelta B — Comparación
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#F1F5F9' }}>{metadata.driver_b || '—'}</div>
            <div style={{ fontSize: '0.8rem', color: '#94A3B8', fontFamily: 'monospace', marginTop: 2 }}>{metadata.vehicle_b || '—'}</div>
          </div>
        </div>
      )}

      {/* ── Warning banners ── */}
      {diffVehicle && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '10px 16px', marginBottom: '8px',
          background: 'rgba(255,170,0,0.1)',
          border: '1px solid rgba(255,170,0,0.35)',
          borderRadius: '8px',
          fontSize: '0.85rem', color: '#FFAA00',
        }}>
          <span style={{ fontSize: '1.1rem' }}>⚠️</span>
          <span>
            <strong>Vehículos distintos:</strong> {metadata.vehicle_a} vs {metadata.vehicle_b}.
            Los deltas de tiempo y los puntos de frenado reflejan diferencias mecánicas, no solo de pilotaje.
          </span>
        </div>
      )}

      {diffDriver && !diffVehicle && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '10px 16px', marginBottom: '8px',
          background: 'rgba(0,212,255,0.07)',
          border: '1px solid rgba(0,212,255,0.2)',
          borderRadius: '8px',
          fontSize: '0.85rem', color: '#94A3B8',
        }}>
          <span style={{ fontSize: '1.1rem' }}>ℹ️</span>
          <span>Comparando <strong style={{ color: '#F1F5F9' }}>{metadata.driver_a}</strong> vs <strong style={{ color: '#F1F5F9' }}>{metadata.driver_b}</strong> en el mismo vehículo.</span>
        </div>
      )}

      {/* ── KPI cards ── */}
      <div className="summary animate-in">
        <div className={`summary__item ${isPositive ? 'summary__item--warning' : isNegative ? 'summary__item--highlight' : ''}`}>
          <div className="summary__label">Delta Total</div>
          <div className={`summary__value ${isPositive ? 'summary__value--positive' : isNegative ? 'summary__value--negative' : 'summary__value--neutral'}`}>
            {total_time_delta > 0 ? '+' : ''}{total_time_delta.toFixed(3)}s
          </div>
          <div className="dropzone__sublabel">
            {isPositive
              ? `${labelB} es más lento`
              : isNegative
              ? `${labelB} es más rápido`
              : 'Tiempos idénticos'}
          </div>
        </div>

        <div className="summary__item">
          <div className="summary__label">Peor Curva</div>
          <div className="summary__value">#{worst_corner}</div>
          <div className="dropzone__sublabel">Pérdida: {worst_corner_loss.toFixed(3)}s</div>
        </div>

        <div className="summary__item">
          <div className="summary__label">Curvas Analizadas</div>
          <div className="summary__value">{num_corners_analyzed}</div>
          <div className="dropzone__sublabel">Detectadas automáticamente</div>
        </div>

        {metadata && metadata.air_temp !== undefined && (
          <div className="summary__item">
            <div className="summary__label">Clima (ACTI)</div>
            <div className="summary__value" style={{ fontSize: '1.2rem' }}>
              🌡️ {metadata.air_temp.toFixed(1)}°C
            </div>
            <div className="dropzone__sublabel">
              Pista: {metadata.road_temp ? `${metadata.road_temp.toFixed(1)}°C` : 'N/D'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SummaryCard;
