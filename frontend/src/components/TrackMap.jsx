import { useMemo } from 'react';

const PADDING = 32;

const TrackMap = ({ trackData }) => {
  const { points, viewBox } = useMemo(() => {
    if (!trackData || trackData.length < 2) return { points: [], viewBox: '0 0 400 300' };

    const xs = trackData.map((d) => d.x);
    const ys = trackData.map((d) => d.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);

    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;

    const W = 600;
    const H = 360;
    const innerW = W - PADDING * 2;
    const innerH = H - PADDING * 2;

    // Preserve aspect ratio
    const scale = Math.min(innerW / xRange, innerH / yRange);
    const offX = PADDING + (innerW - xRange * scale) / 2;
    const offY = PADDING + (innerH - yRange * scale) / 2;

    const pts = trackData.map((d) => ({
      x: offX + (d.x - xMin) * scale,
      y: offY + (yMax - d.y) * scale, // flip Y axis
    }));

    return {
      points: pts,
      viewBox: `0 0 ${W} ${H}`,
    };
  }, [trackData]);

  if (!points.length) return null;

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ') + ' Z';

  const startPt = points[0];
  const startPct = Math.floor(points.length * 0.5);
  const midPt    = points[startPct];

  return (
    <div className="card track-map-card">
      <div className="card__title">
        <span className="card__title-icon">◎</span>
        Mapa del Circuito
      </div>
      <div className="track-map-container">
        <svg
          viewBox={viewBox}
          width="100%"
          height="100%"
          style={{ display: 'block' }}
          aria-label="Mapa del circuito generado desde coordenadas GPS"
        >
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <linearGradient id="trackGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%"   stopColor="#00D4FF" />
              <stop offset="50%"  stopColor="#7C3AED" />
              <stop offset="100%" stopColor="#00D4FF" />
            </linearGradient>
          </defs>

          {/* Shadow path */}
          <path
            d={pathD}
            fill="none"
            stroke="rgba(0,212,255,0.08)"
            strokeWidth="12"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Main track line */}
          <path
            d={pathD}
            fill="none"
            stroke="url(#trackGrad)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#glow)"
          />

          {/* Start/Finish marker */}
          {startPt && (
            <>
              <circle cx={startPt.x} cy={startPt.y} r="8" fill="rgba(0,230,118,0.15)" />
              <circle cx={startPt.x} cy={startPt.y} r="4" fill="#00E676" />
              <text
                x={startPt.x + 10}
                y={startPt.y + 4}
                fontSize="9"
                fill="rgba(0,230,118,0.8)"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="700"
              >
                S/F
              </text>
            </>
          )}

          {/* Direction arrow at midpoint */}
          {midPt && points[startPct + 1] && (() => {
            const nx = points[startPct + 1].x - midPt.x;
            const ny = points[startPct + 1].y - midPt.y;
            const len = Math.sqrt(nx * nx + ny * ny) || 1;
            const ux = (nx / len) * 10;
            const uy = (ny / len) * 10;
            return (
              <polygon
                points={`${midPt.x + ux},${midPt.y + uy} ${midPt.x - uy * 0.5 - ux * 0.4},${midPt.y + ux * 0.5 - uy * 0.4} ${midPt.x + uy * 0.5 - ux * 0.4},${midPt.y - ux * 0.5 - uy * 0.4}`}
                fill="rgba(0,212,255,0.7)"
              />
            );
          })()}
        </svg>
      </div>
    </div>
  );
};

export default TrackMap;
