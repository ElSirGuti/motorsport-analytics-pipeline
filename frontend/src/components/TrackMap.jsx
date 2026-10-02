import { useMemo, useRef, useEffect } from 'react';
import { getCursorDistance } from '../api/cursorStore';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Icon } from './ui';
import { COLOR } from './chartTheme';
import styles from './TrackMap.module.css';

const PADDING = 32;

const LABEL = {
  fontSize: 11, stroke: '#0d1014', strokeWidth: 3, paintOrder: 'stroke',
  fontFamily: 'JetBrains Mono, monospace', fontWeight: 600,
};

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
  const { t } = useLanguage();
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

  const fixedPos = useMemo(
    () => getInterpolatedPosition(points, distances, fixedDistance),
    [points, distances, fixedDistance],
  );
  const cursorRingRef = useRef(null);
  const cursorDotRef = useRef(null);
  const cursorLabelRef = useRef(null);

  useEffect(() => {
    if (!points.length) return;
    let rafId;

    const loop = () => {
      const dist = getCursorDistance();
      const pos = dist != null ? getInterpolatedPosition(points, distances, dist) : null;

      [cursorRingRef.current, cursorDotRef.current].forEach((el) => {
        if (!el) return;
        if (pos) {
          el.setAttribute('cx', pos.x);
          el.setAttribute('cy', pos.y);
          el.style.display = '';
        } else {
          el.style.display = 'none';
        }
      });
      if (cursorLabelRef.current) {
        if (pos && dist != null) {
          const labelOffsetX = pos.x > 540 ? -45 : 12;
          cursorLabelRef.current.setAttribute('x', pos.x + labelOffsetX);
          cursorLabelRef.current.setAttribute('y', pos.y + 4);
          cursorLabelRef.current.textContent = `${dist.toFixed(0)}m`;
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
    <Panel
      icon="map"
      title={t.trackMapTitle}
      actions={fixedDistance != null && (
        <button
          type="button"
          className="ui-btn ui-btn--sm ui-btn--ghost"
          onClick={onClearFixed}
          title={t.trackMapClear}
          aria-label={t.trackMapClear}
        >
          <Icon name="x" size={14} />
          {fixedDistance.toFixed(0)} m
        </button>
      )}
    >
      <div className={styles.container}>
        <svg viewBox={viewBox} width="100%" height="100%" style={{ display: 'block' }} role="img" aria-label={t.trackMapAria}>
          <path d={pathD} fill="none" stroke="#323b48" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
          <path d={pathD} fill="none" stroke="#a3adbb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

          <circle cx={startPt.x} cy={startPt.y} r="5" fill={COLOR.ok} stroke="#0d1014" strokeWidth="2" />
          <text x={startPt.x + 10} y={startPt.y + 4} fill={COLOR.ok} {...LABEL}>S/F</text>

          {midPt && points[startPct + 1] && (() => {
            const nx = points[startPct + 1].x - midPt.x;
            const ny = points[startPct + 1].y - midPt.y;
            const len = Math.sqrt(nx * nx + ny * ny) || 1;
            const ux = (nx / len) * 10;
            const uy = (ny / len) * 10;
            return (
              <polygon
                points={`${midPt.x + ux},${midPt.y + uy} ${midPt.x - uy * 0.5 - ux * 0.4},${midPt.y + ux * 0.5 - uy * 0.4} ${midPt.x + uy * 0.5 - ux * 0.4},${midPt.y - ux * 0.5 - uy * 0.4}`}
                fill="#e8ecf2"
              />
            );
          })()}

          {/* Fixed position marker */}
          {fixedPos && (
            <>
              <circle cx={fixedPos.x} cy={fixedPos.y} r="10" fill="none" stroke={COLOR.warn} strokeWidth="1.5" />
              <circle cx={fixedPos.x} cy={fixedPos.y} r="4" fill={COLOR.warn} />
              <text x={fixedPos.x + (fixedPos.x > 540 ? -48 : 14)} y={fixedPos.y + 4} fill={COLOR.warn} {...LABEL}>
                {fixedDistance?.toFixed(0)}m
              </text>
            </>
          )}

          {/* Cursor position marker, driven directly by rAF */}
          <circle ref={cursorRingRef} r="11" fill="none" stroke={COLOR.accent} strokeWidth="1.5" style={{ display: 'none' }} />
          <circle ref={cursorDotRef} r="4.5" fill={COLOR.accent} stroke="#0d1014" strokeWidth="1.5" style={{ display: 'none' }} />
          <text ref={cursorLabelRef} fill={COLOR.accent} {...LABEL} style={{ display: 'none' }} />
        </svg>
      </div>
    </Panel>
  );
};

export default TrackMap;
