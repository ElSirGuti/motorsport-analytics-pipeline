import { useMemo } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';

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
  const { t } = useLanguage();
  if (us == null) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
        <div style={{ width: `${us}%`, background: '#4FC3F7' }} title={`${t.slipAngleSub} ${us}%`} />
        <div style={{ width: `${neutral}%`, background: 'rgba(255,255,255,0.15)' }} title={`${t.slipAngleNeutral} ${neutral}%`} />
        <div style={{ width: `${os}%`, background: '#FF3D3D' }} title={`${t.slipAngleOver} ${os}%`} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: 'var(--text-3)', marginTop: 3 }}>
        <span style={{ color: '#4FC3F7' }}>{t.slipAngleSub} {us?.toFixed(0)}%</span>
        <span>{t.slipAngleNeutral} {neutral?.toFixed(0)}%</span>
        <span style={{ color: '#FF3D3D' }}>{t.slipAngleOver} {os?.toFixed(0)}%</span>
      </div>
    </div>
  );
};

const LapSummaryCard = ({ summary, label, color }) => {
  const { t } = useLanguage();
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
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>{t.slipAngleMax}</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color }}>
            {beta_max != null ? `${beta_max.toFixed(1)}°` : '—'}
          </div>
        </div>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>{t.slipAngleP95}</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-2)' }}>
            {beta_p95 != null ? `${beta_p95.toFixed(1)}°` : '—'}
          </div>
        </div>
        {balance_mean != null && (
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-3)' }}>{t.slipAngleBalanceLabel}</div>
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
  const { t } = useLanguage();
  const data = slip_angle;
  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  const hasA = data.available_a;
  const hasB = data.available_b;
  const pdA  = hasA ? data.per_distance_a : null;
  const pdB  = hasB ? data.per_distance_b : null;

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
        <div className="chart-title"><span>◈</span> {t.slipAngleTitle}</div>
        <span className="chart-zoom-badge">{t.slipAngleModel}</span>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        {t.slipAngleDescription}
          <span style={{ opacity: 0.6 }}> {t.slipAngleGeometry.replace('{wheelbase}', data.wheelbase_m?.toFixed(2)).replace('{ratio}', data.steer_ratio)}</span>
      </p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        {hasA && <LapSummaryCard summary={data.summary_a} label={labelA} color="#00D4FF" />}
        {hasB && <LapSummaryCard summary={data.summary_b} label={labelB} color="#FF6B6B" />}
      </div>

      {betaData.length > 0 && (
        <>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 6 }}>
            {t.slipAngleChassis}
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

      {hasBalance && balanceData.length > 0 && (
        <>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: 12, marginBottom: 6 }}>
            {t.slipAngleBalance}
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
