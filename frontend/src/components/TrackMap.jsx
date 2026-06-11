import { useMemo, useRef, useEffect, useState } from 'react';
import { getCursorDistance } from '../api/cursorStore';

const PADDING = 32;

function getInterpolatedPosition(points, distances, targetDist) {
  if (points.length === 0 || targetDist == null) return null;
  if (points.length === 1) return points[0];
  if (targetDist <= distances[0]) return points[0];
  if (targetDist >= distances[distances.length - 1]) return points[points.length - 1];

  let lo = 0;
  let hi = distances.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (distances[mid] <= targetDist) lo = mid;
    else hi = mid;
  }

  const t = (targetDist - distances[lo]) / (distances[hi] - distances[lo]);
  return {
    x: points[lo].x + (points[hi].x - points[lo].x) * t,
    y: points[lo].y + (points[hi].y - points[lo].y) * t,
  };
}

const TrackMap = ({ trackData, fixedDistance, onClearFixed }) => {
  const { points, distances, viewBox } = useMemo(() => {
    if (!trackData || trackData.length < 2) return { points: [], distances: [], viewBox: '0 0 400 300' };

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

    const scale = Math.min(innerW / xRange, innerH / yRange);
    const offX = PADDING + (innerW - xRange * scale) / 2;
    const offY = PADDING + (innerH - yRange * scale) / 2;

    const pts = trackData.map((d) => ({
      x: offX + (d.x - xMin) * scale,
      y: offY + (yMax - d.y) * scale,
    }));

    const dists = trackData.map((d) => d.distance ?? 0);

    return { points: pts, distances: dists, viewBox: `0 0 ${W} ${H}` };
  }, [trackData]);

  const [fixedPos, setFixedPos] = useState(null);
  const cursorRingRef = useRef(null);
  const cursorDotRef = useRef(null);
  const cursorLabelRef = useRef(null);

  useEffect(() => {
    setFixedPos(getInterpolatedPosition(points, distances, fixedDistance));
  }, [points, distances, fixedDistance]);

  useEffect(() => {
    if (!points.length) return;
    let rafId;

    const loop = () => {
      const dist = getCursorDistance();
      const pos = dist != null ? getInterpolatedPosition(points, distances, dist) : null;

      if (cursorRingRef.current) {
        if (pos) {
          cursorRingRef.current.setAttribute('cx', pos.x);
          cursorRingRef.current.setAttribute('cy', pos.y);
          cursorRingRef.current.style.display = '';
        } else {
          cursorRingRef.current.style.display = 'none';
        }
      }
      if (cursorDotRef.current) {
        if (pos) {
          cursorDotRef.current.setAttribute('cx', pos.x);
          cursorDotRef.current.setAttribute('cy', pos.y);
          cursorDotRef.current.style.display = '';
        } else {
          cursorDotRef.current.style.display = 'none';
        }
      }
      if (cursorLabelRef.current) {
        if (pos && dist != null) {
          const lbl = `${dist.toFixed(0)}m`;
          const labelOffsetX = pos.x > 540 ? -45 : 10;
          cursorLabelRef.current.setAttribute('x', pos.x + labelOffsetX);
          cursorLabelRef.current.setAttribute('y', pos.y + 4);
          cursorLabelRef.current.textContent = lbl;
          cursorLabelRef.current.style.display = '';
        } else {
          cursorLabelRef.current.style.display = 'none';
        }
      }

      rafId = requestAnimationFrame(loop);
    };

    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [points, distances]);

  if (!points.length) return null;

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ') + ' Z';

  const startPt = points[0];
  const startPct = Math.floor(points.length * 0.5);
  const midPt = points[startPct];

  return (
    <div className="card track-map-card">
      <div className="card__title">
        <span className="card__title-icon">◎</span>
        Mapa del Circuito
        {fixedDistance != null && (
          <button
            className="track-map-clear-btn"
            onClick={onClearFixed}
            title="Quitar punto fijo"
            aria-label="Quitar punto fijo"
          >
            ✕
          </button>
        )}
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
            <filter id="trackGlow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="cursorGlow">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="fixedGlow">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <linearGradient id="trackGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%"   stopColor="#00D4FF" />
              <stop offset="50%"  stopColor="#7C3AED" />
              <stop offset="100%" stopColor="#00D4FF" />
            </linearGradient>
          </defs>

          <path
            d={pathD}
            fill="none"
            stroke="rgba(0,212,255,0.08)"
            strokeWidth="12"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          <path
            d={pathD}
            fill="none"
            stroke="url(#trackGrad)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#trackGlow)"
          />

          {startPt && (
            <>
              <circle cx={startPt.x} cy={startPt.y} r="8" fill="rgba(0,230,118,0.15)" />
              <circle cx={startPt.x} cy={startPt.y} r="4" fill="#00E676" />
              <text
                x={startPt.x + 12}
                y={startPt.y + 5}
                fontSize="11"
                fill="#00E676"
                stroke="rgba(6,10,20,0.85)"
                strokeWidth="3"
                paintOrder="stroke"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="700"
              >
                S/F
              </text>
            </>
          )}

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

          {/* Fixed position marker */}
          {fixedPos && (
            <>
              <circle cx={fixedPos.x} cy={fixedPos.y} r="12" fill="rgba(255,61,61,0.15)" />
              <circle cx={fixedPos.x} cy={fixedPos.y} r="6" fill="#FF3D3D" filter="url(#fixedGlow)" />
              <text
                x={fixedPos.x + (fixedPos.x > 540 ? -48 : 12)}
                y={fixedPos.y + 5}
                fontSize="11"
                fill="#FF3D3D"
                stroke="rgba(6,10,20,0.85)"
                strokeWidth="3"
                paintOrder="stroke"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="700"
              >
                {fixedDistance?.toFixed(0)}m
              </text>
            </>
          )}

          {/* Cursor position marker — manipulated directly by rAF */}
          <circle ref={cursorRingRef} className="track-cursor-ring" r="14" fill="rgba(0,212,255,0.1)" style={{ display: 'none' }} />
          <circle ref={cursorDotRef} className="track-cursor-dot" r="5" fill="#00D4FF" filter="url(#cursorGlow)" style={{ display: 'none' }} />
          <text ref={cursorLabelRef} fontSize="11" fill="#00D4FF" stroke="rgba(6,10,20,0.85)" strokeWidth="3" paintOrder="stroke" fontFamily="JetBrains Mono, monospace" fontWeight="700" style={{ display: 'none' }} />
        </svg>
      </div>
    </div>
  );
};

export default TrackMap;