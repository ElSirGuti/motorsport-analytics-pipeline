import { useMemo } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import styles from './Analysis.module.css';
import {
  COLOR_A, COLOR_B, COLOR_E, COLOR_D, AXIS_TICK, AXIS_LINE, GRID_PROPS, REF_ZERO,
  CHART_MARGIN, fmtDist, makeTooltip, Legend,
} from './analysisKit';

const COLOR_US = 'var(--lap-a)';
const COLOR_OS = 'var(--lap-b)';

const tooltip = makeTooltip((v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}°`);

const BalanceBar = ({ us, os, neutral }) => {
  const { t } = useLanguage();
  if (us == null) return null;
  return (
    <div>
      <div className={styles.bar} role="img" aria-label={`${t.slipAngleSub} ${us}%, ${t.slipAngleNeutral} ${neutral}%, ${t.slipAngleOver} ${os}%`}>
        <div style={{ width: `${us}%`, background: COLOR_US }} />
        <div style={{ width: `${neutral}%`, background: 'var(--ink-4)' }} />
        <div style={{ width: `${os}%`, background: COLOR_OS }} />
      </div>
      <div className={styles.barLabels}>
        <span style={{ color: COLOR_US }}>{t.slipAngleSub} {us?.toFixed(0)}%</span>
        <span>{t.slipAngleNeutral} {neutral?.toFixed(0)}%</span>
        <span style={{ color: COLOR_OS }}>{t.slipAngleOver} {os?.toFixed(0)}%</span>
      </div>
    </div>
  );
};

const Metric = ({ label, value, color }) => (
  <div className={styles.metric}>
    <span className={styles.mLabel}>{label}</span>
    <span className={styles.mValue} style={color ? { color } : undefined}>{value}</span>
  </div>
);

const LapSummaryCard = ({ summary, label, color }) => {
  const { t } = useLanguage();
  if (!summary) return null;
  const { beta_max, beta_p95, understeer_pct, oversteer_pct, neutral_pct, balance_mean } = summary;
  const balColor = balance_mean > 1 ? COLOR_US : balance_mean < -1 ? COLOR_OS : 'var(--ok)';
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <span className={styles.lapName}><span className={styles.swatch} style={{ background: color }} />{label}</span>
      </div>
      <div className={styles.metrics}>
        <Metric label={t.slipAngleMax} value={beta_max != null ? `${beta_max.toFixed(1)}°` : '—'} />
        <Metric label={t.slipAngleP95} value={beta_p95 != null ? `${beta_p95.toFixed(1)}°` : '—'} />
        {balance_mean != null && (
          <Metric
            label={t.slipAngleBalanceLabel}
            value={`${balance_mean > 0 ? '+' : ''}${balance_mean.toFixed(1)}°`}
            color={balColor}
          />
        )}
      </div>
      <BalanceBar us={understeer_pct} os={oversteer_pct} neutral={neutral_pct} />
    </div>
  );
};

const SlipAngleChart = ({ slip_angle, metadata }) => {
  const { t } = useLanguage();
  const data = slip_angle;

  const hasA = !!data?.available_a;
  const hasB = !!data?.available_b;
  const pdA = hasA ? data.per_distance_a : null;
  const pdB = hasB ? data.per_distance_b : null;

  const betaData = useMemo(() => {
    const src = pdA || pdB;
    if (!src?.distance) return [];
    const mapB = pdB ? new Map(pdB.distance.map((d, i) => [d, pdB.beta[i]])) : null;
    return src.distance.map((d, i) => ({
      distance: d,
      beta_a: pdA?.beta[i] ?? null,
      beta_b: mapB?.get(d) ?? null,
    }));
  }, [pdA, pdB]);

  const balanceData = useMemo(() => {
    if (!pdA?.balance) return [];
    return pdA.distance.map((d, i) => ({
      distance: d,
      balance_a: pdA.balance[i],
      balance_b: pdB?.balance?.[i] ?? null,
    }));
  }, [pdA, pdB]);

  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';
  const hasBalance = !!pdA?.balance;

  const geometry = t.slipAngleGeometry
    .replace('{wheelbase}', data.wheelbase_m?.toFixed(2))
    .replace('{ratio}', data.steer_ratio);

  return (
    <Panel icon="steering" title={t.slipAngleTitle} actions={<Badge>{t.slipAngleModel}</Badge>}>
      <p className={styles.desc}>
        {t.slipAngleDescription} <span className={styles.descMuted}>{geometry}</span>
      </p>

      <div className={styles.cards}>
        {hasA && <LapSummaryCard summary={data.summary_a} label={labelA} color={COLOR_A} />}
        {hasB && <LapSummaryCard summary={data.summary_b} label={labelB} color={COLOR_B} />}
      </div>

      {betaData.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>{t.slipAngleChassis}</span>
            <Legend items={[
              ...(hasA ? [{ label: labelA, color: COLOR_A }] : []),
              ...(hasB ? [{ label: labelB, color: COLOR_B }] : []),
            ]} />
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <ComposedChart data={betaData} margin={CHART_MARGIN}>
              <defs>
                <linearGradient id="betaGradA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLOR_A} stopOpacity={0.18} />
                  <stop offset="95%" stopColor={COLOR_A} stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} interval="preserveStartEnd" minTickGap={44} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} unit="°" width={40} domain={['auto', 'auto']} />
              <Tooltip content={tooltip} cursor={{ stroke: 'var(--line-strong)' }} />
              <ReferenceLine y={0} stroke={REF_ZERO} />
              {hasA && (
                <Area type="monotone" dataKey="beta_a" name={`β ${labelA}`} stroke={COLOR_A} strokeWidth={1.5}
                  fill="url(#betaGradA)" isAnimationActive={false} dot={false} connectNulls />
              )}
              {hasB && (
                <Line type="monotone" dataKey="beta_b" name={`β ${labelB}`} stroke={COLOR_B} strokeWidth={1.5}
                  isAnimationActive={false} dot={false} connectNulls />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {hasBalance && balanceData.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>{t.slipAngleBalance} (°)</span>
            <Legend items={[
              { label: labelA, color: COLOR_E },
              ...(hasB ? [{ label: labelB, color: COLOR_D }] : []),
            ]} />
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={balanceData} margin={CHART_MARGIN}>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} interval="preserveStartEnd" minTickGap={44} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} unit="°" width={40} domain={['auto', 'auto']} />
              <Tooltip content={tooltip} cursor={{ stroke: 'var(--line-strong)' }} />
              <ReferenceLine y={0} stroke={REF_ZERO} />
              <ReferenceLine y={2} stroke={COLOR_US} strokeOpacity={0.4} strokeDasharray="3 3" />
              <ReferenceLine y={-2} stroke={COLOR_OS} strokeOpacity={0.4} strokeDasharray="3 3" />
              <Area type="monotone" dataKey="balance_a" name={`Balance ${labelA}`} stroke={COLOR_E} strokeWidth={1.5}
                fill="transparent" isAnimationActive={false} dot={false} connectNulls />
              {hasB && (
                <Line type="monotone" dataKey="balance_b" name={`Balance ${labelB}`} stroke={COLOR_D} strokeWidth={1.25}
                  isAnimationActive={false} dot={false} connectNulls />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
};

export default SlipAngleChart;
