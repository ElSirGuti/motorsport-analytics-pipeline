import { useMemo } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, EmptyState } from './ui';
import css from './LapTimelineChart.module.css';

const HIDDEN_SERIES = ['band_floor', 'band_dim_low', 'band_bright', 'band_dim_high', 'pit_marker'];
const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' };

const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');

function fmtLaptime(seconds) {
  if (seconds == null || isNaN(seconds) || seconds <= 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(3);
  return `${m}:${s.padStart(6, '0')}`;
}

function fmtAxis(seconds) {
  if (seconds == null || isNaN(seconds) || seconds <= 0) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

const CustomTooltip = ({ active, payload, label, t }) => {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  const isPit = point?.pit_actual_time != null;

  return (
    <div className={css.tip}>
      <div className={css.tipHead}>
        {t.timelineLap} {label}
        {isPit && <Badge tone="warn">{clean(t.timelineLegendPit)}</Badge>}
      </div>
      {isPit ? (
        <div className={css.tipRow}>
          {clean(t.timelinePitStop)}<b>{fmtLaptime(point.pit_actual_time)}</b>
        </div>
      ) : (
        payload.map((p) => {
          if (!p.value || HIDDEN_SERIES.includes(p.name)) return null;
          return (
            <div key={p.name} className={css.tipRow}>
              <span className={css.sw} style={{ background: p.color || p.stroke }} />
              {p.name}<b>{fmtLaptime(p.value)}</b>
            </div>
          );
        })
      )}
    </div>
  );
};

function Swatch({ color, dashed, dot, band }) {
  if (band) return <svg width="16" height="10" aria-hidden="true"><rect width="16" height="10" rx="2" fill={color} fillOpacity=".25" /></svg>;
  return (
    <svg width="18" height="10" aria-hidden="true">
      <line x1="0" y1="5" x2="18" y2="5" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '4 3' : undefined} />
      {dot && <circle cx="9" cy="5" r="3.5" fill={color} />}
    </svg>
  );
}

const Legend = ({ hasPitLaps, hasMC, t }) => (
  <div className={css.legend}>
    <span className={css.legendItem}><Swatch color="var(--lap-a)" dot /> {t.timelineLegendActual}</span>
    <span className={css.legendItem}><Swatch color="var(--ink-3)" dashed /> {t.timelineLegendTrend}</span>
    {hasMC && <span className={css.legendItem}><Swatch color="var(--warn)" dashed /> {t.timelineLegendMC}</span>}
    {hasMC && <span className={css.legendItem}><Swatch color="var(--warn)" band /> P10 – P90</span>}
    {hasPitLaps && <span className={css.legendItem}><Swatch color="var(--lap-e)" dot /> {clean(t.timelineLegendPit)}</span>}
  </div>
);

export default function LapTimelineChart({ degradacion, montecarlo, laps }) {
  const { t } = useLanguage();
  const { chartData, separatorLap, yDomain, pitLapNums } = useMemo(() => {
    if (!degradacion?.available) return { chartData: [], separatorLap: null, yDomain: ['auto', 'auto'], pitLapNums: new Set() };

    const pitSet = new Set((laps || []).filter(l => l.is_pit_lap).map(l => l.lap_number));
    const pitTimeMap = {};
    const racingMap = {};
    (laps || []).forEach(l => {
      if (l.is_pit_lap) pitTimeMap[l.lap_number] = l.lap_time_s;
      else racingMap[l.lap_number] = l.lap_time_s;
    });

    const trendMap = {};
    (degradacion.trend_laps || []).forEach((lap, i) => { trendMap[lap] = degradacion.trend_times[i]; });

    const mcMap = {}, p10Map = {}, p25Map = {}, p75Map = {}, p90Map = {};
    if (montecarlo?.available) {
      (montecarlo.future_laps || []).forEach((lap, i) => {
        mcMap[lap]  = montecarlo.p50[i];
        p10Map[lap] = montecarlo.p10[i];
        p25Map[lap] = montecarlo.p25[i];
        p75Map[lap] = montecarlo.p75[i];
        p90Map[lap] = montecarlo.p90[i];
      });
    }

    const racingTimes = [
      ...(degradacion.actual_times || []),
      ...(montecarlo?.p10 || []),
      ...(montecarlo?.p90 || []),
    ].filter(v => v != null && !isNaN(v) && v > 0);

    const minT = racingTimes.length ? Math.min(...racingTimes) - 1.0 : 0;
    const maxT = racingTimes.length ? Math.max(...racingTimes) + 1.0 : 300;

    const allLaps = new Set([
      ...(degradacion.actual_laps || []),
      ...(degradacion.projected_laps || []),
      ...Object.keys(pitTimeMap).map(Number),
    ]);
    const lastActual = Math.max(...(degradacion.actual_laps || [0]), ...pitSet);

    const data = [...allLaps].sort((a, b) => a - b).map(lap => {
      const isProjected = lap > lastActual;
      const p10 = p10Map[lap], p25 = p25Map[lap], p75 = p75Map[lap], p90 = p90Map[lap];
      return {
        lap,
        actual:          pitSet.has(lap) ? null : (racingMap[lap] ?? null),
        pit_marker:      pitSet.has(lap) ? minT + (maxT - minT) * 0.025 : null,
        pit_actual_time: pitTimeMap[lap] ?? null,
        trend:           trendMap[lap]  ?? null,
        mc_p50:          mcMap[lap]     ?? null,
        band_floor:    isProjected && p10 != null ? p10 : null,
        band_dim_low:  isProjected && p25 != null && p10 != null ? p25 - p10 : null,
        band_bright:   isProjected && p75 != null && p25 != null ? p75 - p25 : null,
        band_dim_high: isProjected && p90 != null && p75 != null ? p90 - p75 : null,
      };
    });

    return {
      chartData: data,
      separatorLap: lastActual + 0.5,
      yDomain: [minT, maxT],
      pitLapNums: pitSet,
    };
  }, [degradacion, montecarlo, laps]);

  const title = clean(t.timelineTitle);

  if (!degradacion?.available || chartData.length === 0) {
    return (
      <Panel icon="activity" title={title}>
        <EmptyState icon="activity">{t.timelineNoData}</EmptyState>
      </Panel>
    );
  }

  const hasMC = !!montecarlo?.available;

  return (
    <Panel
      icon="activity"
      title={title}
      actions={(
        <span className={css.headBadges}>
          {pitLapNums.size > 0 && <Badge tone="warn">{clean(t.timelineLegendPit)} · {pitLapNums.size}</Badge>}
          {hasMC && <Badge title="Monte Carlo">σ = {montecarlo.sigma_real_s}s</Badge>}
        </span>
      )}
    >
      <div className={css.chart}>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeOpacity={0.6} vertical={false} />
            <XAxis
              dataKey="lap"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: 'var(--line-strong)' }}
              label={{ value: t.timelineLap, position: 'insideBottom', offset: -2, fill: 'var(--ink-3)', fontSize: 11 }}
              height={36}
            />
            <YAxis
              domain={yDomain}
              allowDataOverflow
              tickFormatter={fmtAxis}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip content={<CustomTooltip t={t} />} cursor={{ stroke: 'var(--ink-4)', strokeDasharray: '3 3' }} />

            {[...pitLapNums].map(lapNum => (
              <ReferenceLine
                key={`pit-${lapNum}`}
                x={lapNum}
                stroke="var(--lap-e)"
                strokeOpacity={0.5}
                strokeDasharray="3 3"
                label={{ value: 'PIT', fill: 'var(--lap-e)', fontSize: 10, fontWeight: 600, position: 'insideTop' }}
              />
            ))}

            {separatorLap && hasMC && (
              <ReferenceLine
                x={separatorLap}
                stroke="var(--ink-4)"
                strokeDasharray="4 4"
                label={{ value: clean(t.timelineProjection), fill: 'var(--ink-3)', fontSize: 10, position: 'insideTopRight' }}
              />
            )}

            <Area dataKey="band_floor"    stackId="mc" fill="transparent"  stroke="none" isAnimationActive={false} legendType="none" />
            <Area dataKey="band_dim_low"  stackId="mc" fill="var(--warn)" fillOpacity={0.08} stroke="none" isAnimationActive={false} legendType="none" />
            <Area dataKey="band_bright"   stackId="mc" fill="var(--warn)" fillOpacity={0.2}  stroke="none" isAnimationActive={false} legendType="none" />
            <Area dataKey="band_dim_high" stackId="mc" fill="var(--warn)" fillOpacity={0.08} stroke="none" isAnimationActive={false} legendType="none" />

            <Line dataKey="mc_p50" name={t.timelineLegendMC} stroke="var(--warn)" strokeWidth={1.5}
              strokeDasharray="5 3" dot={false} isAnimationActive={false} connectNulls={false} />

            <Line dataKey="trend" name={t.timelineLegendTrend} stroke="var(--ink-3)" strokeWidth={1.25}
              strokeDasharray="4 4" dot={false} isAnimationActive={false} connectNulls={false} />

            <Line dataKey="actual" name={t.timelineLegendActual} stroke="var(--lap-a)" strokeWidth={2}
              dot={{ fill: 'var(--lap-a)', r: 3.5, strokeWidth: 0 }}
              activeDot={{ r: 5.5 }} isAnimationActive={false} connectNulls={false} />

            <Line dataKey="pit_marker" name="pit_marker" stroke="none" strokeWidth={0}
              dot={{ fill: 'var(--surface-1)', r: 5, strokeWidth: 2, stroke: 'var(--lap-e)' }}
              activeDot={{ r: 7 }} isAnimationActive={false} connectNulls={false} legendType="none" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <Legend hasPitLaps={pitLapNums.size > 0} hasMC={hasMC} t={t} />
    </Panel>
  );
}
