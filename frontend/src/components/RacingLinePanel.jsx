import { Fragment } from 'react';
import { Panel, Badge, Icon } from './ui';
import s from './RecPanels.module.css';

const BIN_LABEL = {
  brake: { early: 'Early braking', similar: 'Braking OK', late: 'Late braking' },
  apex:  { slow: 'Slow apex', similar: 'Apex OK', fast: 'Fast apex' },
  exit:  { late: 'Late throttle', similar: 'Throttle OK', early: 'Early throttle' },
};
const PHASE_NAME = { brake: 'Brake', apex: 'Apex', exit: 'Exit' };

function PhaseTag({ phase, value, optimal }) {
  const isOpt = value === optimal;
  const label = BIN_LABEL[phase]?.[value] || value;
  const optLabel = BIN_LABEL[phase]?.[optimal] || optimal;
  return (
    <div className={`${s.phase} ${isOpt ? s.good : s.bad}`}>
      <span className={s.phaseKey}>{PHASE_NAME[phase]}</span>
      <span className={s.phaseVal}>{label}</span>
      {isOpt
        ? <Icon name="check" size={14} style={{ color: 'var(--ok)' }} aria-label="Optimal" />
        : <span className={s.phaseTarget}>target <b>{optLabel}</b></span>}
    </div>
  );
}

function QHeatmap({ heatmap, current, optimal }) {
  if (!heatmap?.length) return null;
  const brakeLabels = ['early', 'similar', 'late'];
  const apexLabels = ['slow', 'similar', 'fast'];
  const qByKey = {};
  heatmap.forEach(h => { qByKey[`${h.brake}_${h.apex}`] = h; });

  return (
    <div>
      <div className={s.fieldLbl}>Q-table · braking × apex</div>
      <div className={s.q}>
        <div />
        {apexLabels.map(al => <div key={al} className={s.qHead}>{al.slice(0, 3)}</div>)}
        {brakeLabels.map(bl => (
          <Fragment key={bl}>
            <div className={s.qRow}>{bl.slice(0, 3)}</div>
            {apexLabels.map(al => {
              const cell = qByKey[`${bl}_${al}`];
              const q = cell?.q;
              const isCurrent = bl === current.brake && al === current.apex;
              const isOptimal = bl === optimal.brake && al === optimal.apex;
              const cls = `${s.qCell} ${isOptimal ? s.opt : isCurrent ? s.cur : ''}`;
              return (
                <div key={al} className={cls} title={cell ? `Q: ${q?.toFixed(4)} | obs: ${cell.count}` : 'no data'}>
                  {q != null ? (q > 0 ? '+' : '') + q.toFixed(3) : '—'}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
      <div className={s.legend}>
        <span><span className={s.sw} style={{ background: 'var(--ok)' }} />Optimal</span>
        <span><span className={s.sw} style={{ background: 'var(--warn)' }} />Current</span>
      </div>
    </div>
  );
}

function CornerCard({ corner }) {
  const { corner_number, n_laps, mean_time_loss_s, potential_gain_s,
    current_execution, optimal_execution, already_optimal, recommendations } = corner;

  const tone = already_optimal ? 'ok' : potential_gain_s > 0.15 ? 'bad' : potential_gain_s > 0.05 ? 'warn' : 'ok';
  const cls = { bad: s.high, warn: s.med, ok: s.low }[tone];

  return (
    <div className={`${s.card} ${cls}`}>
      <div className={s.cardHead}>
        <div>
          <div className={s.cardTitle}>Corner {corner_number}</div>
          <div className={s.cardSub}>{n_laps} laps · avg loss <span className={s.mono}>{mean_time_loss_s > 0 ? '+' : ''}{mean_time_loss_s.toFixed(3)} s</span></div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {already_optimal
            ? <Badge tone="ok">OPTIMAL</Badge>
            : <div className={s.recGainVal} style={{ color: `var(--${tone})` }}>+{potential_gain_s.toFixed(3)} s</div>}
          {!already_optimal && <div className={s.recGainLbl}>potential gain</div>}
        </div>
      </div>

      <div className={s.stack} style={{ gap: 4 }}>
        <PhaseTag phase="brake" value={current_execution.brake} optimal={optimal_execution.brake} />
        <PhaseTag phase="apex" value={current_execution.apex} optimal={optimal_execution.apex} />
        <PhaseTag phase="exit" value={current_execution.exit} optimal={optimal_execution.exit} />
      </div>

      {!already_optimal && recommendations?.length > 0 && (
        <ul className={s.actions}>
          {recommendations.map((r, i) => (
            <li key={i}><Icon name="chevron" size={12} /><span>{r}</span></li>
          ))}
        </ul>
      )}

      <details>
        <summary className={s.cardSub} style={{ cursor: 'pointer' }}>Q-table detail</summary>
        <div style={{ marginTop: 8 }}>
          <QHeatmap heatmap={corner.q_heatmap} current={current_execution} optimal={optimal_execution} />
        </div>
      </details>
    </div>
  );
}

export default function RacingLinePanel({ data }) {
  if (!data?.available) return null;

  const { corners, total_potential_gain_s, n_corners } = data;
  const byGain = [...corners].sort((a, b) => b.potential_gain_s - a.potential_gain_s);
  const optimal = corners.filter(c => c.already_optimal).length;

  const gain = (
    <div className={s.gain}>
      <span className={s.gainLabel}>Total potential gain</span>
      <span className={s.gainValue}>+{total_potential_gain_s.toFixed(3)} s</span>
      <span className={s.gainSub}>if optimal line is applied</span>
    </div>
  );

  return (
    <Panel
      icon="target"
      title="Racing Line Optimization"
      subtitle={`Tabular Q-learning · ${n_corners} corners · ${optimal} already optimal`}
      actions={gain}
    >
      <div className={s.sectionHead}><span className={s.sectionTitle}>Corners ranked by potential gain</span></div>
      <div className={s.cards}>
        {byGain.map((c) => <CornerCard key={c.corner_number} corner={c} />)}
      </div>

      <p className={s.note}>
        Offline Q-learning trained on session historical telemetry data. The agent learns which braking/apex/throttle combination produced the least time loss in past laps. Recommendations reflect statistical patterns — validate on track before applying drastic changes.
      </p>
    </Panel>
  );
}
