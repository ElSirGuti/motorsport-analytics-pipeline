import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { setCursorDistance } from '../api/cursorStore';

const TimeDeltaChart = ({ data, zoomDomain, onChartClick }) => {
  const chartData = useMemo(() => {
    if (!data?.distance) return [];
    const rows = data.distance.map((dist, i) => ({
      distance: dist,
      delta: data.delta[i],
    }));
    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [data, zoomDomain]);

  if (!chartData.length) {
    return (
      <div className="chart-card">
        <div className="chart-empty">
          <span className="chart-empty__icon">◌</span>
          Sin datos de delta
        </div>
      </div>
    );
  }

  const maxAbs = Math.max(...chartData.map((r) => Math.abs(r.delta)));
  const yPad   = maxAbs * 0.15 || 0.05;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◷</span>
          Delta de Tiempo Acumulado
        </div>
        {zoomDomain && (
          <span className="chart-zoom-badge">
            ZOOM {zoomDomain[0].toFixed(0)}m → {zoomDomain[1].toFixed(0)}m
          </span>
        )}
      </div>

      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 12, left: -12, bottom: 0 }}
            syncId="distanceSync"
            onMouseMove={(state) => { if (state?.activeLabel != null) setCursorDistance(state.activeLabel); }}
            onMouseLeave={() => setCursorDistance(null)}
            onClick={(state) => { if (state?.activeLabel != null) onChartClick?.(state.activeLabel); }}
          >
            <defs>
              <linearGradient id="deltaGradAbove" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#FF3D3D" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#FF3D3D" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="deltaGradBelow" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%"   stopColor="#00E676" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#00E676" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="distance"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v) => `${v.toFixed(0)}m`}
            />
            <YAxis
              domain={[-(maxAbs + yPad), maxAbs + yPad]}
              tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
              width={52}
            />
            <Tooltip
              formatter={(value) => [
                `${value > 0 ? '+' : ''}${Number(value).toFixed(3)}s`,
                'Delta',
              ]}
              labelFormatter={(l) => `${Number(l).toFixed(0)} m`}
              contentStyle={{ color: 'var(--text-1)' }}
              itemStyle={{ color: chartData.find((r) => r.delta > 0) ? 'var(--red)' : 'var(--green)' }}
            />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 3" />
            {/* Positive area (B is slower) */}
            <Area
              type="monotone"
              dataKey={(d) => (d.delta >= 0 ? d.delta : 0)}
              name="Pérdida"
              stroke="var(--red)"
              strokeWidth={0}
              fill="url(#deltaGradAbove)"
              isAnimationActive={false}
            />
            {/* Negative area (B is faster) */}
            <Area
              type="monotone"
              dataKey={(d) => (d.delta <= 0 ? d.delta : 0)}
              name="Ganancia"
              stroke="var(--green)"
              strokeWidth={0}
              fill="url(#deltaGradBelow)"
              isAnimationActive={false}
            />
            {/* Main delta line */}
            <Area
              type="monotone"
              dataKey="delta"
              name="Delta"
              stroke="rgba(255,255,255,0.7)"
              strokeWidth={1.5}
              fill="transparent"
              activeDot={{ r: 3, strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TimeDeltaChart;
