import { useMemo } from 'react';
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

const renderTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.72rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-3)', marginBottom: 4 }}>{Number(label).toFixed(0)}m</div>
      {payload.map((p) => p.value != null && (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value > 0 ? '+' : ''}{p.value.toFixed(1)} mm
        </div>
      ))}
    </div>
  );
};

const StatCell = ({ label, value, unit = 'mm', color = 'var(--text-2)' }) => (
  <div style={{
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 6, padding: '8px 10px', textAlign: 'center', flex: '1 1 80px',
  }}>
    <div style={{ fontSize: '0.62rem', color: 'var(--text-3)', marginBottom: 3 }}>{label}</div>
    <div style={{ fontSize: '0.9rem', fontWeight: 700, color }}>
      {value != null ? `${value.toFixed(1)}` : '—'}
      <span style={{ fontSize: '0.6rem', opacity: 0.6, marginLeft: 2 }}>{unit}</span>
    </div>
  </div>
);

const BottomingBadges = ({ events, color, label }) => {
  if (!events?.length) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: '0.68rem', color, marginBottom: 4, fontWeight: 600 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {events.map((e, i) => (
          <div key={i} style={{
            fontSize: '0.67rem', background: 'rgba(255,61,61,0.10)',
            border: '1px solid rgba(255,61,61,0.3)',
            borderRadius: 6, padding: '3px 8px', color: '#FF3D3D',
          }}>
            {e.corner} · {e.start_m.toFixed(0)}–{e.end_m.toFixed(0)}m
            <span style={{ opacity: 0.7, marginLeft: 4 }}>({(e.severity * 100).toFixed(0)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const SuspensionChart = ({ suspension, metadata }) => {
  const data = suspension;
  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  // Use lap A series primarily; fall back to B
  const seriesA = data.available_a ? data.per_distance_a : null;
  const seriesB = data.available_b ? data.per_distance_b : null;
  const primary = seriesA || seriesB;

  const chartData = useMemo(() => {
    if (!primary?.distance) return [];
    return primary.distance.map((d, i) => ({
      distance: d,
      roll_f_a:  seriesA?.roll_f?.[i]  ?? null,
      roll_r_a:  seriesA?.roll_r?.[i]  ?? null,
      pitch_a:   seriesA?.pitch?.[i]   ?? null,
      roll_f_b:  seriesB?.roll_f?.[i]  ?? null,
      pitch_b:   seriesB?.pitch?.[i]   ?? null,
    }));
  }, [primary, seriesA, seriesB]);

  const summaryA = data.summary_a;
  const summaryB = data.summary_b;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> Análisis de Suspensión — Pitch &amp; Roll</div>
        <span className="chart-zoom-badge">SuspTravel FL/FR/RL/RR</span>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        Roll: diferencia de recorrido izquierda–derecha (+ = más carga a la derecha).
        Pitch: diferencia delantera–trasera (+ = morro bajo, típico de frenada).
        Los eventos de fondo detectan compresión extrema del amortiguador.
      </p>

      {/* Summary stats */}
      {(summaryA || summaryB) && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {summaryA && (
            <>
              <StatCell label={`Roll Ax. Del. [${labelA}]`} value={summaryA.max_roll_f} color="#00D4FF" />
              <StatCell label={`Roll Ax. Tra. [${labelA}]`} value={summaryA.max_roll_r} color="#00D4FF" />
              <StatCell label={`Pitch max. [${labelA}]`}    value={summaryA.max_pitch}  color="#00D4FF" />
            </>
          )}
          {summaryB && (
            <>
              <StatCell label={`Roll Ax. Del. [${labelB}]`} value={summaryB.max_roll_f} color="#FF6B6B" />
              <StatCell label={`Pitch max. [${labelB}]`}    value={summaryB.max_pitch}  color="#FF6B6B" />
            </>
          )}
        </div>
      )}

      {/* Chart: roll_f + pitch over distance */}
      {chartData.length > 0 && (
        <>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 6 }}>
            Roll eje delantero · Pitch (mm)
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
              <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
              <YAxis tick={{ fontSize: 10 }} unit="mm" width={42} domain={['auto', 'auto']} />
              <Tooltip content={renderTooltip} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
              {seriesA && (
                <>
                  <Line
                    type="monotone" dataKey="roll_f_a" name={`Roll Del. ${labelA}`}
                    stroke="#00D4FF" strokeWidth={1.5} dot={false}
                    isAnimationActive={false} connectNulls
                  />
                  <Line
                    type="monotone" dataKey="pitch_a" name={`Pitch ${labelA}`}
                    stroke="#FFD93D" strokeWidth={1} strokeDasharray="4 2" dot={false}
                    isAnimationActive={false} connectNulls
                  />
                </>
              )}
              {seriesB && (
                <Line
                  type="monotone" dataKey="roll_f_b" name={`Roll Del. ${labelB}`}
                  stroke="#FF6B6B" strokeWidth={1.5} dot={false}
                  isAnimationActive={false} connectNulls
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* Bottoming events */}
      <BottomingBadges
        events={data.bottoming_a} color="#00D4FF"
        label={`Eventos de fondo — ${labelA}`}
      />
      <BottomingBadges
        events={data.bottoming_b} color="#FF6B6B"
        label={`Eventos de fondo — ${labelB}`}
      />
    </div>
  );
};

export default SuspensionChart;
