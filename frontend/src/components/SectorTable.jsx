/**
 * SectorTable — Tabla de sectorización entre Apexes con Time Delta parcial
 * y barra de progreso visual para cada sector.
 */

const sign = (v) => (v > 0 ? '+' : '');

const SectorTable = ({ sectores, totalDelta }) => {
  if (!sectores || sectores.length === 0) return null;

  const maxAbs = Math.max(...sectores.map((s) => Math.abs(s.delta_parcial)));

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>⬡</span>
          Sectorización — Time Delta por Segmento
        </div>
        {totalDelta != null && (
          <span
            className="chart-zoom-badge"
            style={{ color: totalDelta > 0 ? 'var(--red)' : 'var(--green)' }}
          >
            Total: {sign(totalDelta)}{totalDelta.toFixed(3)}s
          </span>
        )}
      </div>

      <div className="sector-table">
        <div className="sector-table__head">
          <span>#</span>
          <span>Zona</span>
          <span>Metros</span>
          <span>Delta Parcial</span>
          <span>Barra</span>
        </div>

        {sectores.map((s) => {
          const isLoss = s.delta_parcial > 0.01;
          const isGain = s.delta_parcial < -0.01;
          const pct    = maxAbs > 0 ? Math.abs(s.delta_parcial) / maxAbs : 0;
          const color  = isLoss ? 'var(--red)' : isGain ? 'var(--green)' : 'rgba(255,255,255,0.3)';
          const longitud = (s.dist_fin - s.dist_inicio).toFixed(0);

          return (
            <div
              key={s.sector}
              className={`sector-row ${isLoss ? 'sector-row--loss' : isGain ? 'sector-row--gain' : ''}`}
            >
              <span className="sector-row__num">{s.sector}</span>
              <span className="sector-row__desc">{s.descripcion}</span>
              <span className="sector-row__dist">{longitud}m</span>
              <span
                className="sector-row__delta"
                style={{ color }}
              >
                {sign(s.delta_parcial)}{s.delta_parcial.toFixed(3)}s
              </span>
              <span className="sector-row__bar">
                <span
                  className="sector-row__bar-fill"
                  style={{
                    width: `${(pct * 100).toFixed(1)}%`,
                    background: color,
                    opacity: 0.85,
                  }}
                />
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SectorTable;
