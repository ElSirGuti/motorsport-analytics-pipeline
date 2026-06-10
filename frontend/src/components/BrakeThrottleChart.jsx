import { useMemo } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';

const BRAKE_COLORS    = ['#FF3D3D', '#FF8C42', '#CC2936', '#FF6B6B'];
const THROTTLE_COLORS = ['#00E676', '#FFB300', '#34D399', '#F59E0B'];

const BrakeThrottleChart = ({ brakeData, throttleData, zoomDomain }) => {
  const chartData = useMemo(() => {
    if (!brakeData?.distance || !throttleData) return [];
    const rows = brakeData.distance.map((dist, i) => {
      const point = { distance: dist };
      Object.keys(brakeData).forEach((k)    => { if (k.startsWith('brake_'))    point[k] = brakeData[k][i]; });
      Object.keys(throttleData).forEach((k) => { if (k.startsWith('throttle_')) point[k] = throttleData[k][i]; });
      return point;
    });
    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [brakeData, throttleData, zoomDomain]);

  if (!chartData.length) {
    return (
      <div className="chart-card">
        <div className="chart-empty">
          <span className="chart-empty__icon">◌</span>
          Sin datos de pedales
        </div>
      </div>
    );
  }

  const brakeKeys    = Object.keys(brakeData).filter((k) => k.startsWith('brake_'));
  const throttleKeys = Object.keys(throttleData).filter((k) => k.startsWith('throttle_'));
  const lapLabels    = brakeData?.lap_labels || {};

  const commonXAxis = (
    <XAxis
      dataKey="distance"
      type="number"
      domain={['dataMin', 'dataMax']}
      tickFormatter={(v) => `${v.toFixed(0)}m`}
    />
  );

  const commonYAxis = (
    <YAxis domain={[0, 105]} tickFormatter={(v) => `${v}%`} width={38} />
  );

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>◈</span>
          Telemetría de Pedales — Freno &amp; Acelerador
        </div>
        {zoomDomain && (
          <span className="chart-zoom-badge">
            ZOOM {zoomDomain[0].toFixed(0)}m → {zoomDomain[1].toFixed(0)}m
          </span>
        )}
      </div>

      {/* Brake sub-chart */}
      <div style={{ marginBottom: '4px' }}>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--red)', marginBottom: '4px', opacity: 0.8 }}>
          Freno
        </div>
        <div style={{ width: '100%', height: 170 }}>
          <ResponsiveContainer>
            <AreaChart data={chartData} margin={{ top: 4, right: 12, left: -16, bottom: 0 }} syncId="pedals">
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="distance" hide type="number" domain={['dataMin', 'dataMax']} />
              {commonYAxis}
              <Tooltip
                formatter={(v, n) => [`${Number(v).toFixed(1)}%`, lapLabels[n] || n]}
                labelFormatter={(l) => `${Number(l).toFixed(0)} m`}
              />
              {brakeKeys.map((key, idx) => (
                <Area
                  key={key} type="monotone" dataKey={key}
                  stroke={BRAKE_COLORS[idx % BRAKE_COLORS.length]}
                  fill={idx === 0 ? BRAKE_COLORS[0] : 'none'}
                  fillOpacity={0.18} strokeWidth={1.8}
                  activeDot={{ r: 3, strokeWidth: 0 }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Throttle sub-chart */}
      <div>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--green)', marginBottom: '4px', opacity: 0.8 }}>
          Acelerador
        </div>
        <div style={{ width: '100%', height: 170 }}>
          <ResponsiveContainer>
            <AreaChart data={chartData} margin={{ top: 4, right: 12, left: -16, bottom: 0 }} syncId="pedals">
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              {commonXAxis}
              {commonYAxis}
              <Tooltip
                formatter={(v, n) => [`${Number(v).toFixed(1)}%`, lapLabels[n] || n]}
                labelFormatter={(l) => `${Number(l).toFixed(0)} m`}
              />
              {throttleKeys.map((key, idx) => (
                <Area
                  key={key} type="monotone" dataKey={key}
                  stroke={THROTTLE_COLORS[idx % THROTTLE_COLORS.length]}
                  fill={idx === 0 ? THROTTLE_COLORS[0] : 'none'}
                  fillOpacity={0.15} strokeWidth={1.8}
                  activeDot={{ r: 3, strokeWidth: 0 }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default BrakeThrottleChart;
