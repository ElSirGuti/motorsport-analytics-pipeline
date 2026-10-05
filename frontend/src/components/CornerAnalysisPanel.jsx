import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { Panel } from './ui';
import { cornerLabel } from '../utils/cornerLabel';
import { cornerMapIndex, withMapInfo, hasPhase, isNoPhase } from '../utils/cornerKind';
import { CornerTags, CornerMapNotice, NoPhaseNote } from './CornerMeta';
import { kindTip, isDim } from '../utils/cornerTips';
import css from './CornerAnalysisPanel.module.css';

const PHASE_COLOR = {
  frenada: 'var(--lap-a)',
  apex:    'var(--lap-d)',
  salida:  'var(--lap-c)',
};
const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 11, fontFamily: 'var(--font-mono)' };
const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');
const head = (s) => clean(s).replace(/\s*:\s*$/, '');
const signed = (v, d) => `${v > 0 ? '+' : ''}${v.toFixed(d)}`;
// A phase value is only meaningful when the backend flags it as measured (flag absent = available).
const has = hasPhase;
const HATCH_BAD = 'cap-hatch-bad';
const HATCH_OK = 'cap-hatch-ok';

// X axis tick: corner number, plus a small bar under flat-out / kink corners.
function CornerTick({ x, y, payload, noPhase }) {
  const n = payload?.value;
  return (
    <g transform={`translate(${x},${y})`}>
      <text x={0} y={0} dy={13} textAnchor="middle" {...AXIS_TICK}>{n}</text>
      {noPhase?.has(n) && <rect x={-5} y={20} width={10} height={3} rx={1} fill="var(--ink-3)" />}
    </g>
  );
}

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
      <div className={css.tipHead}>{cornerLabel(t, d.corner_number, d.corner_name)} <CornerTags corner={d} /></div>
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
        {!isNoPhase(d) && (
          <>
            <span>{clean(t.tooltipBrake)}</span>
            <b>{has(d, 'braking') ? `${signed(d.braking_delta_meters, 0)} m` : '—'}</b>
            <span>{clean(t.tooltipApex)}</span>
            <b>{has(d, 'apex') ? `${signed(d.apex_speed_delta_kmh, 1)} km/h` : '—'}</b>
            <span>{clean(t.tooltipThrottle)}</span>
            <b>{has(d, 'throttle') ? `${signed(d.throttle_delta_meters, 0)} m` : '—'}</b>
          </>
        )}
      </div>
      {isNoPhase(d) && <div className={css.tipKind}>{kindTip(t, d)}</div>}
      {d.focus && <div className={css.tipFocus}>{clean(d.focus)}</div>}
    </div>
  );
}

function PhaseBar({ label, delta, unit, color, available = true }) {
  const { t } = useLanguage();
  if (!available) {
    return (
      <div className={css.phase} title={t.cmNoPhaseTip}>
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

// Every detected corner in one compact table: corners without a phase show '—', never '0 m'.
function AllCornersTable({ corners, sortBy }) {
  const { t } = useLanguage();
  const rows = sortBy === 'impact'
    ? [...corners].sort((a, b) => (b.time_loss_seconds || 0) - (a.time_loss_seconds || 0))
    : [...corners].sort((a, b) => a.corner_number - b.corner_number);
  const cell = (c, phase, val, unit, d) => (has(c, phase) && !isNoPhase(c) && val != null
    ? `${signed(val, d)}${unit}`
    : <span className={css.muted} title={t.cmNoPhaseTip}>{'—'}</span>);
  return (
    <div className={css.allWrap} data-testid="all-corners">
      <div className="ui-eyebrow">{t.cmAllCorners}</div>
      <div className={css.tableScroll}>
        <table className="ui-table">
          <thead>
            <tr>
              <th>{t.cornerLabel}</th>
              <th className="is-num">{head(t.tooltipLoss)}</th>
              <th className="is-num">{head(t.tooltipBrake)}</th>
              <th className="is-num">{head(t.tooltipApex)}</th>
              <th className="is-num">{head(t.tooltipThrottle)}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const loss = c.time_loss_seconds;
              return (
                <tr key={c.corner_number} className={isDim(c) ? css.dimRow : undefined}>
                  <td>
                    <span className={css.cornerCell}>
                      <span className={css.cornerName}>{cornerLabel(t, c.corner_number, c.corner_name)}</span>
                      <CornerTags corner={c} />
                    </span>
                  </td>
                  <td className="is-num" style={{ color: loss > 0 ? 'var(--bad)' : loss < 0 ? 'var(--ok)' : undefined, fontWeight: 600 }}>
                    {loss != null ? `${signed(loss, 3)} s` : '—'}
                  </td>
                  <td className="is-num">{cell(c, 'braking', c.braking_delta_meters, ' m', 0)}</td>
                  <td className="is-num">{cell(c, 'apex', c.apex_speed_delta_kmh, ' km/h', 1)}</td>
                  <td className="is-num">{cell(c, 'throttle', c.throttle_delta_meters, ' m', 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TopCornerCard({ c, rank }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel;
  const dominant = c.dominant_phase;
  const isLoss = (c.time_loss_seconds || 0) > 0;
  const noPhase = isNoPhase(c);

  return (
    <div className={`${css.card}${isDim(c) ? ` ${css.dim}` : ''}`}>
      <div className={css.cardHead}>
        <span className={css.rank} title={t.cornerPriorityRank(rank)} aria-label={t.cornerPriorityRank(rank)}>{rank}</span>
        <div className={css.cardTitle}>
          <div className={css.cardName}>{cornerLabel(t, c.corner_number, c.corner_name)}</div>
          <CornerTags corner={c} />
          {!noPhase && (
            <div className={css.cardPhase}>
              <span className={css.dot} style={{ background: PHASE_COLOR[dominant] || 'var(--ink-3)' }} />
              {PHASE_LABEL[dominant]} {clean(t.phaseDominant)}
            </div>
          )}
        </div>
        <div className={css.cardLoss}>
          <div className={`${css.cardLossVal} ${isLoss ? css.loss : css.gain}`}>
            {signed(c.time_loss_seconds || 0, 3)} s
          </div>
          <div className={css.cardLossLbl}>{isLoss ? t.cornerLoss : t.cornerGain}</div>
        </div>
      </div>

      {noPhase && <NoPhaseNote corner={c} />}
      {!noPhase && <PhaseBar label={PHASE_LABEL.frenada} delta={c.braking_delta_meters} unit=" m" color={PHASE_COLOR.frenada} available={has(c, 'braking')} />}
      {!noPhase && <PhaseBar label={PHASE_LABEL.apex} delta={c.apex_speed_delta_kmh} unit=" km/h" color={PHASE_COLOR.apex} available={has(c, 'apex')} />}
      {!noPhase && <PhaseBar label={PHASE_LABEL.salida} delta={c.throttle_delta_meters} unit=" m" color={PHASE_COLOR.salida} available={has(c, 'throttle')} />}

      {c.focus && <div className={css.focus}>{clean(c.focus)}</div>}
      {c.description && <p className={css.desc}>{c.description}</p>}
    </div>
  );
}

export default function CornerAnalysisPanel({ result, metadata, sessionMode, referenceLap, nLaps, cornerMap }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel;
  const cMap         = cornerMap ?? result?.corner_map;
  const mapIdx       = cornerMapIndex(cMap);
  const corners      = (result?.corners || []).map((c) => withMapInfo(c, mapIdx));
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
  const noPhaseSet = new Set(barData.filter(isNoPhase).map((c) => c.corner_number));
  const missing = barData.filter(c => c.time_loss_seconds == null).map(c => c.corner_number);

  // Priority rank = position in the impact-ordered list from the backend.
  const byNum = Object.fromEntries(corners.map(c => [c.corner_number, c]));
  const ranked = cornerPrio.slice(0, 6).map((c, i) => ({
    c: {
      ...byNum[c.corner_number],
      ...c,
      corner_name: c.corner_name ?? byNum[c.corner_number]?.corner_name ?? null,
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
      <CornerMapNotice cornerMap={cMap} />
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <defs>
              <pattern id={HATCH_BAD} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="var(--bad)" fillOpacity="0.18" />
                <rect width="3" height="6" fill="var(--bad)" fillOpacity="0.85" />
              </pattern>
              <pattern id={HATCH_OK} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="var(--ok)" fillOpacity="0.18" />
                <rect width="3" height="6" fill="var(--ok)" fillOpacity="0.85" />
              </pattern>
            </defs>
            <CartesianGrid stroke="var(--line)" strokeOpacity={0.6} vertical={false} />
            <XAxis
              dataKey="corner_number"
              tick={<CornerTick noPhase={noPhaseSet} />}
              interval={0}
              axisLine={{ stroke: 'var(--line-strong)' }}
              tickLine={false}
              height={36}
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
                  fill={isNoPhase(entry)
                    ? `url(#${entry.time_loss_seconds > 0 ? HATCH_BAD : HATCH_OK})`
                    : entry.time_loss_seconds > 0 ? 'var(--bad)' : 'var(--ok)'}
                  fillOpacity={isNoPhase(entry) ? 1 : entry.time_loss_seconds > 0 && entry.time_loss_seconds <= 0.1 ? 0.55 : 0.9}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className={css.legend}>
        <span className={css.legendItem}><span className={css.sw} style={{ background: 'var(--bad)' }} /> {t.cornerLosses(lb)}</span>
        <span className={css.legendItem}><span className={css.sw} style={{ background: 'var(--ok)' }} /> {t.cornerGains(lb)}</span>
        {noPhaseSet.size > 0 && (
          <span className={css.legendItem} title={t.cmKindTip_flat_out}>
            <span className={`${css.sw} ${css.swHatch}`} /> {t.cmLegendNoPhases}
          </span>
        )}
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
          <AllCornersTable corners={corners} sortBy={sortBy} />
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
