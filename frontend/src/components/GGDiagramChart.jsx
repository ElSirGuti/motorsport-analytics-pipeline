import { useMemo } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';

const renderTooltip = ({ active, payload, t }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem',
      fontFamily: "'JetBrains Mono', monospace", color: '#8899BB',
    }}>
      <div style={{ color: '#fff', marginBottom: 4 }}>
        {d._lap === 'fast' ? `🔵 ${t.ggFast}` : `🔴 ${t.ggSlow}`}
      </div>
      <div>Lat: <span style={{ color: '#fff' }}>{d.lat.toFixed(3)} G</span></div>
      <div>Lon: <span style={{ color: '#fff' }}>{d.lon.toFixed(3)} G</span></div>
      <div>Eff: <span style={{
        color: d.eff >= 90 ? '#00E676' : d.eff >= 70 ? '#FFB300' : '#FF3D3D',
        fontWeight: 700,
      }}>{d.eff.toFixed(1)}%</span></div>
    </div>
  );
};

const GGDiagramChart = ({ ggData, gLimit }) => {
  const { t } = useLanguage();

  const fastPoints = useMemo(() => {
    if (!ggData?.length) return [];
    return ggData
      .filter((d) => d._lap === 'fast')
      .map((d) => ({ lat: d.lat, lon: d.lon, eff: d.eff, _lap: d._lap }));
  }, [ggData]);

  const slowPoints = useMemo(() => {
    if (!ggData?.length) return [];
    return ggData
      .filter((d) => d._lap === 'slow')
      .map((d) => ({ lat: d.lat, lon: d.lon, eff: d.eff, _lap: d._lap }));
  }, [ggData]);

  if (!ggData?.length && !gLimit) return null;

  const limit = gLimit || 1.3;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> {t.ggTitle}</div>
        <span className="chart-zoom-badge">{t.ggLimit(limit)}</span>
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
          <XAxis
            dataKey="lon"
            type="number"
            domain={[-limit * 1.15, limit * 1.15]}
            tick={{ fontSize: 10 }}
            label={{ value: t.ggAxisLabel, position: 'insideBottom', offset: -4, style: { fill: 'var(--text-3)', fontSize: 10 } }}
          />
          <YAxis
            dataKey="lat"
            type="number"
            domain={[-limit * 1.15, limit * 1.15]}
            tick={{ fontSize: 10 }}
            width={36}
          />
          <Tooltip content={<renderTooltip t={t} />} />
          <Legend
            formatter={(value) => <span style={{ color: '#fff', fontSize: '0.75rem' }}>{value}</span>}
          />

          <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
          <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />

          {fastPoints.length > 0 && (
            <Scatter
              name={t.ggFast}
              data={fastPoints}
              fill="#00D4FF"
              fillOpacity={0.25}
              stroke="#00D4FF"
              strokeWidth={0.5}
              isAnimationActive={false}
            />
          )}

          {slowPoints.length > 0 && (
            <Scatter
              name={t.ggSlow}
              data={slowPoints}
              fill="#FF6B6B"
              fillOpacity={0.25}
              stroke="#FF6B6B"
              strokeWidth={0.5}
              isAnimationActive={false}
            />
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};

export default GGDiagramChart;
