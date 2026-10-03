import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel } from './ui';
import { cornerLabel } from '../utils/cornerLabel';
import css from './CornerAnalysisPanel.module.css';

const PHASE_COLOR = {
  frenada: 'var(--lap-a)',
  apex:    'var(--lap-d)',
  salida:  'var(--lap-c)',
};
const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' };
const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');
const signed = (v, d) => `${v > 0 ? '+' : ''}${v.toFixed(d)}`;
// A phase value is only meaningful when the backend flags it as measured (flag absent = available).
const has = (c, phase) => c?.[`${phase}_available`] !== false;

function CustomTooltip({ active, payload }) {
  const { t } = useLanguage();
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  if (d.time_loss_seconds == null) {
    return (
      <div className={css.tip}>
        <div className={css.tipHead}>{cornerLabel(t, d.corner_number, d.corner_name)}</div>
        <div className={css.tipFocus}>{t.rlNoData}</div>
      </div>
    );
  }
  return (
    <div className={css.tip}>
      <div className={css.tipHead}>{cornerLabel(t, d.corner_number, d.corner_name)}</div>
      <div className={css.tipGrid}>
        <span>{clean(t.tooltipLoss)}</span>
        <b className={d.time_loss_seconds > 0 ? css.bad : css.ok}>{signed(d.time_loss_seconds, 3)} s</b>
        {d.std_loss_seconds != null && (
          <>
            <span>{clean(t.tooltipStd)}</span>
            <b className={d.std_loss_seconds > 0.08 ? css.warn : css.ok}>±{d.std_loss_seconds.toFixed(3)} s</b>
          </>
        )}
        {d.n_laps != null && (
          <>
            <span>{clean(t.tooltipLaps)}</span>
            <b>{d.n_laps}</b>
          </>
        )}
        <span>{clean(t.tooltipBrake)}</span>
        <b>{has(d, 'braking') ? `${signed(d.braking_delta_meters, 0)} m` : '—'}</b>
        <span>{clean(t.tooltipApex)}</span>
        <b>{has(d, 'apex') ? `${signed(d.apex_speed_delta_kmh, 1)} km/h` : '—'}</b>
        <span>{clean(t.tooltipThrottle)}</span>
        <b>{has(d, 'throttle') ? `${signed(d.throttle_delta_meters, 0)} m` : '—'}</b>
      </div>
      {d.focus && <div className={css.tipFocus}>{clean(d.focus)}</div>}
    </div>
  );
}

function PhaseBar({ label, delta, unit, color, available = true }) {
  const { t } = useLanguage();
  if (!available) {
    return (
      <div className={css.phase} title={t.cornerNoPhaseData}>
        <span className={css.dot} style={{ background: 'var(--ink-4)' }} />
        <span>{label}</span>
        <div className={css.track} />
        <span className={css.phaseVal}>{'—'}</span>
      </div>
    );
  }
  if (Math.abs(delta) < 0.5) return null;
  return (
    <div className={css.phase}>
      <span className={css.dot} style={{ background: color }} />
      <span>{label}</span>
      <div className={css.track}>
        <div className={css.fill} style={{ width: `${Math.min(100, Math.abs(delta) / 30 * 100)}%`, background: color }} />
      </div>
      <span className={css.phaseVal}>{signed(delta, delta < 10 ? 1 : 0)}{unit}</span>
    </div>
  );
}

function TopCornerCard({ c, rank }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel;
  const dominant = c.dominant_phase;
  const isLoss = (c.time_loss_seconds || 0) > 0;

  return (
    <div className={css.card}>
      <div className={css.cardHead}>
        <span className={css.rank} title={t.cornerPriorityRank(rank)} aria-label={t.cornerPriorityRank(rank)}>{rank}</span>
        <div>
          <div className={css.cardName}>{cornerLabel(t, c.corner_number, c.corner_name)}</div>
          <div className={css.cardPhase}>
            <span className={css.dot} style={{ background: PHASE_COLOR[dominant] || 'var(--ink-3)' }} />
            {PHASE_LABEL[dominant]} {clean(t.phaseDominant)}
          </div>
        </div>
        <div className={css.cardLoss}>
          <div className={`${css.cardLossVal} ${isLoss ? css.loss : css.gain}`}>
            {signed(c.time_loss_seconds || 0, 3)} s
          </div>
          <div className={css.cardLossLbl}>{isLoss ? t.cornerLoss : t.cornerGain}</div>
        </div>
      </div>

      <PhaseBar label={PHASE_LABEL.frenada} delta={c.braking_delta_meters} unit=" m" color={PHASE_COLOR.frenada} available={has(c, 'braking')} />
      <PhaseBar label={PHASE_LABEL.apex} delta={c.apex_speed_delta_kmh} unit=" km/h" color={PHASE_COLOR.apex} available={has(c, 'apex')} />
      <PhaseBar label={PHASE_LABEL.salida} delta={c.throttle_delta_meters} unit=" m" color={PHASE_COLOR.salida} available={has(c, 'throttle')} />

      {c.focus && <div className={css.focus}>{clean(c.focus)}</div>}
      {c.description && <p className={css.desc}>{c.description}</p>}
    </div>
  );
}

export default function CornerAnalysisPanel({ result, metadata, sessionMode, referenceLap, nLaps }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel;
  const corners      = result?.corners || [];
  const cornerPrio   = result?.setup_advisor?.corner_priority || [];
  const [sortBy, setSortBy] = useState('corner');
  const la = metadata?.label_a || 'A';
  const lb = metadata?.label_b || 'B';

  if (!corners.length) return null;

  // Every corner keeps its slot on the X axis (numeric order); corners without data render empty.
  const byCorner = new Map(corners.map(c => [c.corner_number, c]));
  const maxCorner = Math.max(...corners.map(c => c.corner_number));
  const barData = Array.from({ length: maxCorner }, (_, i) => {
    const n = i + 1;
    const c = byCorner.get(n);
    if (!c) return { corner_number: n, time_loss_seconds: null };
    return {
      ...c,
      abs_loss: Math.abs(c.time_loss_seconds || 0),
      ...(cornerPrio.find(cp => cp.corner_number === n) || {}),
      corner_name: c.corner_name ?? null,
      time_loss_seconds: c.time_loss_seconds ?? null,
    };
  });
  const missing = barData.filter(c => c.time_loss_seconds == null).map(c => c.corner_number);

  // Priority rank = position in the impact-ordered list from the backend.
  const byNum = Object.fromEntries(corners.map(c => [c.corner_number, c]));
  const ranked = cornerPrio.slice(0, 6).map((c, i) => ({
    c: {
      ...c,
      corner_name: c.corner_name ?? byNum[c.corner_number]?.corner_name ?? null,
      braking_available: c.braking_available ?? byNum[c.corner_number]?.braking_available,
      apex_available: c.apex_available ?? byNum[c.corner_number]?.apex_available,
      throttle_available: c.throttle_available ?? byNum[c.corner_number]?.throttle_available,
    },
    rank: i + 1,
  }));
  const shown = sortBy === 'corner'
    ? [...ranked].sort((a, b) => a.c.corner_number - b.c.corner_number)
    : ranked;

  const totalLoss = corners.reduce((s, c) => s + Math.max(0, c.time_loss_seconds || 0), 0);

  return (
    <Panel
      icon="steering"
      title={clean(sessionMode ? t.cornerPanelTitleSession : t.cornerPanelTitle)}
      subtitle={sessionMode ? t.cornerDescSession(nLaps, referenceLap) : t.cornerDescCompare(lb, la)}
      actions={(
        <div className={css.total}>
          <div className="ui-eyebrow">{t.cornerTotalLoss}</div>
          <div className={css.totalVal}>+{totalLoss.toFixed(3)} s</div>
        </div>
      )}
    >
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="var(--line)" strokeOpacity={0.6} vertical={false} />
            <XAxis
              dataKey="corner_number"
              tick={AXIS_TICK}
              axisLine={{ stroke: 'var(--line-strong)' }}
              tickLine={false}
              height={32}
              label={{ value: t.cornerLabel, position: 'insideBottom', offset: -2, fill: 'var(--ink-3)', fontSize: 11 }}
            />
            <YAxis
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
            />
            <ReferenceLine y={0} stroke="var(--ink-4)" />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--surface-3)', fillOpacity: 0.5 }} />
            <Bar dataKey="time_loss_seconds" radius={[2, 2, 0, 0]} maxBarSize={32} isAnimationActive={false}>
              {barData.map((entry) => (
                <Cell
                  key={entry.corner_number}
                  fill={entry.time_loss_seconds > 0 ? 'var(--bad)' : 'var(--ok)'}
                  fillOpacity={entry.time_loss_seconds > 0 && entry.time_loss_seconds <= 0.1 ? 0.55 : 0.9}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className={css.legend}>
        <span className={css.legendItem}><span className={css.sw} style={{ background: 'var(--bad)' }} /> {t.cornerLosses(lb)}</span>
        <span className={css.legendItem}><span className={css.sw} style={{ background: 'var(--ok)' }} /> {t.cornerGains(lb)}</span>
        <span className={css.hover}>{clean(t.cornerHover)}</span>
        {missing.length > 0 && <span className={css.hover}>{t.cornerNoDataFor(missing.join(', '))}</span>}
      </div>

      {cornerPrio.length > 0 && (
        <div className={css.section}>
          <div className="ui-eyebrow">{t.cornerPriorityTitle}</div>
          <div role="group" aria-label={t.sortAria} style={{ margin: '8px 0' }}>
            <div className="ui-seg">
              {[['corner', t.sortByCorner], ['impact', t.sortByImpact]].map(([k, label]) => (
                <button key={k} type="button" className="ui-seg__item" aria-pressed={sortBy === k} onClick={() => setSortBy(k)}>{label}</button>
              ))}
            </div>
          </div>
          <div className={css.cards}>
            {shown.map(({ c, rank }, i) => (
              <TopCornerCard key={c.corner_number ?? i} c={c} rank={rank} />
            ))}
          </div>
          <div className={css.legend}>
            {Object.entries(PHASE_LABEL).map(([k, v]) => (
              <span key={k} className={css.legendItem}>
                <span className={css.sw} style={{ background: PHASE_COLOR[k], borderRadius: '50%' }} /> {v}
              </span>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
