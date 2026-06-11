import { useMemo } from 'react';

/**
 * Dibuja el mapa de la pista usando las coordenadas CarCoordX/Y
 * del canal de curvatura, con los Apexes marcados como pins.
 *
 * Los datos de curvatura incluyen Distance + Curvature, pero NO las
 * coordenadas XY directas — el backend las procesó internamente.
 * Por eso reconstruimos la forma visual desde el DataFrame `telemetria`
 * que sí tiene Speed_Fast como proxy de posición (NO tenemos XY aquí).
 *
 * Alternativa: usar los apexes con Distance para marcar líneas verticales
 * sobre el gráfico de Speed. El mapa de pista real necesita que el backend
 * exponga X/Y en la respuesta — lo haremos en una siguiente iteración.
 *
 * Por ahora: mini-sparkline de curvatura como "huella" del circuito.
 */
const TrackMap = ({ curvatura, apexes }) => {
  const { path, apexPoints, viewBox } = useMemo(() => {
    if (!curvatura || curvatura.length < 2) return { path: '', apexPoints: [], viewBox: '0 0 100 40' };

    const W = 800;
    const H = 120;

    // Normalizar distancia al eje X y curvatura al eje Y (invertido para que los picos vayan arriba)
    const dists = curvatura.map((r) => r.Distance);
    const kappas = curvatura.map((r) => r.Curvature);
    const maxD = Math.max(...dists);
    const maxK = Math.max(...kappas) || 1;

    const pts = curvatura.map((r, i) => {
      const x = (r.Distance / maxD) * W;
      const y = H - (r.Curvature / maxK) * (H * 0.85) - H * 0.05;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    });

    // Puntos de Apex
    const apexPts = (apexes || []).map((a, i) => ({
      x: ((a.Distance || 0) / maxD) * W,
      y: H - ((a.Curvature || 0) / maxK) * (H * 0.85) - H * 0.05,
      num: i + 1,
      speed: a.Speed,
      dist: a.Distance,
      radio: a.Curvature > 0 ? (1 / a.Curvature).toFixed(0) : '∞',
    }));

    return {
      path: pts.join(' '),
      apexPoints: apexPts,
      viewBox: `0 0 ${W} ${H + 30}`,
    };
  }, [curvatura, apexes]);

  if (!path) return null;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◎</span>
          Huella de Curvatura del Circuito
        </div>
        <span className="chart-zoom-badge">{apexes?.length || 0} curvas detectadas</span>
      </div>

      <svg
        viewBox={viewBox}
        style={{ width: '100%', height: 160, overflow: 'visible' }}
        aria-label="Mapa de curvatura del circuito"
      >
        <defs>
          <linearGradient id="trackGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#00D4FF" stopOpacity={0.9} />
            <stop offset="50%" stopColor="#a78bfa" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#00D4FF" stopOpacity={0.9} />
          </linearGradient>
          <filter id="apexGlow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Línea base */}
        <line x1="0" y1="120" x2="800" y2="120" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />

        {/* Relleno debajo de la curva */}
        <path
          d={`${path} L800,120 L0,120 Z`}
          fill="url(#trackGrad)"
          fillOpacity={0.12}
        />

        {/* Línea principal de curvatura */}
        <path
          d={path}
          fill="none"
          stroke="url(#trackGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Marcadores de Apex */}
        {apexPoints.map((a) => (
          <g key={a.num} filter="url(#apexGlow)">
            {/* Línea vertical */}
            <line
              x1={a.x} y1={a.y - 4}
              x2={a.x} y2={120}
              stroke="#FFB300"
              strokeWidth="1"
              strokeDasharray="3 2"
              strokeOpacity={0.5}
            />
            {/* Círculo del apex */}
            <circle cx={a.x} cy={a.y} r={5} fill="#FFB300" stroke="#1a1a2e" strokeWidth={1.5} />
            {/* Número */}
            <text
              x={a.x}
              y={a.y - 12}
              textAnchor="middle"
              fontSize="10"
              fill="#FFB300"
              fontFamily="Inter, sans-serif"
              fontWeight="700"
            >
              {a.num}
            </text>
            {/* Tooltip label abajo */}
            <text
              x={a.x}
              y={135}
              textAnchor="middle"
              fontSize="9"
              fill="rgba(255,255,255,0.45)"
              fontFamily="Inter, sans-serif"
            >
              {a.dist?.toFixed(0)}m
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
};

export default TrackMap;
