import { useMemo } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
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
          {p.name}: {p.value.toFixed(3)} g/%
        </div>
      ))}
    </div>
  );
};

const FadeZoneList = ({ zones, color, label }) => {
  if (!zones?.length) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: '0.68rem', color, marginBottom: 4, fontWeight: 600 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {zones.map((z, i) => (
          <div key={i} style={{
            fontSize: '0.67rem', background: `${color}15`, border: `1px solid ${color}44`,
            borderRadius: 6, padding: '3px 8px', color,
          }}>
            {z.start.toFixed(0)}–{z.end.toFixed(0)}m
            <span style={{ opacity: 0.7, marginLeft: 4 }}>({(z.severity * 100).toFixed(0)}% caída)</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const ScoreBadge = ({ score, baseline, label, color }) => {
  if (score == null) return null;
  const ratio = baseline > 0 ? score / baseline : 1;
  const pct = (ratio * 100).toFixed(0);
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '10px 14px', textAlign: 'center', flex: '1 1 100px',
    }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 700, color }}>
        {score.toFixed(3)}
        <span style={{ fontSize: '0.65rem', opacity: 0.6, marginLeft: 4 }}>g/%</span>
      </div>
      {baseline > 0 && (
        <div style={{ fontSize: '0.65rem', color: ratio < 0.85 ? '#FF3D3D' : '#00E676', marginTop: 2 }}>
          {pct}% del baseline
        </div>
      )}
    </div>
  );
};

const BrakeFadeChart = ({ brake_analysis, metadata }) => {
  const data = brake_analysis;
  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  const chartData = useMemo(() => {
    const pd = data.per_distance;
    if (!pd?.distance) return [];
    return pd.distance.map((d, i) => ({
      distance: d,
      eff_a: pd.efficiency_a?.[i] ?? null,
      eff_b: pd.efficiency_b?.[i] ?? null,
    }));
  }, [data]);

  const hasA = data.available_a;
  const hasB = data.available_b;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> Eficiencia de Frenado — Brake Fade</div>
        <span className="chart-zoom-badge">|LonG| / (presión / 100)</span>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        Ratio entre la desaceleración generada y la presión aplicada en el pedal.
        Una caída progresiva indica fade térmico. Las zonas sombreadas muestran
        dónde la eficiencia cae más del 15% respecto al baseline inicial.
      </p>

      {/* Score badges */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        {hasA && (
          <ScoreBadge
            score={data.score_a} baseline={data.baseline_a}
            label={labelA} color="#00D4FF"
          />
        )}
        {hasB && (
          <ScoreBadge
            score={data.score_b} baseline={data.baseline_b}
            label={labelB} color="#FF6B6B"
          />
        )}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="fadeGradA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#00D4FF" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="fadeGradB" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#FF6B6B" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#FF6B6B" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
            <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 'auto']} width={40} />
            <Tooltip content={renderTooltip} />
            {/* Baseline reference lines */}
            {hasA && data.baseline_a > 0 && (
              <ReferenceLine y={data.baseline_a} stroke="#00D4FF" strokeDasharray="4 3" strokeOpacity={0.4} />
            )}
            {hasB && data.baseline_b > 0 && (
              <ReferenceLine y={data.baseline_b} stroke="#FF6B6B" strokeDasharray="4 3" strokeOpacity={0.4} />
            )}
            {/* Fade zones for A */}
            {data.fade_zones_a?.map((z, i) => (
              <Area
                key={`fade_a_${i}`}
                data={chartData.filter(d => d.distance >= z.start && d.distance <= z.end)}
                type="monotone" dataKey="eff_a"
                stroke="none" fill="rgba(255,61,61,0.15)" isAnimationActive={false}
              />
            ))}
            {hasA && (
              <Line
                type="monotone" dataKey="eff_a" name={labelA}
                stroke="#00D4FF" strokeWidth={1.5} dot={false}
                isAnimationActive={false} connectNulls={false}
              />
            )}
            {hasB && (
              <Line
                type="monotone" dataKey="eff_b" name={labelB}
                stroke="#FF6B6B" strokeWidth={1.5} dot={false}
                isAnimationActive={false} connectNulls={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Fade zone lists */}
      <FadeZoneList zones={data.fade_zones_a} color="#00D4FF" label={`Zonas de fade — ${labelA}`} />
      <FadeZoneList zones={data.fade_zones_b} color="#FF6B6B" label={`Zonas de fade — ${labelB}`} />
    </div>
  );
};

export default BrakeFadeChart;
