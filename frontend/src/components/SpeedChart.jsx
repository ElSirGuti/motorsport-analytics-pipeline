import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

const COLORS = ['#00D4FF', '#FF3D3D', '#00E676', '#FFB300', '#FF69B4', '#A78BFA'];

const SpeedChart = ({ data, zoomDomain }) => {
  const chartData = useMemo(() => {
    if (!data?.distance) return [];
    const rows = data.distance.map((dist, i) => {
      const point = { distance: dist };
      Object.keys(data).forEach((key) => {
        if (key.startsWith('speed_')) point[key] = data[key][i];
      });
      return point;
    });
    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [data, zoomDomain]);

  if (!chartData.length) {
    return (
      <div className="chart-card">
        <div className="chart-empty">
          <span className="chart-empty__icon">◌</span>
          Sin datos de velocidad
        </div>
      </div>
    );
  }

  const speedKeys  = Object.keys(data).filter((k) => k.startsWith('speed_'));
  const lapLabels  = data?.lap_labels || {};

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">
          <span>⚡</span>
          Velocidad vs Distancia
        </div>
        {zoomDomain && (
          <span className="chart-zoom-badge">
            ZOOM {zoomDomain[0].toFixed(0)}m → {zoomDomain[1].toFixed(0)}m
          </span>
        )}
      </div>
      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 6, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="distance"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(v) => `${v.toFixed(0)}m`}
            />
            <YAxis
              domain={['auto', 'auto']}
              tickFormatter={(v) => `${v.toFixed(0)}`}
              unit=" km/h"
            />
            <Tooltip
              formatter={(value, name) => [`${Number(value).toFixed(1)} km/h`, lapLabels[name] || name]}
              labelFormatter={(l) => `${Number(l).toFixed(0)} m`}
            />
            <Legend
              formatter={(name) => lapLabels[name] || name}
              wrapperStyle={{ paddingTop: '8px', fontSize: '0.78rem' }}
            />
            {speedKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={1.8}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default SpeedChart;
