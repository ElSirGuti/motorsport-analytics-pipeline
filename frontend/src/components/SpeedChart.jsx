import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

const COLORS = [
  '#00D4FF', '#FF4444', '#00FF88', '#FFAA00',
  '#FF69B4', '#A78BFA', '#F97316', '#34D399',
];

const SpeedChart = ({ data, zoomDomain }) => {
  const chartData = useMemo(() => {
    if (!data || !data.distance) return [];

    const rows = data.distance.map((dist, i) => {
      const point = { distance: dist };
      // Support N laps: speed_a, speed_b, speed_c …
      Object.keys(data).forEach((key) => {
        if (key.startsWith('speed_')) point[key] = data[key][i];
      });
      return point;
    });

    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [data, zoomDomain]);

  if (!chartData.length) return null;

  const speedKeys = data ? Object.keys(data).filter((k) => k.startsWith('speed_')) : [];
  const lapLabels = data?.lap_labels || {};

  return (
    <div className="chart-container animate-in animate-in--delay-1">
      <h3 className="chart-container__title">⚡ Velocidad vs Distancia</h3>
      {zoomDomain && (
        <div style={{ fontSize: '0.75rem', color: '#00D4FF', marginBottom: '4px', textAlign: 'center', letterSpacing: '0.05em' }}>
          🔍 ZOOM: {zoomDomain[0].toFixed(0)}m → {zoomDomain[1].toFixed(0)}m
        </div>
      )}
      <div style={{ width: '100%', height: 350 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="distance"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(val) => `${val.toFixed(0)}m`}
            />
            <YAxis domain={['auto', 'auto']} tickFormatter={(val) => `${val} km/h`} />
            <Tooltip
              formatter={(value, name) => [
                `${value.toFixed(1)} km/h`,
                lapLabels[name] || name,
              ]}
              labelFormatter={(label) => `Distancia: ${Number(label).toFixed(0)}m`}
            />
            {speedKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name={key}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default SpeedChart;
