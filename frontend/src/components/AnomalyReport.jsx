import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import { LAP_COLORS, COLOR, TICK, AXIS_LINE, GRID_PROPS, CURSOR, ACTIVE_DOT, fmtDist } from './chartTheme';
import { ChartTooltip, SeriesLegend } from './chartKit';
import styles from './AnomalyReport.module.css';

const SEV_TONE = { critico: 'bad', media: 'warn', leve: 'ok' };
const SEV_HEX  = { critico: COLOR.bad, media: COLOR.warn, leve: COLOR.ok };

// score is 0-1 where 0.6 = threshold. Normalise to 0-100 within 0.6-1.0 range.
const scoreToPercent = (s) => Math.round(Math.min(100, Math.max(0, (s - 0.6) / 0.4 * 100)));

const ScoreBar = ({ avg, peak, sevKey }) => {
  const color = `var(--${SEV_TONE[sevKey] ?? 'ok'})`;
  return (
    <div>
      <div className={styles.barMeta}>
        <span>Deviation from reference</span>
        <span className={styles.barNums} style={{ color }}>
          avg {(avg * 100).toFixed(0)}% · peak {(peak * 100).toFixed(0)}%
        </span>
      </div>
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{ width: `${scoreToPercent(avg)}%`, background: color }} />
        <div className={styles.barPeak} style={{ left: `${scoreToPercent(peak)}%`, background: color }} />
      </div>
    </div>
  );
};

const AnomalyReport = ({ anomaly }) => {
  const { t } = useLanguage();
  const { scores_fast = [], scores_slow = [], zones = [] } = anomaly || {};

  const chartData = useMemo(() => {
    if (!scores_slow.length) return [];
    const fastMap = new Map(scores_fast.map((p) => [p.distance, p.score]));
    return scores_slow.map((p) => ({
      distance: p.distance,
      slow: p.score,
      fast: fastMap.get(p.distance) ?? 0,
    }));
  }, [scores_fast, scores_slow]);

  if (!chartData.length && !zones.length) return null;

  const criticalZones = zones.filter((z) => (z.severity_key ?? z.severity) === 'critico').length;

  const SEV_LABEL = {
    critico: t.severityCritico,
    media:   t.severityMedia,
    leve:    t.severityLeve,
  };

  return (
    <Panel
      icon="alert"
      title={t.anomalyTitle}
      actions={(
        <>
          {criticalZones > 0 && <Badge tone="bad">{t.anomalyCritical(criticalZones)}</Badge>}
          <Badge>{zones.length === 1 ? t.anomalyZone(1) : t.anomalyZones(zones.length)}</Badge>
        </>
      )}
    >
      <p className={styles.desc}>{t.anomalyDescription}</p>

      {chartData.length > 0 && (
        <>
          <SeriesLegend items={[
            { key: 'fast', label: t.anomalyReference, color: LAP_COLORS[0] },
            { key: 'slow', label: t.anomalySlowLap, color: LAP_COLORS[1] },
            { key: 'thr', label: 'Threshold 60%', color: COLOR.warn },
          ]} />
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis
                dataKey="distance" type="number" domain={['dataMin', 'dataMax']}
                tick={TICK} axisLine={AXIS_LINE} tickLine={false}
                tickFormatter={fmtDist} unit=" m" minTickGap={28}
              />
              <YAxis
                domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={TICK} axisLine={false} tickLine={false}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={44}
              />
              <Tooltip
                cursor={CURSOR}
                content={<ChartTooltip digits={1} valueFormatter={(v) => `${(v * 100).toFixed(1)}%`} />}
              />
              <ReferenceLine y={0.6} stroke={COLOR.warn} strokeOpacity={0.6} strokeDasharray="4 3" />
              {zones.map((z, i) => (
                <ReferenceLine
                  key={i} x={z.start_m}
                  stroke={SEV_HEX[z.severity_key ?? 'leve']}
                  strokeWidth={1.25} strokeOpacity={0.55}
                />
              ))}
              <Area
                type="monotone" dataKey="fast" name={t.anomalyReference}
                stroke={LAP_COLORS[0]} strokeWidth={1.25} fill={LAP_COLORS[0]} fillOpacity={0.1}
                isAnimationActive={false} dot={false} activeDot={ACTIVE_DOT}
              />
              <Area
                type="monotone" dataKey="slow" name={t.anomalySlowLap}
                stroke={LAP_COLORS[1]} strokeWidth={1.75} fill={LAP_COLORS[1]} fillOpacity={0.14}
                isAnimationActive={false} dot={false} activeDot={ACTIVE_DOT}
              />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}

      {zones.length > 0 && (
        <div className={styles.zones}>
          {zones.map((z, i) => {
            const sevKey = z.severity_key ?? 'leve';
            return (
              <div key={i} className={styles.zone} style={{ borderLeftColor: `var(--${SEV_TONE[sevKey] ?? 'ok'})` }}>
                <div className={styles.zoneHead}>
                  <Badge tone={SEV_TONE[sevKey]}>{SEV_LABEL[sevKey] ?? z.severity}</Badge>
                  <span className={styles.range}>{z.start_m.toFixed(0)} – {z.end_m.toFixed(0)} m</span>
                  <span className={styles.len}>{z.length_m.toFixed(0)} m zone</span>
                </div>
                <ScoreBar avg={z.avg_score} peak={z.peak_score} sevKey={sevKey} />
                <p className={styles.zoneDesc}>{z.descripcion}</p>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
};

export default AnomalyReport;
