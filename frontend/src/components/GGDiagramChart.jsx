import { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import { useLanguage } from '../context/LanguageContext';
import useThemeColors, { parseRgb } from '../hooks/useThemeColors';
import { Panel, Badge, Stat } from './ui';
import styles from './GGDiagramChart.module.css';

const PAD = { top: 24, right: 24, bottom: 40, left: 44 };
const CSS_H = 340;
const MONO = 'JetBrains Mono, monospace';

// Equal scale on both axes (a friction circle must look like a circle); the square plot is centred.
function makeCoordFns(cssW, limit) {
  const range = limit * 1.15 * 2;
  const availW = cssW - PAD.left - PAD.right;
  const availH = CSS_H - PAD.top - PAD.bottom;
  const side = Math.min(availW, availH);
  const left = PAD.left + (availW - side) / 2;
  const toX = (v) => left + (v + limit * 1.15) / range * side;
  const toY = (v) => PAD.top + (limit * 1.15 - v) / range * side;
  return { toX, toY, plotW: side, plotH: side, range, left };
}

// Canvas needs literal colours: resolve theme tokens (computed values) and apply alpha.
const withAlpha = (color, alpha) => {
  const rgb = parseRgb(color);
  return rgb ? `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})` : color;
};
const effColor = (colors, eff, alpha = 1) => withAlpha(eff >= 90 ? colors.ok : eff >= 72 ? colors.warn : colors.bad, alpha);
const effTone = (eff) => (eff >= 90 ? 'ok' : eff >= 72 ? 'warn' : 'bad');

const GGDiagramChart = ({ ggData, gLimit }) => {
  const { t } = useLanguage();
  const colors = useThemeColors();
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
    if (cssW < 120) return; // container not laid out yet (avoids negative arc radius)
    canvas.width = cssW * dpr;
    canvas.height = CSS_H * dpr;
    canvas.style.width = cssW + 'px';
    canvas.style.height = CSS_H + 'px';

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const { toX, toY, plotW, plotH, range, left } = makeCoordFns(cssW, limit);
    const ticks = [-limit, -limit * 0.5, 0, limit * 0.5, limit];

    // Grid lines
    ctx.strokeStyle = withAlpha(colors.ink2, 0.16);
    ctx.lineWidth = 1;
    ticks.forEach(v => {
      ctx.beginPath(); ctx.moveTo(toX(v), PAD.top); ctx.lineTo(toX(v), PAD.top + plotH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left, toY(v)); ctx.lineTo(left + plotW, toY(v)); ctx.stroke();
    });

    // Friction circle
    const cx = toX(0);
    const cy = toY(0);
    const r = Math.max(0, limit / range * plotW);
    ctx.strokeStyle = withAlpha(colors.ink2, 0.7);
    ctx.lineWidth = 1.25;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Centre axes
    ctx.strokeStyle = withAlpha(colors.ink2, 0.4);
    ctx.beginPath(); ctx.moveTo(cx, PAD.top); ctx.lineTo(cx, PAD.top + plotH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(left, cy); ctx.lineTo(left + plotW, cy); ctx.stroke();

    // Points: slow = hollow rings, fast = filled dots (efficiency colour)
    ctx.lineWidth = 1;
    slowPoints.forEach(({ lat, lon, eff }) => {
      ctx.beginPath();
      ctx.arc(toX(lon), toY(lat), 2.4, 0, Math.PI * 2);
      ctx.strokeStyle = effColor(colors, eff, 0.7);
      ctx.stroke();
    });
    fastPoints.forEach(({ lat, lon, eff }) => {
      ctx.beginPath();
      ctx.arc(toX(lon), toY(lat), 2, 0, Math.PI * 2);
      ctx.fillStyle = effColor(colors, eff, 0.85);
      ctx.fill();
    });

    // Quadrant labels
    ctx.font = `600 10px ${MONO}`;
    ctx.lineJoin = 'round';
    ctx.lineWidth = 4;
    ctx.strokeStyle = withAlpha(colors.surface0, 0.9);
    ctx.fillStyle = colors.ink1;
    // Braking / traction sit at the far ends of the horizontal axis so they never collide at the centre.
    ctx.textAlign = 'left';
    ctx.strokeText(t.ggQuadBraking, left + 6, cy - 5);
    ctx.fillText(t.ggQuadBraking, left + 6, cy - 5);
    ctx.textAlign = 'right';
    ctx.strokeText(t.ggQuadTraction, left + plotW - 6, cy - 5);
    ctx.fillText(t.ggQuadTraction, left + plotW - 6, cy - 5);
    ctx.textAlign = 'center';
    ctx.strokeText(t.ggQuadLeft, cx, PAD.top + 12);
    ctx.fillText(t.ggQuadLeft, cx, PAD.top + 12);
    ctx.strokeText(t.ggQuadRight, cx, PAD.top + plotH - 5);
    ctx.fillText(t.ggQuadRight, cx, PAD.top + plotH - 5);

    // Axis tick values + titles
    ctx.fillStyle = colors.ink3;
    ctx.font = `10px ${MONO}`;
    ticks.forEach(v => {
      ctx.textAlign = 'center';
      ctx.fillText(v.toFixed(1), toX(v), PAD.top + plotH + 16);
      ctx.textAlign = 'right';
      ctx.fillText(v.toFixed(1), left - 6, toY(v) + 3);
    });
    ctx.textAlign = 'right';
    ctx.fillText(t.ggLonG, left + plotW, PAD.top + plotH + 32);
    ctx.textAlign = 'left';
    ctx.fillText(t.ggLatG, left - 40, PAD.top - 10);
  }, [fastPoints, slowPoints, limit, t, colors]);

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
      { key: 'braking',  label: t.ggBraking,      eff: avgE(brakingPts) },
      { key: 'traction', label: t.ggTraction,      eff: avgE(tractionPts) },
      { key: 'left',     label: t.ggTurnLeft,     eff: avgE(leftPts) },
      { key: 'right',    label: t.ggTurnRight,    eff: avgE(rightPts) },
    ].filter(q => q.eff !== null);

    const getRec = (key, eff) => t[`ggRec_${key}_${eff >= 85 ? 'high' : eff >= 72 ? 'mid' : 'low'}`];

    // Show recommendations only for quadrants below 85, sorted worst first
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
  }, [fastPoints, slowPoints, t]);

  if (!fastPoints.length && !slowPoints.length && !gLimit) return null;

  return (
    <Panel
      icon="target"
      title={t.ggTitle}
      actions={<Badge>{t.ggLimit(limit)}</Badge>}
    >
      <div className={styles.legend}>
        <span className={styles.legendItem}><span className={styles.dotFilled} />{t.ggFast}</span>
        <span className={styles.legendItem}><span className={styles.dotHollow} />{t.ggSlow}</span>
        <span className={styles.spacer} />
        {[['ok', '≥ 90 %'], ['warn', '72–90 %'], ['bad', '< 72 %']].map(([tone, label]) => (
          <span key={tone} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: `var(--${tone})` }} />
            {label}
          </span>
        ))}
      </div>

      <div ref={containerRef} className={styles.canvasWrap}>
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={t.ggTitle}
          style={{ display: 'block', cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
        />
        {tooltip && (
          <div className={styles.tip} style={{ left: tooltip.screenX + 14, top: tooltip.screenY - 8 }}>
            <div className={styles.tipHead}>{tooltip._lap === 'fast' ? t.ggFast : t.ggSlow}</div>
            <div className={styles.tipRow}><span>{t.ggTipLat}</span><b>{tooltip.lat.toFixed(3)} G</b></div>
            <div className={styles.tipRow}><span>{t.ggTipLon}</span><b>{tooltip.lon.toFixed(3)} G</b></div>
            <div className={styles.tipRow}>
              <span>{t.ggTipEff}</span>
              <b style={{ color: `var(--${effTone(tooltip.eff)})` }}>{tooltip.eff.toFixed(1)} %</b>
            </div>
          </div>
        )}
      </div>

      {stats && (
        <div className={styles.stats}>
          <div className="ui-grid ui-grid--3">
            <Stat label={t.ggFastAvgEff} value={`${stats.fastAvgEff.toFixed(1)} %`} tone={effTone(stats.fastAvgEff)} />
            {stats.slowAvgEff !== null && (
              <Stat label={t.ggSlowAvgEff} value={`${stats.slowAvgEff.toFixed(1)} %`} tone={effTone(stats.slowAvgEff)} />
            )}
            <Stat label={t.ggPeakG} value={`${stats.fastPeakG.toFixed(2)} G`} />
          </div>

          <div className={styles.quads}>
            {stats.quadrants.map(({ key, label, eff }) => (
              <Badge key={key} tone={effTone(eff)}>{label} {eff.toFixed(1)} %</Badge>
            ))}
          </div>

          {stats.recs.length > 0 ? (
            <ul className={styles.recs}>
              {stats.recs.map(({ key, label, eff, rec }) => (
                <li key={key} className={styles.rec} style={{ borderLeftColor: `var(--${effTone(eff)})` }}>
                  <span className={styles.recLabel}>{label}</span>
                  <span className={styles.recText}>{rec}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={`${styles.rec} ${styles.recOk}`}>
              {t.ggAllGood}
            </p>
          )}
        </div>
      )}
    </Panel>
  );
};

export default GGDiagramChart;
