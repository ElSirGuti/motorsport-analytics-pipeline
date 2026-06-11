import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

const SEV_COLOR = { leve: '#00E676', media: '#FFB300', critico: '#FF3D3D' };
const SEV_LABEL = { leve: 'LEVE', media: 'MEDIA', critico: 'CRÍTICO' };

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

const AnomalyReport = ({ anomaly }) => {
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

  const maxDist = chartData.at(-1)?.distance ?? 0;
  const criticalZones = zones.filter((z) => z.severity === 'critico').length;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◈</span> Isolation Forest — Detección de Anomalías
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {criticalZones > 0 && (
            <span className="chart-zoom-badge" style={{ color: 'var(--red)', borderColor: 'var(--red-border)', background: 'var(--red-dim)' }}>
              {criticalZones} crítico{criticalZones > 1 ? 's' : ''}
            </span>
          )}
          <span className="chart-zoom-badge">{zones.length} zona{zones.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: 'var(--s4)', lineHeight: 1.5 }}>
        Entrenado sobre la vuelta rápida (referencia). Las zonas donde el error de reconstrucción
        se dispara indican ejecuciones que divergen del patrón óptimo en múltiples canales simultáneos.
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
            <ReferenceLine y={0.6} stroke="rgba(255,179,0,0.4)" strokeDasharray="4 3" />
            {zones.map((z, i) => (
              <ReferenceLine
                key={i}
                x={z.start_m}
                stroke={SEV_COLOR[z.severity]}
                strokeWidth={1.5}
                strokeOpacity={0.6}
              />
            ))}
            <Area
              type="monotone" dataKey="fast" name="Referencia"
              stroke="#00D4FF" strokeWidth={1} fill="url(#anomGradFast)"
              isAnimationActive={false} dot={false}
            />
            <Area
              type="monotone" dataKey="slow" name="Vuelta lenta"
              stroke="#FF3D3D" strokeWidth={1.5} fill="url(#anomGradSlow)"
              isAnimationActive={false} dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      {zones.length > 0 && (
        <div className="anomaly-zones">
          {zones.map((z, i) => (
            <div key={i} className={`anomaly-zone anomaly-zone--${z.severity}`}>
              <div className="anomaly-zone__header">
                <span className={`dynamic-event__severidad dynamic-event__severidad--${z.severity}`}>
                  {SEV_LABEL[z.severity]}
                </span>
                <span className="anomaly-zone__range">
                  {z.start_m.toFixed(0)}m – {z.end_m.toFixed(0)}m
                </span>
                <span className="anomaly-zone__len">{z.length_m.toFixed(0)}m</span>
                <span className="anomaly-zone__score" style={{ color: SEV_COLOR[z.severity] }}>
                  {(z.avg_score * 100).toFixed(0)}% error
                </span>
              </div>
              <div className="anomaly-zone__desc">{z.descripcion}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AnomalyReport;
