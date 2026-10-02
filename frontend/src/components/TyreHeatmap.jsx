import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import styles from './Analysis.module.css';
import {
  COLOR_A, COLOR_B, COLOR_C, COLOR_D, AXIS_TICK, AXIS_LINE, GRID_PROPS,
  CHART_MARGIN, fmtDist, makeTooltip, Legend,
} from './analysisKit';

const CORNERS = ['FL', 'FR', 'RL', 'RR'];

const STATUS_TONE = {
  fria: 'accent',
  suboptima: 'accent',
  optima: 'ok',
  caliente: 'warn',
  sobrecalentada: 'bad',
  desconocida: undefined,
};
const STATUS_COLOR = {
  fria: 'var(--accent)',
  suboptima: 'var(--accent)',
  optima: 'var(--ok)',
  caliente: 'var(--warn)',
  sobrecalentada: 'var(--bad)',
  desconocida: 'var(--ink-3)',
};

const CORNER_COLORS = { FL: COLOR_A, FR: COLOR_B, RL: COLOR_D, RR: COLOR_C };

const statusToKey = (s) => ({
  fria: 'tyreCold',
  suboptima: 'tyreSuboptimal',
  optima: 'tyreOptimal',
  caliente: 'tyreHot',
  sobrecalentada: 'tyreOverheated',
  desconocida: 'tyreUnknown',
}[s] || 'tyreUnknown');

const cornerLabelKey = (corner) => ({
  FL: 'tyreFL', FR: 'tyreFR', RL: 'tyreRL', RR: 'tyreRR',
}[corner] || 'tyreUnknown');

const tooltip = makeTooltip((v) => `${v.toFixed(1)} °C`);

const CornerCard = ({ corner, data, t }) => {
  if (!data) return null;
  const status = data.window_status || 'desconocida';
  const color = STATUS_COLOR[status] || STATUS_COLOR.desconocida;
  const { surface_mean: surface, core_mean: core, delta_t_mean: delta, window_deviation: dev, high_stress_pct: stress } = data;

  return (
    <div className={styles.card} style={{ borderTop: `2px solid ${color}` }}>
      <div className={styles.cardHead}>
        <span className={styles.lapName}>{t[cornerLabelKey(corner)]}</span>
        <Badge tone={STATUS_TONE[status]}>{t[statusToKey(status)]}</Badge>
      </div>
      <div className={styles.tyreVal} style={{ color }}>
        {surface != null ? surface.toFixed(0) : '—'}<span className={styles.mUnit}>°C</span>
      </div>
      <div className={styles.sub}>
        {core != null && <div>{t.tyreCore} {core.toFixed(0)} °C</div>}
        {delta != null && <div>ΔT {delta > 0 ? '+' : ''}{delta.toFixed(1)} °C</div>}
        {dev != null && dev !== 0 && (
          <div style={{ color: dev > 0 ? 'var(--warn)' : 'var(--accent)' }}>
            {dev > 0 ? t.tyreAbove(dev) : t.tyreBelow(Math.abs(dev))}
          </div>
        )}
        {stress > 0 && <div style={{ color: 'var(--bad)' }}>{t.tyreStress} {stress.toFixed(0)}%</div>}
      </div>
    </div>
  );
};

const LapGroup = ({ lap, label, color, t }) => {
  if (!lap?.available) return null;
  return (
    <div>
      <div className={styles.lapGroupTitle}>
        <span className={styles.swatch} style={{ background: color }} />{label}
      </div>
      <div className={styles.tyreGrid}>
        {lap.corners?.map((c) => <CornerCard key={c.corner} corner={c.corner} data={c} t={t} />)}
      </div>
    </div>
  );
};

const TyreHeatmap = ({ tyre_analysis, metadata }) => {
  const { t } = useLanguage();
  const lap = tyre_analysis;
  const lapA = lap?.lap_a;
  const lapB = lap?.lap_b;
  const active = lapA?.available ? lapA : lapB;

  const distSeries = useMemo(() => {
    const src = active?.per_distance;
    if (!src?.distance) return [];
    return src.distance.map((d, i) => {
      const row = { distance: d };
      CORNERS.forEach((c) => {
        if (src[`${c}_surface`]) row[`${c}_s`] = src[`${c}_surface`][i];
        if (src[`${c}_core`]) row[`${c}_c`] = src[`${c}_core`][i];
      });
      return row;
    });
  }, [active]);

  if (!lap?.available) return null;

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';
  const t_min = lap.t_min ?? 80;
  const t_max = lap.t_max ?? 100;

  return (
    <Panel icon="tyre" title={t.tyreTitle} actions={<Badge tone="accent">{t.tyreWindow(t_min, t_max)}</Badge>}>
      <LapGroup lap={lapA} label={labelA} color={COLOR_A} t={t} />
      <LapGroup lap={lapB} label={labelB} color={COLOR_B} t={t} />

      {distSeries.length > 0 && (
        <div className={styles.chartBox}>
          <div className={styles.chartTitle}>
            <span className={styles.chartLabel}>{t.tyreSurface} (°C)</span>
            <Legend items={CORNERS.map((c) => ({ label: t[cornerLabelKey(c)], color: CORNER_COLORS[c] }))} />
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={distSeries} margin={CHART_MARGIN}>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="distance" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={fmtDist} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} unit=" °C" width={52} domain={['auto', 'auto']} />
              <Tooltip content={tooltip} cursor={{ stroke: '#323b48' }} />
              <ReferenceLine y={t_min} stroke="#4da3ff" strokeOpacity={0.45} strokeDasharray="4 3"
                label={{ value: `${t_min}°`, position: 'insideBottomLeft', fontSize: 10, fill: '#4da3ff' }} />
              <ReferenceLine y={t_max} stroke="#f5a524" strokeOpacity={0.45} strokeDasharray="4 3"
                label={{ value: `${t_max}°`, position: 'insideTopLeft', fontSize: 10, fill: '#f5a524' }} />
              {CORNERS.map((c) => (
                <Line key={c} type="monotone" dataKey={`${c}_s`} name={t[cornerLabelKey(c)]}
                  stroke={CORNER_COLORS[c]} strokeWidth={1.5} dot={false}
                  isAnimationActive={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
};

export default TyreHeatmap;
