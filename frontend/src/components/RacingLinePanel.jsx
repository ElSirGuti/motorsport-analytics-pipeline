import { Fragment, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import s from './RecPanels.module.css';


function PhaseTag({ phase, value, optimal }) {
  const { t } = useLanguage();
  const isOpt = value === optimal;
  const label = t[`rlBin_${phase}_${value}`] || value;
  const optLabel = t[`rlBin_${phase}_${optimal}`] || optimal;
  return (
    <div className={`${s.phase} ${isOpt ? s.good : s.bad}`}>
      <span className={s.phaseKey}>{t[`rlPhase_${phase}`]}</span>
      <span className={s.phaseVal}>{label}</span>
      {isOpt
        ? <Icon name="check" size={14} style={{ color: 'var(--ok)' }} aria-label={t.rlOptimalLower} />
        : <span className={s.phaseTarget}>{t.rlTarget} <b>{optLabel}</b></span>}
    </div>
  );
}

function QHeatmap({ heatmap, current, optimal }) {
  const { t } = useLanguage();
  if (!heatmap?.length) return null;
  const brakeLabels = ['early', 'similar', 'late'];
  const apexLabels = ['slow', 'similar', 'fast'];
  const qByKey = {};
  heatmap.forEach(h => { qByKey[`${h.brake}_${h.apex}`] = h; });

  return (
    <div>
      <div className={s.fieldLbl}>{t.rlQTable}</div>
      <div className={s.q}>
        <div />
        {apexLabels.map(al => <div key={al} className={s.qHead}>{t[`rlShort_${al}`]}</div>)}
        {brakeLabels.map(bl => (
          <Fragment key={bl}>
            <div className={s.qRow}>{t[`rlShort_${bl}`]}</div>
            {apexLabels.map(al => {
              const cell = qByKey[`${bl}_${al}`];
              const q = cell?.q;
              const isCurrent = bl === current.brake && al === current.apex;
              const isOptimal = bl === optimal.brake && al === optimal.apex;
              const cls = `${s.qCell} ${isOptimal ? s.opt : isCurrent ? s.cur : ''}`;
              return (
                <div key={al} className={cls} title={cell && q != null ? t.rlCellTip(q.toFixed(4), cell.count) : t.rlNoData}>
                  {q != null ? (q > 0 ? '+' : '') + q.toFixed(3) : '—'}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
      <div className={s.legend}>
        <span><span className={s.sw} style={{ background: 'var(--ok)' }} />{t.rlOptimal}</span>
        <span><span className={s.sw} style={{ background: 'var(--warn)' }} />{t.rlCurrent}</span>
      </div>
    </div>
  );
}

function CornerCard({ corner }) {
  const { t } = useLanguage();
  const { corner_number, n_laps, mean_time_loss_s, potential_gain_s,
    current_execution, optimal_execution, already_optimal, recommendations } = corner;

  const tone = already_optimal ? 'ok' : potential_gain_s > 0.15 ? 'bad' : potential_gain_s > 0.05 ? 'warn' : 'ok';
  const cls = { bad: s.high, warn: s.med, ok: s.low }[tone];

  return (
    <div className={`${s.card} ${cls}`}>
      <div className={s.cardHead}>
        <div>
          <div className={s.cardTitle}>{t.rlCorner(corner_number)}</div>
          <div className={s.cardSub}>{t.rlLapsAvgLoss(n_laps)} <span className={s.mono}>{mean_time_loss_s > 0 ? '+' : ''}{mean_time_loss_s.toFixed(3)} s</span></div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {already_optimal
            ? <Badge tone="ok">{t.rlOptimalBadge}</Badge>
            : <div className={s.recGainVal} style={{ color: `var(--${tone})` }}>+{potential_gain_s.toFixed(3)} s</div>}
          {!already_optimal && <div className={s.recGainLbl}>{t.rlPotentialGain}</div>}
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
        <summary className={s.cardSub} style={{ cursor: 'pointer' }}>{t.rlQDetail}</summary>
        <div style={{ marginTop: 8 }}>
          <QHeatmap heatmap={corner.q_heatmap} current={current_execution} optimal={optimal_execution} />
        </div>
      </details>
    </div>
  );
}

export default function RacingLinePanel({ data }) {
  const { t } = useLanguage();
  const [sortBy, setSortBy] = useState('corner');
  if (!data?.available) return null;

  const { corners, total_potential_gain_s, n_corners } = data;
  const sorted = sortBy === 'corner'
    ? [...corners].sort((a, b) => a.corner_number - b.corner_number)
    : [...corners].sort((a, b) => b.potential_gain_s - a.potential_gain_s);
  const optimal = corners.filter(c => c.already_optimal).length;

  const gain = (
    <div className={s.gain}>
      <span className={s.gainLabel}>{t.rlTotalGain}</span>
      <span className={s.gainValue}>+{total_potential_gain_s.toFixed(3)} s</span>
      <span className={s.gainSub}>{t.rlIfOptimal}</span>
    </div>
  );

  return (
    <Panel
      icon="target"
      title={t.rlTitle}
      subtitle={t.rlSubtitle(n_corners, optimal)}
      actions={gain}
    >
      <div className={s.sectionHead}>
        <span className={s.sectionTitle}>{sortBy === 'corner' ? t.rlByCorner : t.rlRanked}</span>
        <div className="ui-seg" role="group" aria-label={t.sortAria} style={{ marginLeft: 'auto' }}>
          {[['corner', t.sortByCorner], ['impact', t.sortByImpact]].map(([k, label]) => (
            <button key={k} type="button" className="ui-seg__item" aria-pressed={sortBy === k} onClick={() => setSortBy(k)}>{label}</button>
          ))}
        </div>
      </div>
      <div className={s.cards}>
        {sorted.map((c) => <CornerCard key={c.corner_number} corner={c} />)}
      </div>

      <p className={s.note}>{t.rlDisclaimer}</p>
    </Panel>
  );
}
