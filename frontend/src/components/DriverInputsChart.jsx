import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';

const LABEL_MAP = {
  'Muy suave': { color: '#00E676', bg: 'rgba(0,230,118,0.12)' },
  'Suave':     { color: '#69F0AE', bg: 'rgba(105,240,174,0.10)' },
  'Normal':    { color: '#00D4FF', bg: 'rgba(0,212,255,0.10)' },
  'Activo':    { color: '#FFB300', bg: 'rgba(255,179,0,0.12)' },
  'Nervioso':  { color: '#FF3D3D', bg: 'rgba(255,61,61,0.15)' },
};

const renderTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.72rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-3)', marginBottom: 4 }}>{Number(label).toFixed(0)}m</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {(p.value * 100).toFixed(1)}%
        </div>
      ))}
    </div>
  );
};

const BandBar = ({ label: lbl, value, title, lapLabel, color }) => {
  if (value == null) return null;
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.67rem', color: 'var(--text-3)', marginBottom: 2 }}>
        <span>{lbl}</span>
        <span style={{ color }}>{(value * 100).toFixed(1)}%</span>
      </div>
      <div style={{ height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
    </div>
  );
};

const PilotCard = ({ scoreKey, labelKey, bandsKey, overlapKey, data, lapLabel, colorPrimary }) => {
  const score  = data[scoreKey];
  const lbl    = data[labelKey];
  const bands  = data[bandsKey];
  const overlap = data[overlapKey];
  if (score == null) return null;

  const style = LABEL_MAP[lbl] || { color: 'var(--text-2)', bg: 'rgba(255,255,255,0.06)' };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '12px 14px', flex: '1 1 180px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: '0.78rem', color: colorPrimary, fontWeight: 600 }}>{lapLabel}</span>
        <span style={{
          fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.06em',
          color: style.color, background: style.bg, borderRadius: 4, padding: '2px 8px',
        }}>
          {lbl || '—'}
        </span>
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: style.color, marginBottom: 8 }}>
        {(score * 100).toFixed(1)}%
        <span style={{ fontSize: '0.65rem', opacity: 0.6, marginLeft: 4 }}>nerviosismo</span>
      </div>
      {bands && (
        <div style={{ marginBottom: 8 }}>
          <BandBar lbl="Baja freq. (<0.5 Hz)" value={bands.low} color="#00E676" />
          <BandBar lbl="Media freq. (0.5–2 Hz)" value={bands.mid} color="#FFB300" />
          <BandBar lbl="Alta freq. (>2 Hz)"  value={bands.high} color="#FF3D3D" />
        </div>
      )}
      {overlap != null && (
        <div style={{ fontSize: '0.67rem', color: overlap > 5 ? '#FFB300' : 'var(--text-3)' }}>
          Solapamiento freno-gas: {overlap.toFixed(1)}%
        </div>
      )}
    </div>
  );
};

const DriverInputsChart = ({ driver_inputs, metadata }) => {
  const data = driver_inputs;
  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  const chartData = useMemo(() => {
    const pd = data.per_distance;
    if (!pd?.distance) return [];
    return pd.distance.map((d, i) => ({
      distance: d,
      nerv_a: pd.nervousness_a?.[i] ?? null,
      nerv_b: pd.nervousness_b?.[i] ?? null,
    }));
  }, [data]);

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> Análisis de Inputs del Piloto</div>
        <span className="chart-zoom-badge">FFT · Nerviosismo</span>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        Las micro-correcciones de alta frecuencia en el volante indican falta de confianza
        en el agarre o fatiga del piloto. El índice se normaliza por vuelta (0=suavísimo,
        100%=máxima actividad registrada).
      </p>

      {/* Pilot cards */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <PilotCard
          scoreKey="nervousness_score_a" labelKey="nervousness_label_a"
          bandsKey="fft_bands_a" overlapKey="overlap_pct_a"
          data={data} lapLabel={labelA} colorPrimary="#00D4FF"
        />
        <PilotCard
          scoreKey="nervousness_score_b" labelKey="nervousness_label_b"
          bandsKey="fft_bands_b" overlapKey="overlap_pct_b"
          data={data} lapLabel={labelB} colorPrimary="#FF6B6B"
        />
      </div>

      {/* Nervousness over distance */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="nervGradA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#00D4FF" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="nervGradB" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#FF6B6B" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#FF6B6B" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
            <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={36} />
            <Tooltip content={renderTooltip} />
            {data.available_a && (
              <Area
                type="monotone" dataKey="nerv_a" name={labelA}
                stroke="#00D4FF" strokeWidth={1.5} fill="url(#nervGradA)"
                isAnimationActive={false} dot={false} connectNulls
              />
            )}
            {data.available_b && (
              <Area
                type="monotone" dataKey="nerv_b" name={labelB}
                stroke="#FF6B6B" strokeWidth={1.5} fill="url(#nervGradB)"
                isAnimationActive={false} dot={false} connectNulls
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default DriverInputsChart;
