import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Stat, Badge, EmptyState, Icon } from './ui';
import css from './PitWindowWidget.module.css';

const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' };
const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');

const FuelTooltip = ({ active, payload, label, t }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className={css.tip}>
      <div className={css.tipHead}>{t.pitWindowLap(label)}</div>
      <div className={css.tipVal}>{payload[0]?.value?.toFixed(3)} L</div>
    </div>
  );
};

export default function PitWindowWidget({ combustible }) {
  const { t } = useLanguage();
  if (!combustible) return null;
  const title = clean(t.pitWindowTitle);

  if (!combustible.available) {
    return (
      <Panel icon="fuel" title={title}>
        <EmptyState icon="fuel">{t.pitWindowNoFuel}</EmptyState>
      </Panel>
    );
  }

  const { pit_window, combustible_actual_l, consumo_medio_l, consumo_std_l,
          vueltas_restantes_min, vueltas_restantes_max, fuel_per_lap } = combustible;

  const [open, close] = pit_window || [0, 0];
  const lapsLeft = vueltas_restantes_min;

  let tone = 'warn';
  let status = t.pitStatusPrepare;
  if (lapsLeft >= 5) { tone = 'ok'; status = t.pitStatusOk; }
  else if (lapsLeft <= 2) { tone = 'bad'; status = t.pitStatusBox; }

  const barData = (fuel_per_lap || []).map(r => ({
    lap: r.lap_number,
    burned: parseFloat(r.fuel_burned?.toFixed(3) ?? 0),
  }));

  const needsMoreLaps = (fuel_per_lap?.length ?? 0) < 3;
  const fmt = (v, d) => (v == null || isNaN(v) ? '—' : v.toFixed(d));

  return (
    <Panel
      icon="fuel"
      title={title}
      actions={<Badge>{t.pitFuelRemaining(combustible_actual_l)}</Badge>}
    >
      {needsMoreLaps ? (
        <div className={css.notice}>
          <Icon name="info" size={16} />
          <div>{t.pitWindowNeedMore}</div>
        </div>
      ) : (
        <div className={`${css.call} ${css[tone]}`} role="status">
          <div className={css.callMain}>
            <div className={css.callTitle}>
              {clean(t.pitWindowLabel)}
              <Badge tone={tone}>{status}</Badge>
            </div>
            <div className={css.callLaps}>{t.pitWindowLap(open)} – {t.pitWindowLap(close)}</div>
            <div className={css.callAction}>
              {t.pitPlanStop}
            </div>
          </div>
          <div className={css.callSide}>
            <span>{t.pitWindowLapsRange(vueltas_restantes_min, vueltas_restantes_max)}</span>
            <span>{fmt(consumo_medio_l, 3)} {t.pitFuelPerLapShort} ±{fmt(consumo_std_l, 3)}</span>
          </div>
        </div>
      )}

      {barData.length > 0 && (
        <>
          <div className={`ui-eyebrow ${css.sub}`}>{t.pitWindowConsumptionTitle} (L)</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={barData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeOpacity={0.6} vertical={false} />
              <XAxis dataKey="lap" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} />
              <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} tickFormatter={v => `${v}`} width={40} />
              <Tooltip content={<FuelTooltip t={t} />} cursor={{ fill: 'var(--surface-3)', fillOpacity: 0.5 }} />
              {consumo_medio_l != null && (
                <ReferenceLine y={consumo_medio_l} stroke="var(--ink-3)" strokeDasharray="4 4" />
              )}
              <Bar dataKey="burned" fill="var(--lap-d)" fillOpacity={0.8} radius={[2, 2, 0, 0]} maxBarSize={28} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}

      <div className={css.stats}>
        <Stat label={t.pitValueFuel} value={`${fmt(combustible_actual_l, 1)} L`} />
        <Stat label={t.pitValueConsumption} value={`${fmt(consumo_medio_l, 3)} L/v`} />
        <Stat label={t.pitValueStd} value={`±${fmt(consumo_std_l, 3)} L`} />
      </div>
    </Panel>
  );
}
