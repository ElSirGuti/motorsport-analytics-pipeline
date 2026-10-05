import { useMemo, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend } from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import css from './IncidentsPanel.module.css';

const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' };
const KIND_TONE = { spin: 'bad', slide: 'warn', off_track: 'warn' };
const SEV_TONE = { minor: 'ok', moderate: 'warn', major: 'bad' };

const traceRows = (trace) => (trace?.t || []).map((t, i) => ({
  t,
  throttle: trace.throttle?.[i],
  brake: trace.brake?.[i],
  steer: trace.steer?.[i],
  speed: trace.speed?.[i],
  slip: trace.slip?.[i],
}));

function InputsChart({ rows, t }) {
  const hasSteer = rows.some((r) => r.steer != null);
  return (
    <ResponsiveContainer width="100%" height={170}>
      <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={AXIS_TICK} tickFormatter={(v) => `${v}s`} />
        <YAxis yAxisId="pct" domain={[0, 100]} tick={AXIS_TICK} width={34} />
        {hasSteer && <YAxis yAxisId="deg" orientation="right" tick={AXIS_TICK} width={40} />}
        <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', fontSize: 12 }} labelFormatter={(v) => `${v}s`} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <ReferenceLine yAxisId="pct" x={0} stroke="var(--bad)" strokeDasharray="4 3" />
        <Line yAxisId="pct" type="monotone" dataKey="throttle" name={t.incThrottle} stroke="var(--ok)" dot={false} strokeWidth={1.8} isAnimationActive={false} />
        <Line yAxisId="pct" type="monotone" dataKey="brake" name={t.incBrake} stroke="var(--bad)" dot={false} strokeWidth={1.8} isAnimationActive={false} />
        {hasSteer && <Line yAxisId="deg" type="monotone" dataKey="steer" name={t.incSteer} stroke="var(--accent)" dot={false} strokeWidth={1.6} isAnimationActive={false} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

function SpeedChart({ rows, t }) {
  const hasSlip = rows.some((r) => r.slip != null);
  return (
    <ResponsiveContainer width="100%" height={170}>
      <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={AXIS_TICK} tickFormatter={(v) => `${v}s`} />
        <YAxis yAxisId="spd" tick={AXIS_TICK} width={38} />
        {hasSlip && <YAxis yAxisId="slip" orientation="right" tick={AXIS_TICK} width={40} />}
        <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', fontSize: 12 }} labelFormatter={(v) => `${v}s`} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <ReferenceLine yAxisId="spd" x={0} stroke="var(--bad)" strokeDasharray="4 3" />
        <Line yAxisId="spd" type="monotone" dataKey="speed" name={t.incSpeed} stroke="var(--lap-a)" dot={false} strokeWidth={1.8} isAnimationActive={false} />
        {hasSlip && <Line yAxisId="slip" type="monotone" dataKey="slip" name={t.incSlip} stroke="var(--warn)" dot={false} strokeWidth={1.6} isAnimationActive={false} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

function Event({ ev, open, onToggle, t }) {
  const rows = useMemo(() => traceRows(ev.trace), [ev.trace]);
  const [main, ...others] = ev.causes || [];
  const place = ev.corner?.corner_name
    || (ev.corner?.corner_number != null ? `T${ev.corner.corner_number}` : t.incAtDistance(ev.distance_m));
  return (
    <div className={css.card} data-testid="incident-card">
      <button type="button" className={css.cardHead} onClick={onToggle} aria-expanded={open}>
        <Badge tone={KIND_TONE[ev.kind]}>{t[`incKind_${ev.kind}`] ?? ev.kind}</Badge>
        <span className={css.where}>{t.incLap(ev.lap)} · {place}</span>
        <Badge tone={SEV_TONE[ev.severity]}>{t[`incSev_${ev.severity}`] ?? ev.severity}</Badge>
        {ev.went_off && ev.kind !== 'off_track' && <span className={css.meta}>{t.incWentOff}</span>}
        <span className={css.meta}>
          {ev.lap_delta_s != null && <span>{t.incLost(ev.lap_delta_s)}</span>}
          {ev.lap_invalidated && <span>{t.incInvalidated}</span>}
        </span>
        <span className={css.spacer} />
        {main && <span className={css.meta}>{main.label}</span>}
        <Icon name="chevron" size={14} className={`${css.chev} ${open ? css.chevOpen : ''}`} />
      </button>
      {open && (
        <div className={css.body}>
          <div className={css.meta}>
            <span>{t.incMinSpeed(ev.min_speed_kmh)}</span>
            {ev.peak_slip_deg != null && <span>{t.incPeakSlip(ev.peak_slip_deg)}</span>}
            {ev.rotation_deg != null && ev.kind !== 'off_track' && <span>{t.incRotation(ev.rotation_deg)}</span>}
            {ev.off_track && <span>{t.incOffDetail(ev.off_track.wheels, ev.off_track.peak_dirt, ev.off_track.duration_s)}</span>}
          </div>

          {main ? (
            <div className={css.cause}>
              <span className={css.label}>{t.incMainCause}</span>
              <div className={css.mainCause}>
                {main.label}
                <span className={css.conf}>{t[`incConf_${main.confidence}`]}</span>
              </div>
              <div className={css.bar} aria-hidden="true"><div className={css.barFill} style={{ width: `${Math.round(main.score * 100)}%` }} /></div>
              <span className={css.label}>{t.incEvidence}</span>
              <ul className={css.evidence}>{main.evidence.map((e, i) => <li key={i}>{e.text}</li>)}</ul>
              <p className={css.advice}><b>{t.incAdvice}: </b>{main.advice}</p>
            </div>
          ) : (
            <div className={css.cause}>
              <span className={css.mainCause}>{t.incNoCause}</span>
              <span className={css.note}>{t.incNoCauseHint}</span>
            </div>
          )}

          {others.length > 0 && (
            <div className={css.others}>
              <span className={css.label}>{t.incOtherCauses}</span>
              {others.map((c) => (
                <div key={c.code} className={css.otherRow}>
                  <b>{c.label}</b>
                  <span className={css.conf}>{t[`incConf_${c.confidence}`]}</span>
                  {c.evidence[0] && <span>· {c.evidence[0].text}</span>}
                </div>
              ))}
            </div>
          )}

          {rows.length > 2 && (
            <div>
              <div className={css.chartTitle}>{t.incTrace}</div>
              <div className={css.charts}>
                <div><div className={css.chartTitle}>{t.incChartInputs}</div><InputsChart rows={rows} t={t} /></div>
                <div><div className={css.chartTitle}>{t.incChartSpeed}</div><SpeedChart rows={rows} t={t} /></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const IncidentsPanel = ({ data }) => {
  const { t } = useLanguage();
  const events = data?.events || [];
  const [openId, setOpenId] = useState(events[0]?.id ?? null);
  if (!data?.available) return null;
  const s = data.summary || {};
  const hot = s.hot_spots || [];
  const src = data.sources || {};

  return (
    <Panel icon="alert" title={t.incTitle} subtitle={events.length ? t.incSub(events.length, s.n_laps_with_incident) : undefined} id="incidents">
      <div className={css.root}>
        {events.length === 0 ? (
          <div className={css.empty}>
            {t.incNone}
            <div className={css.emptyHint}>{t.incNoneHint}</div>
          </div>
        ) : (
          <>
            {hot.length > 0 && (
              <div className={css.hot} role="note">
                <Icon name="target" size={14} />
                <span className={css.hotTitle}>{t.incHotTitle}</span>
                {hot.map((h, i) => (
                  <Badge key={i} tone="warn">
                    {t.incHot(h.corner?.corner_name || (h.corner?.corner_number != null ? `T${h.corner.corner_number}` : t.incAtDistance(h.distance_m)), h.count)}
                  </Badge>
                ))}
              </div>
            )}
            <div className={css.list}>
              {events.map((ev) => (
                <Event key={ev.id} ev={ev} t={t} open={openId === ev.id} onToggle={() => setOpenId(openId === ev.id ? null : ev.id)} />
              ))}
            </div>
          </>
        )}
        <p className={css.note}>{t.incNote}</p>
        <ul className={css.sources}>
          {src.slip && src.slip !== 'none' && <li>{t[`incSrcSlip_${src.slip}`]}</li>}
          <li>{t[`incSrcOff_${src.off_track || 'none'}`]}</li>
          {s.wind_logged === false && <li>{t.incNoWind}</li>}
        </ul>
      </div>
    </Panel>
  );
};

export default IncidentsPanel;
