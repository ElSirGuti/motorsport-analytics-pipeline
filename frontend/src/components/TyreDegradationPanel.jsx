import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { Panel, Stat, Badge } from './ui';
import s from './RecPanels.module.css';

const wearTone = (pct) => (pct < 40 ? 'ok' : pct < 70 ? 'warn' : 'bad');
const TONE_VAR = { ok: 'var(--ok)', warn: 'var(--warn)', bad: 'var(--bad)' };
const AXIS = { fill: 'var(--ink-3)', fontSize: 11 };

const FACTOR_LABELS = {
  lap_number: 'Lap number',
  mean_lat_g: 'Mean lateral G',
  mean_brake_g: 'Mean braking G',
  mean_speed: 'Mean speed',
  temp_fl: 'Temp. FL', temp_fr: 'Temp. FR', temp_rl: 'Temp. RL', temp_rr: 'Temp. RR',
  stress_fl: 'Thermal stress FL', stress_fr: 'Thermal stress FR',
  stress_rl: 'Thermal stress RL', stress_rr: 'Thermal stress RR',
};

function WearGauge({ pct }) {
  const color = TONE_VAR[wearTone(pct)];
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className={s.gauge}>
      <svg width={130} height={78} viewBox="0 0 130 78" role="img" aria-label={`Tyre wear ${Math.round(clamped)}%`}>
        <path d="M 13 65 A 52 52 0 0 1 117 65" fill="none" stroke="var(--surface-3)" strokeWidth={10} strokeLinecap="round" />
        <path
          d="M 13 65 A 52 52 0 0 1 117 65" fill="none" stroke={color} strokeWidth={10} strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * 163} 163`}
        />
        <text x={65} y={62} textAnchor="middle" fill="var(--ink-1)" fontSize={22} fontWeight={600} fontFamily="var(--font-mono)">
          {Math.round(clamped)}%
        </text>
      </svg>
      <span className={s.gaugeLbl}>Current wear</span>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={s.tip}>
      <div className={s.tipHead}>Lap {label}</div>
      {payload.map((p, i) => (
        <div key={i} className={s.tipRow}>
          <span style={{ color: p.color }}>{p.name}</span>
          <strong className={s.mono}>{p.value != null ? `${p.value > 0 ? '+' : ''}${p.value.toFixed(3)} s` : '—'}</strong>
        </div>
      ))}
    </div>
  );
}

function TrendCard({ label, value, warn, sub }) {
  return (
    <div className={s.card} style={{ gap: 4 }}>
      <span className={s.metricLbl}>{label}</span>
      <span className={s.metricVal} style={{ color: warn ? 'var(--warn)' : undefined }}>{value}</span>
      <span className={s.cardSub}>{sub}</span>
    </div>
  );
}

export default function TyreDegradationPanel({ data }) {
  if (!data?.available) return null;

  const {
    wear_pct, remaining_laps, current_delta_s, cliff_threshold_s,
    degradation_rate_s_per_lap, n_laps_analyzed,
    top_wear_factors, lap_data = [], projection = [],
    front_temp_trend_c_per_lap, rear_temp_trend_c_per_lap,
    left_mean_temp, right_mean_temp, tyre_temps_available,
  } = data;

  const wearColor = TONE_VAR[wearTone(wear_pct)];
  const chartData = [
    ...lap_data.map(d => ({ lap: d.lap, actual: d.delta, trend: d.trend })),
    ...projection.map(d => ({ lap: d.lap, projected: d.projected, cliff: d.cliff })),
  ];

  const rateSign = degradation_rate_s_per_lap > 0 ? '+' : '';
  const remainingNum = typeof remaining_laps === 'number';
  const remainingTone = remainingNum ? (remaining_laps < 5 ? 'bad' : remaining_laps < 15 ? 'warn' : 'ok') : 'ok';
  const remainingLabel = remainingNum ? `${remaining_laps} laps` : remaining_laps;

  const deltaTone = current_delta_s > 0.5 ? 'bad' : current_delta_s > 0.15 ? 'warn' : 'ok';
  const rateTone = degradation_rate_s_per_lap > 0.04 ? 'bad' : degradation_rate_s_per_lap > 0.015 ? 'warn' : 'ok';

  const pit = {
    bad:  { tone: 'bad',  text: 'Box window is open. Plan the stop now.' },
    warn: { tone: 'warn', text: 'Approaching the performance cliff. Prepare the pit stop.' },
    ok:   { tone: 'ok',   text: 'Tyres are within the working window. No stop required yet.' },
  }[remainingTone];

  return (
    <Panel
      icon="tyre"
      title="Tyre Degradation & Pit Strategy"
      subtitle={`Ridge polynomial regression · ${n_laps_analyzed} laps analyzed`}
      actions={<Badge>Ridge + Poly(2)</Badge>}
    >
      <div className={`${s.alert} ${s[pit.tone]}`} role="status" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <Badge tone={pit.tone}>{remainingNum ? `${remaining_laps} LAPS LEFT` : 'STINT'}</Badge>
        <span>{pit.text}</span>
      </div>

      <div className={s.pitBar}>
        <WearGauge pct={wear_pct} />
        <div className={s.kpis} style={{ flex: 1, minWidth: 260 }}>
          <Stat label="Remaining" value={remainingLabel} tone={remainingTone} hint="before cliff" />
          <Stat label="Δ vs best" value={`${current_delta_s > 0 ? '+' : ''}${current_delta_s.toFixed(3)} s`} tone={deltaTone} />
          <Stat label="Degradation" value={`${rateSign}${degradation_rate_s_per_lap.toFixed(4)}`} tone={rateTone} hint="s / lap" />
          <Stat label="Cliff" value={`+${cliff_threshold_s.toFixed(1)} s`} hint="threshold" />
        </div>
      </div>

      <div className={s.chartBox}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 24, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="lap" tick={AXIS} axisLine={{ stroke: 'var(--line-strong)' }} tickLine={false}
              label={{ value: 'Lap', position: 'insideBottom', offset: -2, fill: 'var(--ink-3)', fontSize: 11 }}
            />
            <YAxis
              tick={AXIS} axisLine={false} tickLine={false} width={64}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)} s`}
            />
            <ReferenceLine y={cliff_threshold_s} stroke="var(--bad)" strokeDasharray="4 3" strokeOpacity={0.6}
              label={{ value: 'Cliff', fill: 'var(--bad)', fontSize: 11, position: 'right' }} />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <Tooltip content={<ChartTooltip />} />
            <Line dataKey="actual" name="Δ actual" stroke={wearColor} strokeWidth={2} dot={{ r: 3, fill: wearColor }} connectNulls={false} />
            <Line dataKey="trend" name="Trend" stroke="var(--accent)" strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls={false} />
            <Line dataKey="projected" name="Projection" stroke="var(--warn)" strokeWidth={1.5} strokeDasharray="2 3" dot={false} connectNulls={false} />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 11, color: 'var(--ink-3)', paddingTop: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {tyre_temps_available && (
        <div className={s.section}>
          <div className={s.sectionHead}><span className={s.sectionTitle}>Thermal trends</span></div>
          <div className={s.cards} style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))' }}>
            {front_temp_trend_c_per_lap != null && (
              <TrendCard label="Front axle" sub="thermal trend" warn={Math.abs(front_temp_trend_c_per_lap) > 1.5}
                value={`${front_temp_trend_c_per_lap > 0 ? '+' : ''}${front_temp_trend_c_per_lap.toFixed(2)} °C/lap`} />
            )}
            {rear_temp_trend_c_per_lap != null && (
              <TrendCard label="Rear axle" sub="thermal trend" warn={Math.abs(rear_temp_trend_c_per_lap) > 1.5}
                value={`${rear_temp_trend_c_per_lap > 0 ? '+' : ''}${rear_temp_trend_c_per_lap.toFixed(2)} °C/lap`} />
            )}
            {left_mean_temp != null && right_mean_temp != null && (
              <TrendCard label="L/R asymmetry" warn={Math.abs(left_mean_temp - right_mean_temp) > 8}
                value={`${Math.abs(left_mean_temp - right_mean_temp).toFixed(1)} °C`}
                sub={`L ${left_mean_temp.toFixed(0)} °C · R ${right_mean_temp.toFixed(0)} °C`} />
            )}
          </div>
        </div>
      )}

      {top_wear_factors?.length > 0 && (
        <div className={s.section}>
          <div className={s.sectionHead}><span className={s.sectionTitle}>Wear factors (correlation with degradation)</span></div>
          <div className={s.stack} style={{ gap: 8 }}>
            {top_wear_factors.map((f, i) => (
              <div key={i} className={s.factor}>
                <span>{FACTOR_LABELS[f.factor] || f.factor}</span>
                <div className={s.factorTrack}>
                  <div className={s.factorFill} style={{ width: `${Math.min(100, f.correlation * 100)}%`, opacity: i === 0 ? 1 : 0.7 }} />
                </div>
                <span className={s.factorPct}>{(f.correlation * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className={s.note}>
        Prediction based on polynomial regression over current session data. Accuracy improves with more laps. The cliff threshold is a conservative estimate; actual results depend on external factors (track temperature, compound, pressures).
      </p>
    </Panel>
  );
}
