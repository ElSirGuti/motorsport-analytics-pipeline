import React, { useMemo } from 'react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

const BRAKE_COLORS  = ['#FF6B00', '#FF0066', '#FF8C42', '#CC2936'];
const THROTTLE_COLORS = ['#00FF88', '#FFAA00', '#34D399', '#F59E0B'];

const BrakeThrottleChart = ({ brakeData, throttleData, zoomDomain }) => {
  const chartData = useMemo(() => {
    if (!brakeData || !brakeData.distance || !throttleData) return [];

    const rows = brakeData.distance.map((dist, i) => {
      const point = { distance: dist };
      Object.keys(brakeData).forEach((key) => {
        if (key.startsWith('brake_')) point[key] = brakeData[key][i];
      });
      Object.keys(throttleData).forEach((key) => {
        if (key.startsWith('throttle_')) point[key] = throttleData[key][i];
      });
      return point;
    });

    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [brakeData, throttleData, zoomDomain]);

  if (!chartData.length) return null;

  const brakeKeys    = Object.keys(brakeData).filter((k) => k.startsWith('brake_'));
  const throttleKeys = Object.keys(throttleData).filter((k) => k.startsWith('throttle_'));
  const lapLabels    = brakeData?.lap_labels || {};

  return (
    <div className="chart-container animate-in animate-in--delay-2">
      <h3 className="chart-container__title">
        🕹️ Telemetría de Pedales (Freno &amp; Acelerador)
      </h3>

      {/* Brake chart */}
      <div style={{ width: '100%', height: 200, marginBottom: '1rem' }}>
        <ResponsiveContainer>
          <AreaChart
            data={chartData}
            margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
            syncId="pedals"
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="distance" hide type="number" domain={['dataMin', 'dataMax']} />
            <YAxis domain={[0, 105]} tickFormatter={(val) => `${val}%`} />
            <Tooltip
              formatter={(value, name) => [`${value.toFixed(1)}%`, lapLabels[name] || name]}
              labelFormatter={(label) => `Distancia: ${Number(label).toFixed(0)}m`}
            />
            {brakeKeys.map((key, idx) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={BRAKE_COLORS[idx % BRAKE_COLORS.length]}
                fill={idx === 0 ? BRAKE_COLORS[0] : 'none'}
                fillOpacity={0.2}
                strokeWidth={2}
                activeDot={{ r: 4 }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Throttle chart */}
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer>
          <AreaChart
            data={chartData}
            margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
            syncId="pedals"
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="distance"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(val) => `${val.toFixed(0)}m`}
            />
            <YAxis domain={[0, 105]} tickFormatter={(val) => `${val}%`} />
            <Tooltip
              formatter={(value, name) => [`${value.toFixed(1)}%`, lapLabels[name] || name]}
              labelFormatter={(label) => `Distancia: ${Number(label).toFixed(0)}m`}
            />
            {throttleKeys.map((key, idx) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={THROTTLE_COLORS[idx % THROTTLE_COLORS.length]}
                fill={idx === 0 ? THROTTLE_COLORS[0] : 'none'}
                fillOpacity={0.15}
                strokeWidth={2}
                activeDot={{ r: 4 }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default BrakeThrottleChart;
