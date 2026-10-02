import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useCursorWriter } from '../hooks/useCursorWriter';
import { Panel } from './ui';
import { LAP_COLORS, TICK, AXIS_LINE, GRID_PROPS, CURSOR, ACTIVE_DOT, fmtDist } from './chartTheme';
import { ChartTooltip, ZoomBadge, SeriesLegend, ChartEmpty } from './chartKit';

// labels: translations object passed from parent
const SpeedChart = ({ data, zoomDomain, onChartClick, labels }) => {
  const cursorHandlers = useCursorWriter();
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
    return <ChartEmpty icon="gauge" title={labels?.speedTitle}>{labels?.speedNoData ?? ''}</ChartEmpty>;
  }

  const speedKeys = Object.keys(data).filter((k) => k.startsWith('speed_'));
  const lapLabels = data?.lap_labels || {};
  const legend = speedKeys.map((k, i) => ({ key: k, label: lapLabels[k] || k, color: LAP_COLORS[i % LAP_COLORS.length] }));

  return (
    <Panel icon="gauge" title={labels?.speedTitle ?? ''} subtitle="km/h" actions={<ZoomBadge domain={zoomDomain} />}>
      <SeriesLegend items={legend} />
      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer>
          <LineChart
            data={chartData}
            margin={{ top: 6, right: 12, left: 0, bottom: 0 }}
            syncId="distanceSync"
            {...cursorHandlers}
            onClick={(state) => { if (state?.activeLabel != null) onChartClick?.(state.activeLabel); }}
          >
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="distance" type="number" domain={['dataMin', 'dataMax']}
              tick={TICK} axisLine={AXIS_LINE} tickLine={false}
              tickFormatter={fmtDist} unit=" m" minTickGap={28}
            />
            <YAxis
              domain={['auto', 'auto']} tick={TICK} axisLine={false} tickLine={false}
              tickFormatter={(v) => v.toFixed(0)} width={40}
            />
            <Tooltip
              cursor={CURSOR}
              content={<ChartTooltip unit=" km/h" nameMap={lapLabels} />}
            />
            {speedKeys.map((key, idx) => (
              <Line
                key={key} type="monotone" dataKey={key} name={key}
                stroke={LAP_COLORS[idx % LAP_COLORS.length]}
                strokeWidth={1.75} dot={false} activeDot={ACTIVE_DOT}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
};

export default SpeedChart;
