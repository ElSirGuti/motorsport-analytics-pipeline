import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

const TimeDeltaChart = ({ data, zoomDomain }) => {
  const chartData = useMemo(() => {
    if (!data || !data.distance) return [];

    const rows = data.distance.map((dist, i) => ({
      distance: dist,
      delta: data.delta[i],
    }));

    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [data, zoomDomain]);

  if (!chartData.length) return null;

  // Custom SVG gradient defs for the area chart
  const renderGradient = () => (
    <defs>
      <linearGradient id="colorDelta" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#FF4444" stopOpacity={0.8}/>
        <stop offset="50%" stopColor="#FF4444" stopOpacity={0.1}/>
        <stop offset="50%" stopColor="#00FF88" stopOpacity={0.1}/>
        <stop offset="95%" stopColor="#00FF88" stopOpacity={0.8}/>
      </linearGradient>
    </defs>
  );

  return (
    <div className="chart-container animate-in animate-in--delay-3">
      <h3 className="chart-container__title">
        ⏱️ Delta de Tiempo Acumulado (s)
      </h3>
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            {renderGradient()}
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis 
              dataKey="distance" 
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(val) => `${val.toFixed(0)}m`}
            />
            <YAxis 
              tickFormatter={(val) => `${val > 0 ? '+' : ''}${val.toFixed(2)}s`}
            />
            <Tooltip 
              formatter={(value) => [
                <span style={{ color: value >= 0 ? '#FF4444' : '#00FF88' }}>
                  {value > 0 ? '+' : ''}{value.toFixed(3)}s
                </span>, 
                'Delta'
              ]}
              labelFormatter={(label) => `Distancia: ${Number(label).toFixed(0)}m`}
            />
            <ReferenceLine y={0} stroke="#94A3B8" strokeDasharray="3 3" />
            <Area 
              type="monotone" 
              dataKey="delta" 
              stroke="#FFFFFF" 
              strokeWidth={1.5}
              fillOpacity={1} 
              fill="url(#colorDelta)" 
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TimeDeltaChart;
