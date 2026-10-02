import { Panel, Badge, Icon } from './ui';
import s from './RecPanels.module.css';

const PRIORITY_TONE = { alta: 'bad', media: 'warn', baja: 'ok', nominal: undefined };
const PRIORITY_CLS = { alta: 'high', media: 'med', baja: 'low', nominal: 'nom' };
const PRIORITY_LABEL = { alta: 'HIGH', media: 'MEDIUM', baja: 'LOW', nominal: 'NOMINAL' };

const STATUS_TONE = {
  critical: 'bad', critical_brake: 'bad',
  warning: 'warn', low_delta: 'warn', high_delta: 'warn', suboptimal: 'warn', hot: 'warn',
  too_cold: 'accent',
  normal: 'ok', ok: 'ok', optimal: 'ok',
};
const VALUE_COLOR = { bad: 'var(--bad)', warn: 'var(--warn)', ok: 'var(--ok)', accent: 'var(--accent)' };

const CORNER_LABELS = { FL: 'Front Left', FR: 'Front Right', RL: 'Rear Left', RR: 'Rear Right' };

const statusText = (status) => String(status ?? '').replace(/_/g, ' ').toUpperCase();

function StatusBadge({ status, label }) {
  return <Badge tone={STATUS_TONE[status]}>{label ?? statusText(status)}</Badge>;
}

function Metric({ label, value, sub, color }) {
  return (
    <div className={s.metric}>
      <span className={s.metricLbl}>{label}</span>
      <span className={s.metricVal} style={color ? { color } : undefined}>{value}</span>
      {sub && <span className={s.metricSub}>{sub}</span>}
    </div>
  );
}

function RecCard({ rec, showCorner = false }) {
  const prio = rec.priority in PRIORITY_CLS ? rec.priority : 'baja';
  return (
    <div className={`${s.rec} ${s[PRIORITY_CLS[prio]]}`}>
      <div className={`${s.recHead} ${s.recStatic}`}>
        <div className={s.recMain}>
          <div className={s.recMeta}>
            <Badge tone={PRIORITY_TONE[prio]}>{PRIORITY_LABEL[prio]}</Badge>
            {showCorner && rec.corner && <span className={s.recCat}>{CORNER_LABELS[rec.corner] ?? rec.corner}</span>}
          </div>
          <p className={s.recText}>{rec.reason || rec.action}</p>
        </div>
        {rec.target_cold && (
          <div className={s.recGain}>
            <div className={s.recGainVal}>{rec.target_cold.bar} bar</div>
            <div className={s.recGainLbl}>
              {rec.target_cold.psi} PSI cold ({rec.direction === 'lower' ? '−' : '+'}{rec.delta_bar} bar)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon, children }) {
  return (
    <div className={s.section}>
      <div className={s.sectionHead}>
        {icon && <Icon name={icon} size={14} className="ui-panel__icon" />}
        <span className={s.sectionTitle}>{title}</span>
      </div>
      {children}
    </div>
  );
}

function FluidSection({ data, label }) {
  if (!data?.available) return null;
  const trendSign = data.trend_c_per_lap > 0 ? '+' : '';
  const tone = STATUS_TONE[data.status];
  return (
    <Section title={label} icon="thermometer">
      <div className={s.card}>
        <div className={s.cardHead}>
          <StatusBadge status={data.status} />
          {data.trend_c_per_lap != null && (
            <span className={`${s.mono} ${s.cardSub}`}>{trendSign}{data.trend_c_per_lap} °C / lap</span>
          )}
        </div>
        <div className={s.metrics}>
          <Metric label="Mean" value={`${data.mean_c} °C`} />
          <Metric label="Peak" value={`${data.max_c} °C`} color={VALUE_COLOR[tone]} />
          <Metric label="Warn at" value={`${data.warn_threshold_c} °C`} />
        </div>
        {data.alert && <div className={`${s.alert} ${tone ? s[tone] : ''}`}>{data.alert}</div>}
      </div>
    </Section>
  );
}

function BrakeTempSection({ data }) {
  if (!data?.available) return null;
  return (
    <Section title="Brake temperatures" icon="gauge">
      <div className={s.cards2} style={{ marginBottom: 12 }}>
        {Object.entries(data.corners).map(([corner, c]) => (
          <div key={corner} className={s.card}>
            <div className={s.cardHead}>
              <span className={s.cardTitle}>{CORNER_LABELS[corner] ?? corner}</span>
              <StatusBadge status={c.status} />
            </div>
            <div className={s.metrics}>
              <Metric label="Mean" value={`${c.mean_c} °C`} color={VALUE_COLOR[STATUS_TONE[c.status]]} />
              <Metric label="Peak" value={`${c.max_c} °C`} />
            </div>
          </div>
        ))}
      </div>

      {data.balance && (
        <p className={s.cardSub} style={{ marginBottom: 12 }}>
          F/R thermal balance: <span className={s.mono}>{data.balance.front_mean_c} °C</span> front vs{' '}
          <span className={s.mono}>{data.balance.rear_mean_c} °C</span> rear
          {data.balance.ratio_f_r && <span> (ratio <span className={s.mono}>{data.balance.ratio_f_r}</span>)</span>}
        </p>
      )}

      {data.duct_recs?.length > 0 && (
        <>
          <h4 className={s.sub}>Duct recommendations</h4>
          <div className={s.stack}>
            {data.duct_recs.map((rec, i) => <RecCard key={i} rec={rec} showCorner />)}
          </div>
        </>
      )}

      <p className={s.note}>Optimal window: <span className={s.mono}>{data.optimal_range_c?.[0]}–{data.optimal_range_c?.[1]} °C</span></p>
    </Section>
  );
}

function TyrePressureSection({ data }) {
  if (!data?.available) return null;
  const hasRecs = data.recommendations?.length > 0;
  return (
    <Section title="Tyre pressures" icon="tyre">
      <div className={s.cards2} style={{ marginBottom: hasRecs ? 16 : 0 }}>
        {Object.entries(data.corners).map(([corner, c]) => {
          const tone = STATUS_TONE[c.status] ?? 'ok';
          return (
            <div key={corner} className={s.card}>
              <div className={s.cardHead}>
                <span className={s.cardTitle}>{CORNER_LABELS[corner] ?? corner}</span>
                {c.status !== 'ok' && <StatusBadge status={c.status} />}
              </div>
              <div className={s.metrics}>
                <Metric label="Hot" value={`${c.hot?.bar} bar`} sub={`${c.hot?.psi} PSI`} />
                {c.cold && <Metric label="Cold" value={`${c.cold.bar} bar`} sub={`${c.cold.psi} PSI`} />}
                {c.delta && (
                  <Metric label="Δ hot-cold" value={`${c.delta.bar} bar`} sub={`${c.delta.psi} PSI`} color={tone === 'ok' ? undefined : VALUE_COLOR[tone]} />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {hasRecs && (
        <>
          <h4 className={s.sub}>Pressure recommendations</h4>
          <div className={s.stack}>
            {data.recommendations.map((rec, i) => <RecCard key={i} rec={rec} showCorner />)}
          </div>
        </>
      )}

      <p className={s.note}>
        Target hot-cold delta: <span className={s.mono}>{data.delta_target?.bar} bar ({data.delta_target?.psi} PSI)</span>
        {' · '}Window: <span className={s.mono}>{data.delta_window?.low?.bar}–{data.delta_window?.high?.bar} bar</span>
      </p>
    </Section>
  );
}

function BrakeBiasSection({ data }) {
  if (!data?.available) return null;
  const prio = data.recommendation?.priority in PRIORITY_CLS ? data.recommendation.priority : 'low';
  const markCls = data.recommendation ? s[PRIORITY_CLS[prio]] ?? '' : s.low;
  const lo = data.typical_range?.[0] ?? 50;
  const hi = data.typical_range?.[1] ?? 65;
  const pos = (v) => `${Math.min(100, Math.max(0, ((v - 45) / 25) * 100))}%`;
  return (
    <Section title="Brake bias" icon="gauge">
      <div className={s.biasRow} style={{ marginBottom: data.recommendation || data.out_of_range ? 12 : 0 }}>
        <div className={s.metric}>
          <span className={s.metricLbl}>Current (front)</span>
          <span className={s.biasVal}>{data.current_pct}%</span>
        </div>
        <div className={s.biasBar}>
          <div className={s.metricLbl} style={{ marginBottom: 6 }}>Typical range</div>
          <div className={s.bar} role="img" aria-label={`Brake bias ${data.current_pct}%, typical ${lo} to ${hi}%`}>
            <div className={s.barRange} style={{ left: pos(lo), width: `${((hi - lo) / 25) * 100}%` }} />
            <div className={`${s.barMark} ${markCls}`} style={{ left: pos(data.current_pct) }} />
          </div>
          <div className={s.barScale}><span>45%</span><span>70%</span></div>
        </div>
      </div>

      {data.out_of_range && <div className={`${s.alert} ${s.warn}`} style={{ marginBottom: 8 }}>{data.out_of_range}</div>}
      {data.recommendation && <RecCard rec={data.recommendation} />}
    </Section>
  );
}

export default function ThermalManagementPanel({ thermal_analysis }) {
  const data = thermal_analysis;
  if (!data?.available) return null;

  const totalRecs = data.n_recommendations ?? 0;

  return (
    <Panel
      icon="thermometer"
      title="Thermal Management"
      subtitle="Engine fluids · brake temperatures · tyre pressures · brake bias"
      actions={totalRecs > 0 ? <Badge tone="warn">{totalRecs} recommendation{totalRecs !== 1 ? 's' : ''}</Badge> : <Badge tone="ok">No actions</Badge>}
    >
      <FluidSection data={data.water_temp} label="Water temperature" />
      <FluidSection data={data.oil_temp} label="Oil temperature" />
      <BrakeTempSection data={data.brake_temps} />
      <TyrePressureSection data={data.tyre_pressure} />
      <BrakeBiasSection data={data.brake_bias} />
    </Panel>
  );
}
