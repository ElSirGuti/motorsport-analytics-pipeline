import { useMemo } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';
import { useCursorWriter } from '../hooks/useCursorWriter';
import { Panel } from './ui';
import { LAP_COLORS, TICK, AXIS_LINE, GRID_PROPS, CURSOR, ACTIVE_DOT, fmtDist } from './chartTheme';
import { ChartTooltip, ZoomBadge, SeriesLegend, ChartEmpty } from './chartKit';
import styles from './BrakeThrottleChart.module.css';

// labels: translations object passed from parent
const BrakeThrottleChart = ({ brakeData, throttleData, zoomDomain, onChartClick, labels }) => {
  const cursorHandlers = useCursorWriter();
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
    return <ChartEmpty icon="activity" title={labels?.brakeThrottleTitle}>{labels?.brakeThrottleNoData ?? ''}</ChartEmpty>;
  }

  const brakeKeys    = Object.keys(brakeData).filter((k) => k.startsWith('brake_'));
  const throttleKeys = Object.keys(throttleData).filter((k) => k.startsWith('throttle_'));
  const lapLabels    = { ...(throttleData?.lap_labels || {}), ...(brakeData?.lap_labels || {}) };

  const onClick = (state) => { if (state?.activeLabel != null) onChartClick?.(state.activeLabel); };
  const yAxis = <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tick={TICK} axisLine={false} tickLine={false} width={40} />;
  const tooltip = <Tooltip cursor={CURSOR} content={<ChartTooltip unit="%" nameMap={lapLabels} />} />;

  const renderAreas = (keys) => keys.map((key, idx) => (
    <Area
      key={key} type="monotone" dataKey={key} name={key}
      stroke={LAP_COLORS[idx % LAP_COLORS.length]}
      fill={LAP_COLORS[idx % LAP_COLORS.length]}
      fillOpacity={idx === 0 ? 0.14 : 0}
      strokeWidth={1.75} activeDot={ACTIVE_DOT} isAnimationActive={false}
    />
  ));

  const prefix = `${labels?.brakeThrottleBrake ?? ''} — `;
  const legend = brakeKeys.map((k, i) => ({
    key: k, color: LAP_COLORS[i % LAP_COLORS.length],
    label: (brakeData.lap_labels?.[k] || k).replace(prefix, ''),
  }));

  return (
    <Panel icon="activity" title={labels?.brakeThrottleTitle ?? ''} subtitle="%" actions={<ZoomBadge domain={zoomDomain} />}>
      <SeriesLegend items={legend} />

      <div className={styles.lane}>{labels?.brakeThrottleBrake ?? ''}</div>
      <div style={{ width: '100%', height: 150 }}>
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }} syncId="pedals" {...cursorHandlers} onClick={onClick}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="distance" hide type="number" domain={['dataMin', 'dataMax']} />
            {yAxis}
            {tooltip}
            {renderAreas(brakeKeys)}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className={styles.lane}>{labels?.brakeThrottleThrottle ?? ''}</div>
      <div style={{ width: '100%', height: 170 }}>
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }} syncId="pedals" {...cursorHandlers} onClick={onClick}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="distance" type="number" domain={['dataMin', 'dataMax']}
              tick={TICK} axisLine={AXIS_LINE} tickLine={false}
              tickFormatter={fmtDist} unit=" m" minTickGap={28}
            />
            {yAxis}
            {tooltip}
            {renderAreas(throttleKeys)}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
};

export default BrakeThrottleChart;
