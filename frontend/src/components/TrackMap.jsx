import React from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const TrackMap = ({ trackData, highlightDomain = null }) => {
  if (!trackData || trackData.length === 0) return null;

  // Encontrar límites para escalar correctamente (mantener aspecto cuadrado)
  const xValues = trackData.map((d) => d.x);
  const yValues = trackData.map((d) => d.y);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  // Asegurar proporción 1:1 en la medida de lo posible si Recharts lo permite,
  // pero podemos usar el mismo dominio o dejar que autoescale.

  return (
    <div className="card track-map-card" style={{ height: '400px', width: '100%', marginBottom: '20px' }}>
      <h3 className="chart-title">Mapa del Circuito</h3>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart
          margin={{
            top: 20,
            right: 20,
            bottom: 20,
            left: 20,
          }}
        >
          <XAxis type="number" dataKey="x" name="X" domain={[xMin, xMax]} tick={false} axisLine={false} />
          <YAxis type="number" dataKey="y" name="Y" domain={[yMin, yMax]} tick={false} axisLine={false} />
          <ZAxis range={[10, 10]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Scatter name="Track" data={trackData} fill="#ff4b4b" line shape="circle" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TrackMap;
