import { useMemo } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import styles from './Analysis.module.css';
import {
  COLOR_A, COLOR_B, AXIS_TICK, AXIS_LINE, GRID_PROPS,
  CHART_MARGIN, fmtDist, makeTooltip, Legend,
} from './analysisKit';

const tooltip = makeTooltip((v) => `${v.toFixed(3)} g/%`);

const FadeZoneList = ({ zones, color, label }) => {
  const { t } = useLanguage();
  if (!zones?.length) return null;
  return (
    <div className={styles.group}>
      <div className={styles.groupLabel}>
        <Icon name="alert" size={13} style={{ color: 'var(--warn)' }} />
        <span style={{ color }}>{label}</span>
      </div>
      <div className={styles.chips}>
        {zones.map((z, i) => (
          <span key={i} className={styles.chip}>
            {z.start.toFixed(0)}–{z.end.toFixed(0)} m
            <span className={styles.chipMute}>{t.brakeFadeDrop((z.severity * 100).toFixed(0))}</span>
          </span>
        ))}
      </div>
    </div>
  );
};

const ScoreCard = ({ score, baseline, label, color }) => {
  const { t } = useLanguage();
  if (score == null) return null;
  const ratio = baseline > 0 ? score / baseline : 1;
  const pct = (ratio * 100).toFixed(0);
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <span className={styles.lapName}><span className={styles.swatch} style={{ background: color }} />{label}</span>
        {baseline > 0 && <Badge tone={ratio < 0.85 ? 'bad' : 'ok'}>{pct}%</Badge>}
      </div>
      <div className={styles.mValue} style={{ fontSize: 'var(--fs-xl)' }}>
        {score.toFixed(3)}<span className={styles.mUnit}>g/%</span>
      </div>
      {baseline > 0 && (
        <div className={styles.sub} style={{ color: ratio < 0.85 ? 'var(--bad)' : 'var(--ok)', marginTop: 4 }}>
          {t.brakeFadeBaseline(pct)}
        </div>
      )}
    </div>
  );
};

const BrakeFadeChart = ({ brake_analysis, metadata }) => {
  const { t } = useLanguage();
  const data = brake_analysis;

  const chartData = useMemo(() => {
    const pd = data?.per_distance;
    if (!pd?.distance) return [];
    return pd.distance.map((d, i) => ({
      distance: d,
      eff_a: pd.efficiency_a?.[i] ?? null,
      eff_b: pd.efficiency_b?.[i] ?? null,
    }));
  }, [data]);

  if (!data?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';
  const hasA = data.available_a;
  const hasB = data.available_b;

  return (
    <Panel icon="gauge" title={t.brakeFadeTitle} actions={<Badge>{t.brakeFadeBadge}</Badge>}>
      <p className={styles.desc}>{t.brakeFadeDescription}</p>

      <div className={styles.cards}>
        {hasA && <ScoreCard score={data.score_a} baseline={data.baseline_a} label={labelA} color={COLOR_A} />}
        {hasB && <ScoreCard score={data.score_b} baseline={data.baseline_b} label={labelB} color={COLOR_B} />}
      </div>

      {chartData.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>{t.brakeFadeTitle} (g/%)</span>
            <Legend items={[
              ...(hasA ? [{ label: labelA, color: COLOR_A }] : []),
              ...(hasB ? [{ label: labelB, color: COLOR_B }] : []),
              ...(hasA && data.baseline_a > 0 ? [{ label: t.baselineLabel, color: '#6f7a8a', dashed: true }] : []),
            ]} />
          </div>
          <ResponsiveContainer width="100%" height={210}>
            <ComposedChart data={chartData} margin={CHART_MARGIN}>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} domain={[0, 'auto']} width={44} />
              <Tooltip content={tooltip} cursor={{ stroke: '#323b48' }} />
              {hasA && data.baseline_a > 0 && (
                <ReferenceLine y={data.baseline_a} stroke={COLOR_A} strokeDasharray="4 3" strokeOpacity={0.5} />
              )}
              {hasB && data.baseline_b > 0 && (
                <ReferenceLine y={data.baseline_b} stroke={COLOR_B} strokeDasharray="4 3" strokeOpacity={0.5} />
              )}
              {data.fade_zones_a?.map((z, i) => (
                <Area key={`fade_a_${i}`}
                  data={chartData.filter((d) => d.distance >= z.start && d.distance <= z.end)}
                  type="monotone" dataKey="eff_a" stroke="none" fill="rgba(240,97,109,0.18)"
                  isAnimationActive={false} legendType="none" tooltipType="none" />
              ))}
              {hasA && (
                <Line type="monotone" dataKey="eff_a" name={labelA} stroke={COLOR_A} strokeWidth={1.5}
                  dot={false} isAnimationActive={false} connectNulls={false} />
              )}
              {hasB && (
                <Line type="monotone" dataKey="eff_b" name={labelB} stroke={COLOR_B} strokeWidth={1.5}
                  dot={false} isAnimationActive={false} connectNulls={false} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <FadeZoneList zones={data.fade_zones_a} color={COLOR_A} label={t.brakeFadeZones(labelA)} />
      <FadeZoneList zones={data.fade_zones_b} color={COLOR_B} label={t.brakeFadeZones(labelB)} />
    </Panel>
  );
};

export default BrakeFadeChart;
