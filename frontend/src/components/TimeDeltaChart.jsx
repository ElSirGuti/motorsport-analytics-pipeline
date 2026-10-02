import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useCursorWriter } from '../hooks/useCursorWriter';
import { Panel } from './ui';
import { COLOR, TICK, AXIS_LINE, GRID_PROPS, CURSOR, ACTIVE_DOT, fmtDist } from './chartTheme';
import { ChartTooltip, ZoomBadge, ChartEmpty } from './chartKit';
import styles from './chartKit.module.css';

// labels: translations object passed from parent
const TimeDeltaChart = ({ data, zoomDomain, onChartClick, labels }) => {
  const cursorHandlers = useCursorWriter();
  const chartData = useMemo(() => {
    if (!data?.distance) return [];
    const rows = data.distance.map((dist, i) => ({
      distance: dist,
      delta: data.delta[i],
      loss: data.delta[i] >= 0 ? data.delta[i] : 0,
      gain: data.delta[i] <= 0 ? data.delta[i] : 0,
    }));
    if (!zoomDomain) return rows;
    const [lo, hi] = zoomDomain;
    return rows.filter((r) => r.distance >= lo && r.distance <= hi);
  }, [data, zoomDomain]);

  if (!chartData.length) {
    return <ChartEmpty icon="stopwatch" title={labels?.timeDeltaTitle}>{labels?.timeDeltaNoData ?? ''}</ChartEmpty>;
  }

  const maxAbs = Math.max(...chartData.map((r) => Math.abs(r.delta)));
  const yPad   = maxAbs * 0.15 || 0.05;
  const lossLabel = labels?.timeDeltaLoss || 'Loss';
  const gainLabel = labels?.timeDeltaGain || 'Gain';

  return (
    <Panel icon="stopwatch" title={labels?.timeDeltaTitle ?? ''} subtitle="s" actions={<ZoomBadge domain={zoomDomain} />}>
      <ul className={styles.legend}>
        <li className={styles.legendItem}><span className={styles.legendLine} style={{ background: COLOR.bad }} />{lossLabel}</li>
        <li className={styles.legendItem}><span className={styles.legendLine} style={{ background: COLOR.ok }} />{gainLabel}</li>
      </ul>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 12, left: 0, bottom: 0 }}
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
              domain={[-(maxAbs + yPad), maxAbs + yPad]}
              tick={TICK} axisLine={false} tickLine={false}
              tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}`}
              width={52}
            />
            <Tooltip
              cursor={CURSOR}
              content={<ChartTooltip digits={3} unit=" s" sign hideKeys={['loss', 'gain']} nameMap={{ delta: 'Delta' }} />}
            />
            <ReferenceLine y={0} stroke={COLOR.ink3} strokeOpacity={0.6} />
            <Area type="monotone" dataKey="loss" name={lossLabel} stroke="none" fill={COLOR.bad} fillOpacity={0.22} isAnimationActive={false} activeDot={false} />
            <Area type="monotone" dataKey="gain" name={gainLabel} stroke="none" fill={COLOR.ok} fillOpacity={0.22} isAnimationActive={false} activeDot={false} />
            <Area type="monotone" dataKey="delta" name="Delta" stroke="#e8ecf2" strokeWidth={1.5} fill="none" activeDot={ACTIVE_DOT} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
};

export default TimeDeltaChart;
