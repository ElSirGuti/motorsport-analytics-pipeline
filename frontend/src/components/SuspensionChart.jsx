import { useMemo } from 'react';
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import styles from './Analysis.module.css';
import {
  COLOR_A, COLOR_B, COLOR_D, AXIS_TICK, AXIS_LINE, GRID_PROPS, REF_ZERO,
  CHART_MARGIN, fmtDist, makeTooltip, Legend,
} from './analysisKit';

const tooltip = makeTooltip((v) => `${v > 0 ? '+' : ''}${v.toFixed(1)} mm`);

const StatCell = ({ label, value, color }) => (
  <div className={styles.card}>
    <div className={styles.mLabel} style={{ marginBottom: 4 }}>
      <span className={styles.swatch} style={{ background: color, display: 'inline-block', marginRight: 6 }} />
      {label}
    </div>
    <div className={styles.mValue}>
      {value != null ? value.toFixed(1) : '—'}
      <span className={styles.mUnit}>mm</span>
    </div>
  </div>
);

const BottomingBadges = ({ events, color, label }) => {
  if (!events?.length) return null;
  return (
    <div className={styles.group}>
      <div className={styles.groupLabel}>
        <Icon name="alert" size={13} style={{ color: 'var(--bad)' }} />
        <span style={{ color }}>{label}</span>
      </div>
      <div className={styles.chips}>
        {events.map((e, i) => (
          <span key={i} className={styles.chip}>
            {e.corner} · {e.start_m.toFixed(0)}–{e.end_m.toFixed(0)} m
            <span className={styles.chipMute}>({(e.severity * 100).toFixed(0)}%)</span>
          </span>
        ))}
      </div>
    </div>
  );
};

const SuspensionChart = ({ suspension, metadata }) => {
  const { t } = useLanguage();
  const data = suspension;

  const seriesA = data?.available_a ? data.per_distance_a : null;
  const seriesB = data?.available_b ? data.per_distance_b : null;
  const primary = seriesA || seriesB;

  const chartData = useMemo(() => {
    if (!primary?.distance) return [];
    return primary.distance.map((d, i) => ({
      distance: d,
      roll_f_a: seriesA?.roll_f?.[i] ?? null,
      roll_r_a: seriesA?.roll_r?.[i] ?? null,
      pitch_a: seriesA?.pitch?.[i] ?? null,
      roll_f_b: seriesB?.roll_f?.[i] ?? null,
      pitch_b: seriesB?.pitch?.[i] ?? null,
    }));
  }, [primary, seriesA, seriesB]);

  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';
  const summaryA = data.summary_a;
  const summaryB = data.summary_b;

  return (
    <Panel icon="activity" title={t.suspensionTitle} actions={<Badge>{t.suspensionBadge}</Badge>}>
      <p className={styles.desc}>{t.suspensionDescription}</p>

      {(summaryA || summaryB) && (
        <div className={styles.cards} style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
          {summaryA && (
            <>
              <StatCell label={t.suspensionRollFront(labelA)} value={summaryA.max_roll_f} color={COLOR_A} />
              <StatCell label={t.suspensionRollRear(labelA)} value={summaryA.max_roll_r} color={COLOR_A} />
              <StatCell label={t.suspensionPitch(labelA)} value={summaryA.max_pitch} color={COLOR_A} />
            </>
          )}
          {summaryB && (
            <>
              <StatCell label={t.suspensionRollFront(labelB)} value={summaryB.max_roll_f} color={COLOR_B} />
              <StatCell label={t.suspensionPitch(labelB)} value={summaryB.max_pitch} color={COLOR_B} />
            </>
          )}
        </div>
      )}

      {chartData.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>Roll / Pitch (mm)</span>
            <Legend items={[
              ...(seriesA ? [
                { label: `Roll ${labelA}`, color: COLOR_A },
                { label: `Pitch ${labelA}`, color: COLOR_D, dashed: true },
              ] : []),
              ...(seriesB ? [{ label: `Roll ${labelB}`, color: COLOR_B }] : []),
            ]} />
          </div>
          <ResponsiveContainer width="100%" height={210}>
            <ComposedChart data={chartData} margin={CHART_MARGIN}>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} unit=" mm" width={52} domain={['auto', 'auto']} />
              <Tooltip content={tooltip} cursor={{ stroke: '#323b48' }} />
              <ReferenceLine y={0} stroke={REF_ZERO} />
              {seriesA && (
                <>
                  <Line type="monotone" dataKey="roll_f_a" name={`Roll ${labelA}`} stroke={COLOR_A} strokeWidth={1.5}
                    dot={false} isAnimationActive={false} connectNulls />
                  <Line type="monotone" dataKey="pitch_a" name={`Pitch ${labelA}`} stroke={COLOR_D} strokeWidth={1.25}
                    strokeDasharray="4 2" dot={false} isAnimationActive={false} connectNulls />
                </>
              )}
              {seriesB && (
                <Line type="monotone" dataKey="roll_f_b" name={`Roll ${labelB}`} stroke={COLOR_B} strokeWidth={1.5}
                  dot={false} isAnimationActive={false} connectNulls />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <BottomingBadges events={data.bottoming_a} color={COLOR_A} label={t.suspensionBottoming(labelA)} />
      <BottomingBadges events={data.bottoming_b} color={COLOR_B} label={t.suspensionBottoming(labelB)} />
    </Panel>
  );
};

export default SuspensionChart;
