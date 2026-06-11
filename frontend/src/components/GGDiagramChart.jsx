import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Customized, Legend, Cell,
} from 'recharts';

const FAST_COLOR = '#00D4FF';
const SLOW_COLOR = '#FF3D3D';
const CIRCLE_COLOR = 'rgba(255,255,255,0.2)';

function FrictionCircle({ gLimit, xAxisMap, yAxisMap }) {
  const xKey = Object.keys(xAxisMap || {})[0];
  const yKey = Object.keys(yAxisMap || {})[0];
  if (!xKey || !yKey) return null;
  const xAxis = xAxisMap[xKey];
  const yAxis = yAxisMap[yKey];
  if (!xAxis || !yAxis) return null;

  const cx = xAxis.scale(0);
  const cy = yAxis.scale(0);
  const xRadius = Math.abs(xAxis.scale(gLimit) - cx);
  const yRadius = Math.abs(cy - yAxis.scale(gLimit));

  return (
    <g>
      <ellipse cx={cx} cy={cy} rx={xRadius} ry={yRadius}
        fill="none" stroke={CIRCLE_COLOR}
        strokeWidth={1.5} strokeDasharray="4 4" />
      <line x1={cx - xRadius} y1={cy} x2={cx + xRadius} y2={cy}
        stroke={CIRCLE_COLOR} strokeWidth={0.5} strokeDasharray="2 3" />
      <line x1={cx} y1={cy - yRadius} x2={cx} y2={cy + yRadius}
        stroke={CIRCLE_COLOR} strokeWidth={0.5} strokeDasharray="2 3" />
    </g>
  );
}


const renderTooltip = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem',
      fontFamily: "'JetBrains Mono', monospace", color: '#8899BB',
    }}>
      <div style={{ color: '#fff', marginBottom: 4 }}>
        {d._lap === 'fast' ? '🔵 Vuelta rápida' : '🔴 Vuelta lenta'}
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

const CircleDot = (props) => {
  const { cx, cy, fill, fillOpacity } = props;
  if (cx == null || cy == null) return null;
  return <circle cx={cx} cy={cy} r={3} fill={fill} fillOpacity={fillOpacity} />;
};

const GGDiagramChart = ({ ggData, gLimit }) => {
  const hasFast = ggData?.fast?.length > 0;
  const hasSlow = ggData?.slow?.length > 0;
  if (!hasFast && !hasSlow) return null;

  const limit = gLimit || 1.0;
  const pad = limit * 0.15;
  const domain = [-limit - pad, limit + pad];

  const fastData = hasFast ? ggData.fast.map((p) => ({ ...p, _lap: 'fast' })) : [];
  const slowData = hasSlow ? ggData.slow.map((p) => ({ ...p, _lap: 'slow' })) : [];

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◎</span> Diagrama G-G — Círculo de Fricción</div>
        <div className="chart-zoom-badge">Límite {limit.toFixed(2)} G</div>
      </div>
      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 12, right: 20, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
          <XAxis
            type="number" dataKey="lon" domain={domain}
            tick={{ fontSize: 11 }} tickCount={7}
            label={{ value: 'Longitudinal G (frenada ← → aceleración)', position: 'insideBottom', offset: -4, fill: '#667799', fontSize: 11 }}
          />
          <YAxis
            type="number" dataKey="lat" domain={domain}
            tick={{ fontSize: 11 }} tickCount={7}
            label={{ value: 'Lateral G', angle: -90, position: 'insideLeft', offset: 2, fill: '#667799', fontSize: 11 }}
          />
          <Tooltip content={renderTooltip} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} />
          <Legend
            formatter={(v) => v === 'fast' ? 'Vuelta rápida' : v === 'slow' ? 'Vuelta lenta' : v}
          />
          <Customized component={(p) => <FrictionCircle gLimit={limit} {...p} />} />
          {fastData.length > 0 && (
            <Scatter name="fast" data={fastData} isAnimationActive={false}
              shape={<CircleDot fill={FAST_COLOR} fillOpacity={0.5} />}>
              {fastData.map((p, i) => {
                const color = p.eff >= 90 ? '#00E676' : p.eff >= 70 ? '#FFB300' : p.eff >= 50 ? '#FF8C42' : FAST_COLOR;
                return <Cell key={i} fill={color} fillOpacity={0.5} />;
              })}
            </Scatter>
          )}
          {slowData.length > 0 && (
            <Scatter name="slow" data={slowData} isAnimationActive={false}
              shape={<CircleDot fill={SLOW_COLOR} fillOpacity={0.35} />}>
              {slowData.map((p, i) => {
                const color = p.eff >= 90 ? '#00E676' : p.eff >= 70 ? '#FFB300' : p.eff >= 50 ? '#FF8C42' : SLOW_COLOR;
                return <Cell key={i} fill={color} fillOpacity={0.35} />;
              })}
            </Scatter>
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};

export default GGDiagramChart;
