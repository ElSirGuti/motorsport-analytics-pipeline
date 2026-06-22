import { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import { useLanguage } from '../context/LanguageContext';

const PAD = { top: 24, right: 24, bottom: 40, left: 44 };
const CSS_H = 340;

function makeCoordFns(cssW, limit) {
  const range = limit * 1.15 * 2;
  const plotW = cssW - PAD.left - PAD.right;
  const plotH = CSS_H - PAD.top - PAD.bottom;
  const toX = (v) => PAD.left + (v + limit * 1.15) / range * plotW;
  const toY = (v) => PAD.top + (limit * 1.15 - v) / range * plotH;
  return { toX, toY, plotW, plotH, range };
}

const GGStat = ({ label, value, color }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <span style={{ fontSize: '0.63rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
    <span style={{ fontSize: '0.85rem', fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
  </div>
);

const effColor = (eff, alpha = 1) => {
  if (eff >= 90) return `rgba(0,230,118,${alpha})`;
  if (eff >= 72) return `rgba(255,179,0,${alpha})`;
  return `rgba(255,61,61,${alpha})`;
};

const REC_MAP = {
  braking: {
    low: 'Trail braking underused. Carry brake pressure into turn entry to keep the nose planted and maximise the braking zone.',
    mid: 'Trail braking present but inconsistent. Focus on a more progressive release through turn-in.',
    high: 'Braking zone well-exploited.',
  },
  traction: {
    low: 'Early or abrupt throttle detected. Progressive application from apex outward will fill this quadrant.',
    mid: 'Traction has headroom. Slightly later initial input with an earlier full-throttle point at exit.',
    high: 'Traction phase well-optimised.',
  },
  left: {
    low: 'Understeer or cautious line in left-handers. Review entry speed, turn-in point, and mid-corner rotation.',
    mid: 'Left-corner grip available. Carry slightly more mid-corner speed to fill the lateral zone.',
    high: 'Left-corner grip well-utilised.',
  },
  right: {
    low: 'Understeer or cautious line in right-handers. Check trail-brake balance and rotation timing.',
    mid: 'Right-corner grip available. A later apex may improve exit speed.',
    high: 'Right-corner grip well-utilised.',
  },
};

const GGDiagramChart = ({ ggData, gLimit }) => {
  const { t } = useLanguage();
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  const fastPoints = useMemo(() => {
    const src = ggData?.fast ?? (Array.isArray(ggData) ? ggData.filter(d => d._lap === 'fast') : []);
    return src.map((d) => ({ lat: d.lat, lon: d.lon, eff: d.eff ?? 0, _lap: 'fast' }));
  }, [ggData]);

  const slowPoints = useMemo(() => {
    const src = ggData?.slow ?? (Array.isArray(ggData) ? ggData.filter(d => d._lap === 'slow') : []);
    return src.map((d) => ({ lat: d.lat, lon: d.lon, eff: d.eff ?? 0, _lap: 'slow' }));
  }, [ggData]);

  const limit = gLimit || 1.3;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = container.clientWidth;
    canvas.width = cssW * dpr;
    canvas.height = CSS_H * dpr;
    canvas.style.width = cssW + 'px';
    canvas.style.height = CSS_H + 'px';

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const { toX, toY, plotW, plotH, range } = makeCoordFns(cssW, limit);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    [-limit, -limit * 0.5, 0, limit * 0.5, limit].forEach(v => {
      ctx.beginPath(); ctx.moveTo(toX(v), PAD.top); ctx.lineTo(toX(v), PAD.top + plotH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(PAD.left, toY(v)); ctx.lineTo(PAD.left + plotW, toY(v)); ctx.stroke();
    });

    // Friction circle
    const cx = toX(0);
    const cy = toY(0);
    const r = limit / range * plotW;
    ctx.strokeStyle = 'rgba(255,255,255,0.22)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Center crosshair
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx, PAD.top); ctx.lineTo(cx, PAD.top + plotH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(PAD.left, cy); ctx.lineTo(PAD.left + plotW, cy); ctx.stroke();

    // Quadrant labels — placed near each axis half, just off the crosshair
    ctx.font = 'bold 7.5px JetBrains Mono, monospace';
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.textAlign = 'right';
    ctx.fillText('← BRAKING', cx - 8, cy - 5);
    ctx.textAlign = 'left';
    ctx.fillText('TRACTION →', cx + 8, cy - 5);
    ctx.textAlign = 'center';
    ctx.fillText('TURN LEFT ↑', cx, PAD.top + 12);
    ctx.fillText('↓ TURN RIGHT', cx, PAD.top + plotH - 5);

    // Points — slow below fast
    slowPoints.forEach(({ lat, lon, eff }) => {
      ctx.beginPath();
      ctx.arc(toX(lon), toY(lat), 2, 0, Math.PI * 2);
      ctx.fillStyle = effColor(eff, 0.5);
      ctx.fill();
    });
    fastPoints.forEach(({ lat, lon, eff }) => {
      ctx.beginPath();
      ctx.arc(toX(lon), toY(lat), 2, 0, Math.PI * 2);
      ctx.fillStyle = effColor(eff, 0.78);
      ctx.fill();
    });

    // Axis tick values
    ctx.fillStyle = 'rgba(255,255,255,0.25)';
    ctx.font = '9px JetBrains Mono, monospace';
    [-limit, -limit * 0.5, 0, limit * 0.5, limit].forEach(v => {
      ctx.textAlign = 'center';
      ctx.fillText(v.toFixed(1), toX(v), PAD.top + plotH + 16);
      ctx.textAlign = 'right';
      ctx.fillText(v.toFixed(1), PAD.left - 4, toY(v) + 3);
    });
  }, [fastPoints, slowPoints, limit]);

  useEffect(() => {
    draw();
    const ro = new ResizeObserver(draw);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [draw]);

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const { toX, toY } = makeCoordFns(container.clientWidth, limit);
    let nearest = null;
    let minDist = 18;
    [...slowPoints, ...fastPoints].forEach(p => {
      const dist = Math.hypot(mx - toX(p.lon), my - toY(p.lat));
      if (dist < minDist) { minDist = dist; nearest = { ...p, screenX: mx, screenY: my }; }
    });
    setTooltip(nearest);
  }, [fastPoints, slowPoints, limit]);

  const stats = useMemo(() => {
    if (!fastPoints.length) return null;
    const avgE = (pts) => pts.length ? pts.reduce((s, p) => s + p.eff, 0) / pts.length : null;

    const brakingPts  = fastPoints.filter(p => p.lon < -0.1);
    const tractionPts = fastPoints.filter(p => p.lon >  0.1);
    const leftPts     = fastPoints.filter(p => p.lat >  0.1);
    const rightPts    = fastPoints.filter(p => p.lat < -0.1);

    const quadrants = [
      { key: 'braking',  label: 'Braking',      eff: avgE(brakingPts) },
      { key: 'traction', label: 'Traction',      eff: avgE(tractionPts) },
      { key: 'left',     label: 'Turn Left',     eff: avgE(leftPts) },
      { key: 'right',    label: 'Turn Right',    eff: avgE(rightPts) },
    ].filter(q => q.eff !== null);

    const getRec = (key, eff) => REC_MAP[key][eff >= 85 ? 'high' : eff >= 72 ? 'mid' : 'low'];

    // Show recommendations only for quadrants below 85 — sorted worst first
    const recs = [...quadrants]
      .filter(q => q.eff < 85)
      .sort((a, b) => a.eff - b.eff)
      .slice(0, 2)
      .map(q => ({ ...q, rec: getRec(q.key, q.eff) }));

    return {
      fastAvgEff: avgE(fastPoints),
      slowAvgEff: slowPoints.length ? avgE(slowPoints) : null,
      fastPeakG: Math.max(...fastPoints.map(p => Math.sqrt(p.lat ** 2 + p.lon ** 2))),
      quadrants,
      recs,
    };
  }, [fastPoints, slowPoints]);

  if (!fastPoints.length && !slowPoints.length && !gLimit) return null;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> {t.ggTitle}</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.72rem', color: '#00D4FF' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#00D4FF', display: 'inline-block' }} />
            {t.ggFast}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.72rem', color: '#FF6B6B' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#FF6B6B', display: 'inline-block' }} />
            {t.ggSlow}
          </span>
          <span className="chart-zoom-badge">{t.ggLimit(limit)}</span>
        </div>
      </div>

      <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
        <canvas
          ref={canvasRef}
          style={{ display: 'block', cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
        />
        {tooltip && (
          <div style={{
            position: 'absolute',
            left: tooltip.screenX + 14,
            top: tooltip.screenY - 8,
            pointerEvents: 'none',
            background: 'rgba(10,15,30,0.97)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: '0.75rem',
            fontFamily: "'JetBrains Mono', monospace",
            color: '#8899BB',
            zIndex: 10,
          }}>
            <div style={{ color: '#fff', marginBottom: 4 }}>
              {tooltip._lap === 'fast' ? `🔵 ${t.ggFast}` : `🔴 ${t.ggSlow}`}
            </div>
            <div>Lat: <span style={{ color: '#fff' }}>{tooltip.lat.toFixed(3)} G</span></div>
            <div>Lon: <span style={{ color: '#fff' }}>{tooltip.lon.toFixed(3)} G</span></div>
            <div>Eff: <span style={{
              color: tooltip.eff >= 90 ? '#00E676' : tooltip.eff >= 72 ? '#FFB300' : '#FF3D3D',
              fontWeight: 700,
            }}>{tooltip.eff.toFixed(1)}%</span></div>
          </div>
        )}
      </div>

      {stats && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '12px 16px 16px' }}>

          {/* Summary stats + legend */}
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
            <GGStat label="Fast avg eff" value={`${stats.fastAvgEff.toFixed(1)}%`}
              color={effColor(stats.fastAvgEff)} />
            {stats.slowAvgEff !== null && (
              <GGStat label="Slow avg eff" value={`${stats.slowAvgEff.toFixed(1)}%`}
                color={effColor(stats.slowAvgEff)} />
            )}
            <GGStat label="Peak G (fast)" value={`${stats.fastPeakG.toFixed(2)} G`} color="#8899BB" />
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
              {[['≥ 90%', '#00E676'], ['72–90%', '#FFB300'], ['< 72%', '#FF3D3D']].map(([label, color]) => (
                <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.68rem', color: 'var(--text-3)' }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
                  {label}
                </span>
              ))}
            </div>
          </div>

          {/* Per-quadrant efficiency chips */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
            {stats.quadrants.map(({ key, label, eff }) => (
              <div key={key} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'rgba(255,255,255,0.04)',
                border: `1px solid ${effColor(eff, 0.35)}`,
                borderRadius: 6,
                padding: '5px 10px',
              }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: effColor(eff),
                  flexShrink: 0,
                }} />
                <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>{label}</span>
                <span style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: effColor(eff),
                  fontFamily: "'JetBrains Mono', monospace",
                }}>{eff.toFixed(1)}%</span>
              </div>
            ))}
          </div>

          {/* Targeted recommendations */}
          {stats.recs.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {stats.recs.map(({ key, label, eff, rec }) => (
                <div key={key} style={{
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start',
                  borderLeft: `2px solid ${effColor(eff, 0.6)}`,
                  paddingLeft: 10,
                }}>
                  <span style={{
                    fontSize: '0.63rem',
                    fontWeight: 700,
                    color: effColor(eff),
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    whiteSpace: 'nowrap',
                    paddingTop: 2,
                    minWidth: 70,
                  }}>{label}</span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', lineHeight: 1.5 }}>{rec}</span>
                </div>
              ))}
            </div>
          )}

          {stats.recs.length === 0 && (
            <p style={{
              margin: 0,
              fontSize: '0.73rem',
              color: 'var(--text-2)',
              lineHeight: 1.5,
              borderLeft: '2px solid rgba(0,230,118,0.4)',
              paddingLeft: 10,
            }}>
              All quadrants above 85% — driver is consistently near the friction limit.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default GGDiagramChart;
