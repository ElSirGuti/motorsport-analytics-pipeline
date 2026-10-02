import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import styles from './Analysis.module.css';
import {
  COLOR_A, COLOR_B, COLOR_C, COLOR_D, AXIS_TICK, AXIS_LINE, GRID_PROPS,
  CHART_MARGIN, fmtDist, makeTooltip, Legend,
} from './analysisKit';

const tooltip = makeTooltip((v) => `${(v * 100).toFixed(1)}%`);

const BandBar = ({ label, value, color }) => {
  if (value == null) return null;
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className={styles.bandRow}>
      <div className={styles.bandHead}>
        <span>{label}</span>
        <span>{(value * 100).toFixed(1)}%</span>
      </div>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
};

const PilotCard = ({ scoreKey, labelKey, bandsKey, overlapKey, data, lapLabel, lapColor }) => {
  const { t } = useLanguage();
  const score = data[scoreKey];
  const lbl = data[labelKey];
  const bands = data[bandsKey];
  const overlap = data[overlapKey];
  if (score == null) return null;

  const TONES = {
    [t.driverInputsVerySmooth]: { tone: 'ok', color: 'var(--ok)' },
    [t.driverInputsSmooth]: { tone: 'ok', color: 'var(--ok)' },
    [t.driverInputsNormal]: { tone: 'accent', color: 'var(--accent)' },
    [t.driverInputsActive]: { tone: 'warn', color: 'var(--warn)' },
    [t.driverInputsNervous]: { tone: 'bad', color: 'var(--bad)' },
  };
  const style = TONES[lbl] || { tone: undefined, color: 'var(--ink-1)' };

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <span className={styles.lapName}><span className={styles.swatch} style={{ background: lapColor }} />{lapLabel}</span>
        <Badge tone={style.tone}>{lbl || '—'}</Badge>
      </div>
      <div className={styles.mValue} style={{ fontSize: 'var(--fs-xl)', color: style.color, marginBottom: 10 }}>
        {(score * 100).toFixed(1)}%
        <span className={styles.mUnit}>{t.driverInputsNervousness}</span>
      </div>
      {bands && (
        <div style={{ marginBottom: 8 }}>
          <BandBar label={t.driverInputsLowFreq} value={bands.low} color={COLOR_C} />
          <BandBar label={t.driverInputsMidFreq} value={bands.mid} color={COLOR_D} />
          <BandBar label={t.driverInputsHighFreq} value={bands.high} color="#f0616d" />
        </div>
      )}
      {overlap != null && (
        <div className={styles.sub} style={{ color: overlap > 5 ? 'var(--warn)' : undefined }}>
          {t.driverInputsOverlap(overlap)}
        </div>
      )}
    </div>
  );
};

const DriverInputsChart = ({ driver_inputs, metadata }) => {
  const { t } = useLanguage();
  const data = driver_inputs;

  const chartData = useMemo(() => {
    const pd = data?.per_distance;
    if (!pd?.distance) return [];
    return pd.distance.map((d, i) => ({
      distance: d,
      nerv_a: pd.nervousness_a?.[i] ?? null,
      nerv_b: pd.nervousness_b?.[i] ?? null,
    }));
  }, [data]);

  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';

  return (
    <Panel icon="steering" title={t.driverInputsTitle} actions={<Badge>{t.driverInputsFFT}</Badge>}>
      <p className={styles.desc}>{t.driverInputsDescription}</p>

      <div className={styles.cards}>
        <PilotCard scoreKey="nervousness_score_a" labelKey="nervousness_label_a" bandsKey="fft_bands_a"
          overlapKey="overlap_pct_a" data={data} lapLabel={labelA} lapColor={COLOR_A} />
        <PilotCard scoreKey="nervousness_score_b" labelKey="nervousness_label_b" bandsKey="fft_bands_b"
          overlapKey="overlap_pct_b" data={data} lapLabel={labelB} lapColor={COLOR_B} />
      </div>

      {chartData.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>{t.driverInputsNervousness} (%)</span>
            <Legend items={[
              ...(data.available_a ? [{ label: labelA, color: COLOR_A }] : []),
              ...(data.available_b ? [{ label: labelB, color: COLOR_B }] : []),
            ]} />
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <AreaChart data={chartData} margin={CHART_MARGIN}>
              <defs>
                <linearGradient id="nervGradA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLOR_A} stopOpacity={0.22} />
                  <stop offset="95%" stopColor={COLOR_A} stopOpacity={0.01} />
                </linearGradient>
                <linearGradient id="nervGradB" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLOR_B} stopOpacity={0.22} />
                  <stop offset="95%" stopColor={COLOR_B} stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} />
              <YAxis domain={[0, 1]} tick={AXIS_TICK} axisLine={false} tickLine={false}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={44} />
              <Tooltip content={tooltip} cursor={{ stroke: '#323b48' }} />
              {data.available_a && (
                <Area type="monotone" dataKey="nerv_a" name={labelA} stroke={COLOR_A} strokeWidth={1.5}
                  fill="url(#nervGradA)" isAnimationActive={false} dot={false} connectNulls />
              )}
              {data.available_b && (
                <Area type="monotone" dataKey="nerv_b" name={labelB} stroke={COLOR_B} strokeWidth={1.5}
                  fill="url(#nervGradB)" isAnimationActive={false} dot={false} connectNulls />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
};

export default DriverInputsChart;
