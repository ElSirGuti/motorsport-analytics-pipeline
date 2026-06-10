import React from 'react';

const CornerReport = ({ corners, onCornerClick, activeCorner }) => {
  if (!corners || corners.length === 0) return null;

  return (
    <div className="animate-in animate-in--delay-4">
      <h2 className="section-title">
        <span className="section-title__icon">🔍</span>
        Análisis Detallado por Curva
        {activeCorner != null && (
          <span style={{
            marginLeft: '1rem',
            fontSize: '0.8rem',
            fontWeight: 400,
            color: '#00D4FF',
            background: 'rgba(0,212,255,0.1)',
            padding: '2px 10px',
            borderRadius: '20px',
            border: '1px solid rgba(0,212,255,0.3)',
          }}>
            🔍 Curva {activeCorner} seleccionada
          </span>
        )}
      </h2>
      
      <div className="corner-grid">
        {corners.map((corner, index) => {
          const isLoss = corner.time_loss_seconds > 0.01;
          const isGain = corner.time_loss_seconds < -0.01;
          const isActive = activeCorner === corner.corner_number;
          
          let cardClass = 'corner-card--neutral';
          if (isLoss) cardClass = 'corner-card--loss';
          if (isGain) cardClass = 'corner-card--gain';

          const hasZoom = corner.start_distance != null && corner.end_distance != null;

          return (
            <div 
              key={index} 
              className={`corner-card ${cardClass}`}
              onClick={() => {
                if (onCornerClick && hasZoom) {
                  onCornerClick(
                    isActive ? null : [Math.max(0, corner.start_distance - 50), corner.end_distance + 50],
                    isActive ? null : corner.corner_number
                  );
                }
              }}
              style={{
                cursor: hasZoom ? 'pointer' : 'default',
                transition: 'transform 0.18s, box-shadow 0.18s, outline 0.18s',
                outline: isActive ? '2px solid #00D4FF' : '2px solid transparent',
                boxShadow: isActive ? '0 0 18px rgba(0,212,255,0.4)' : undefined,
                transform: isActive ? 'scale(1.03)' : undefined,
              }}
              title={hasZoom ? (isActive ? 'Clic para quitar zoom' : 'Clic para hacer zoom en esta curva') : ''}
            >
              {/* Zoom badge */}
              {hasZoom && (
                <div style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  fontSize: '0.65rem',
                  color: isActive ? '#00D4FF' : 'rgba(255,255,255,0.3)',
                  transition: 'color 0.2s',
                }}>
                  {isActive ? '🔍 ZOOM ACTIVO' : '🔍'}
                </div>
              )}

              <div className="corner-card__header">
                <div className="corner-card__number">Curva {corner.corner_number}</div>
                <div className={`corner-card__delta ${isLoss ? 'corner-card__delta--loss' : isGain ? 'corner-card__delta--gain' : ''}`}>
                  {corner.time_loss_seconds > 0 ? '+' : ''}{corner.time_loss_seconds.toFixed(3)}s
                </div>
              </div>
              
              <div className="corner-card__metrics">
                <div className="corner-card__metric">
                  <span className="corner-card__metric-label">Punto de Frenado</span>
                  <span className={`corner-card__metric-value ${corner.braking_delta_meters < -2 ? 'corner-card__metric-value--negative' : corner.braking_delta_meters > 2 ? 'corner-card__metric-value--positive' : ''}`}>
                    {corner.braking_delta_meters < 0 ? `${Math.abs(corner.braking_delta_meters).toFixed(0)}m ANTES` : 
                     corner.braking_delta_meters > 0 ? `${corner.braking_delta_meters.toFixed(0)}m DESPUÉS` : 
                     'Similar'}
                  </span>
                </div>
                
                <div className="corner-card__metric">
                  <span className="corner-card__metric-label">Velocidad Apex</span>
                  <span className={`corner-card__metric-value ${corner.apex_speed_delta_kmh < -1 ? 'corner-card__metric-value--negative' : corner.apex_speed_delta_kmh > 1 ? 'corner-card__metric-value--positive' : ''}`}>
                    {corner.apex_speed_delta_kmh > 0 ? '+' : ''}{corner.apex_speed_delta_kmh.toFixed(1)} km/h
                  </span>
                </div>
                
                <div className="corner-card__metric">
                  <span className="corner-card__metric-label">Aceleración</span>
                  <span className={`corner-card__metric-value ${corner.throttle_delta_meters > 2 ? 'corner-card__metric-value--negative' : corner.throttle_delta_meters < -2 ? 'corner-card__metric-value--positive' : ''}`}>
                    {corner.throttle_delta_meters > 0 ? `${corner.throttle_delta_meters.toFixed(0)}m DESPUÉS` : 
                     corner.throttle_delta_meters < 0 ? `${Math.abs(corner.throttle_delta_meters).toFixed(0)}m ANTES` : 
                     'Similar'}
                  </span>
                </div>

                {corner.start_distance != null && (
                  <div className="corner-card__metric" style={{ marginTop: '4px' }}>
                    <span className="corner-card__metric-label">Zona</span>
                    <span className="corner-card__metric-value" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {corner.start_distance.toFixed(0)}m – {corner.end_distance.toFixed(0)}m
                    </span>
                  </div>
                )}
              </div>
              
              <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {corner.description}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CornerReport;
