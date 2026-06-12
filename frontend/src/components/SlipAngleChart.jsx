import { useMemo } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
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
          {p.name}: {p.value > 0 ? '+' : ''}{p.value.toFixed(2)}°
        </div>
      ))}
    </div>
  );
};

const BalanceBar = ({ us, os, neutral }) => {
  if (us == null) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
        <div style={{ width: `${us}%`, background: '#4FC3F7' }} title={`Subviraje ${us}%`} />
        <div style={{ width: `${neutral}%`, background: 'rgba(255,255,255,0.15)' }} title={`Neutral ${neutral}%`} />
        <div style={{ width: `${os}%`, background: '#FF3D3D' }} title={`Sobreviraje ${os}%`} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: 'var(--text-3)', marginTop: 3 }}>
        <span style={{ color: '#4FC3F7' }}>SUB {us?.toFixed(0)}%</span>
        <span>NEUTRAL {neutral?.toFixed(0)}%</span>
        <span style={{ color: '#FF3D3D' }}>SOBRE {os?.toFixed(0)}%</span>
      </div>
    </div>
  );
};

const LapSummaryCard = ({ summary, label, color }) => {
  if (!summary) return null;
  const { beta_max, beta_p95, understeer_pct, oversteer_pct, neutral_pct, balance_mean } = summary;
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '12px 14px', flex: '1 1 180px',
    }}>
      <div style={{ fontSize: '0.78rem', color, fontWeight: 600, marginBottom: 8 }}>{label}</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>β máx.</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color }}>
            {beta_max != null ? `${beta_max.toFixed(1)}°` : '—'}
          </div>
        </div>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>β p95</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-2)' }}>
            {beta_p95 != null ? `${beta_p95.toFixed(1)}°` : '—'}
          </div>
        </div>
        {balance_mean != null && (
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>Balance</div>
            <div style={{
              fontSize: '1.0rem', fontWeight: 700,
              color: balance_mean > 1 ? '#4FC3F7' : balance_mean < -1 ? '#FF3D3D' : '#00E676',
            }}>
              {balance_mean > 0 ? '+' : ''}{balance_mean.toFixed(1)}°
            </div>
          </div>
        )}
      </div>
      <BalanceBar us={understeer_pct} os={oversteer_pct} neutral={neutral_pct} />
    </div>
  );
};

const SlipAngleChart = ({ slip_angle, metadata }) => {
  const data = slip_angle;
  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  const hasA = data.available_a;
  const hasB = data.available_b;
  const pdA  = hasA ? data.per_distance_a : null;
  const pdB  = hasB ? data.per_distance_b : null;

  // β chart data (body slip)
  const betaData = useMemo(() => {
    const src = pdA || pdB;
    if (!src?.distance) return [];
    const mapB = pdB ? new Map(pdB.distance.map((d, i) => [d, pdB.beta[i]])) : null;
    return src.distance.map((d, i) => ({
      distance: d,
      beta_a: pdA?.beta[i] ?? null,
      beta_b: mapB?.get(d) ?? null,
    }));
  }, [pdA, pdB]);

  // Balance chart (αF − αR) — shows US/OS character over the lap
  const balanceData = useMemo(() => {
    if (!pdA?.balance) return [];
    return pdA.distance.map((d, i) => ({
      distance: d,
      balance_a: pdA.balance[i],
      balance_b: pdB?.balance?.[i] ?? null,
    }));
  }, [pdA, pdB]);

  const hasBalance = !!pdA?.balance;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> Ángulo de Deslizamiento (Sideslip β)</div>
        <span className="chart-zoom-badge">modelo bicicleta cinemático</span>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        β es el ángulo entre la dirección de movimiento del vehículo y su eje longitudinal.
        Valores altos indican que el chasis se mueve "de costado". El balance αF−αR muestra
        si el coche trabaja más en el eje delantero (subviraje, azul) o trasero (sobreviraje, rojo).
        <span style={{ opacity: 0.6 }}> Geometría asumida: L={data.wheelbase_m}m, ratio={data.steer_ratio}:1.</span>
      </p>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        {hasA && <LapSummaryCard summary={data.summary_a} label={labelA} color="#00D4FF" />}
        {hasB && <LapSummaryCard summary={data.summary_b} label={labelB} color="#FF6B6B" />}
      </div>

      {/* β over distance */}
      {betaData.length > 0 && (
        <>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 6 }}>
            Ángulo de deslizamiento del chasis β (°)
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={betaData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="betaGradA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#00D4FF" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
              <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
              <YAxis tick={{ fontSize: 10 }} unit="°" width={36} domain={['auto', 'auto']} />
              <Tooltip content={renderTooltip} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
              {hasA && (
                <Area
                  type="monotone" dataKey="beta_a" name={`β ${labelA}`}
                  stroke="#00D4FF" strokeWidth={1.5} fill="url(#betaGradA)"
                  isAnimationActive={false} dot={false} connectNulls
                />
              )}
              {hasB && (
                <Line
                  type="monotone" dataKey="beta_b" name={`β ${labelB}`}
                  stroke="#FF6B6B" strokeWidth={1.5}
                  isAnimationActive={false} dot={false} connectNulls
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}

      {/* Balance (αF − αR) over distance */}
      {hasBalance && balanceData.length > 0 && (
        <>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 12, marginBottom: 6 }}>
            Balance de pista: αF − αR (+ = subviraje · − = sobreviraje)
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <ComposedChart data={balanceData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
              <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
              <YAxis tick={{ fontSize: 10 }} unit="°" width={36} domain={['auto', 'auto']} />
              <Tooltip content={renderTooltip} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.2)" />
              <ReferenceLine y={2}  stroke="rgba(79,195,247,0.3)"  strokeDasharray="3 3" />
              <ReferenceLine y={-2} stroke="rgba(255,61,61,0.3)"   strokeDasharray="3 3" />
              <Area
                type="monotone" dataKey="balance_a" name={`Balance ${labelA}`}
                stroke="#A78BFA" strokeWidth={1.5}
                fill="transparent"
                isAnimationActive={false} dot={false} connectNulls
              />
              {hasB && (
                <Line
                  type="monotone" dataKey="balance_b" name={`Balance ${labelB}`}
                  stroke="#FFD93D" strokeWidth={1}
                  isAnimationActive={false} dot={false} connectNulls
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
};

export default SlipAngleChart;
