import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';

const SEV_COLOR  = { critico: '#FF3D3D', media: '#FFB300', leve: '#00E676' };
const SEV_BG     = { critico: 'rgba(255,61,61,0.07)',  media: 'rgba(255,179,0,0.06)',  leve: 'rgba(0,230,118,0.05)' };
const SEV_BORDER = { critico: 'rgba(255,61,61,0.5)',   media: 'rgba(255,179,0,0.45)',  leve: 'rgba(0,230,118,0.4)' };

// score is 0–1 where 0.6 = threshold. Normalise to 0–100 within 0.6–1.0 range.
const scoreToPercent = (s) => Math.round(Math.min(100, Math.max(0, (s - 0.6) / 0.4 * 100)));

const renderTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.72rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-3)', marginBottom: 2 }}>{d?.distance?.toFixed(0)}m</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {(p.value * 100).toFixed(1)}%
        </div>
      ))}
    </div>
  );
};

const ScoreBar = ({ avg, peak, sevKey }) => {
  const color = SEV_COLOR[sevKey] ?? '#8899BB';
  const pct = scoreToPercent(avg);
  const peakPct = scoreToPercent(peak);
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: '0.65rem', color: 'var(--text-3)' }}>
        <span>Deviation from reference</span>
        <span style={{ color, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
          avg {(avg * 100).toFixed(0)}% · peak {(peak * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'visible' }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%',
          width: `${pct}%`, background: color, borderRadius: 3, opacity: 0.7,
        }} />
        {/* peak marker */}
        <div style={{
          position: 'absolute', top: -2, width: 2, height: 10,
          left: `${peakPct}%`, background: color, borderRadius: 1,
        }} />
      </div>
    </div>
  );
};

const AnomalyReport = ({ anomaly }) => {
  const { t } = useLanguage();
  const { scores_fast = [], scores_slow = [], zones = [] } = anomaly || {};

  const chartData = useMemo(() => {
    if (!scores_slow.length) return [];
    const fastMap = new Map(scores_fast.map((p) => [p.distance, p.score]));
    return scores_slow.map((p) => ({
      distance: p.distance,
      slow: p.score,
      fast: fastMap.get(p.distance) ?? 0,
    }));
  }, [scores_fast, scores_slow]);

  if (!chartData.length && !zones.length) return null;

  const criticalZones = zones.filter((z) => (z.severity_key ?? z.severity) === 'critico').length;

  const SEV_LABEL = {
    critico: t.severityCritico,
    media:   t.severityMedia,
    leve:    t.severityLeve,
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◈</span> {t.anomalyTitle}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {criticalZones > 0 && (
            <span className="chart-zoom-badge" style={{ color: 'var(--red)', borderColor: 'var(--red-border)', background: 'var(--red-dim)' }}>
              {t.anomalyCritical(criticalZones)}
            </span>
          )}
          <span className="chart-zoom-badge">{zones.length === 1 ? t.anomalyZone(1) : t.anomalyZones(zones.length)}</span>
        </div>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        {t.anomalyDescription}
      </p>

      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="anomGradFast" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#00D4FF" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="anomGradSlow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#FF3D3D" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#FF3D3D" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
            <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(0)}m`} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={36} />
            <Tooltip content={renderTooltip} />
            {/* anomaly threshold reference line */}
            <ReferenceLine y={0.6} stroke="rgba(255,179,0,0.4)" strokeDasharray="4 3"
              label={{ value: 'threshold', position: 'insideTopRight', fill: 'rgba(255,179,0,0.5)', fontSize: 9 }} />
            {zones.map((z, i) => (
              <ReferenceLine
                key={i}
                x={z.start_m}
                stroke={SEV_COLOR[z.severity_key ?? 'leve']}
                strokeWidth={1.5}
                strokeOpacity={0.6}
              />
            ))}
            <Area
              type="monotone" dataKey="fast" name={t.anomalyReference}
              stroke="#00D4FF" strokeWidth={1} fill="url(#anomGradFast)"
              isAnimationActive={false} dot={false}
            />
            <Area
              type="monotone" dataKey="slow" name={t.anomalySlowLap}
              stroke="#FF3D3D" strokeWidth={1.5} fill="url(#anomGradSlow)"
              isAnimationActive={false} dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      {zones.length > 0 && (
        <div className="anomaly-zones">
          {zones.map((z, i) => {
            const sevKey = z.severity_key ?? 'leve';
            const color  = SEV_COLOR[sevKey];
            return (
              <div key={i} style={{
                borderRadius: 8,
                padding: '12px 14px',
                borderLeft: `3px solid ${SEV_BORDER[sevKey]}`,
                background: SEV_BG[sevKey],
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}>
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase',
                    letterSpacing: '0.1em', padding: '2px 8px', borderRadius: 4,
                    color, background: `${color}18`, border: `1px solid ${color}40`,
                  }}>
                    {SEV_LABEL[sevKey] ?? z.severity}
                  </span>
                  <span style={{ fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-2)' }}>
                    {z.start_m.toFixed(0)}m – {z.end_m.toFixed(0)}m
                  </span>
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>
                    {z.length_m.toFixed(0)}m zone
                  </span>
                </div>

                {/* Deviation bar */}
                <ScoreBar avg={z.avg_score} peak={z.peak_score} sevKey={sevKey} />

                {/* Description */}
                <p style={{ margin: 0, fontSize: '0.73rem', color: 'var(--text-2)', lineHeight: 1.55 }}>
                  {z.descripcion}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AnomalyReport;
