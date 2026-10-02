import { useId, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon, EmptyState } from './ui';
import s from './RecPanels.module.css';

const TONE = { alta: 'bad', media: 'warn', baja: 'ok', nominal: undefined };
const ROWCLS = { alta: 'high', media: 'med', baja: 'low', nominal: 'nom' };

function RecCard({ rec, isPilotMode }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const prio = rec.priority in ROWCLS ? rec.priority : 'baja';
  const labels = { alta: t.priorityHigh, media: t.priorityMed, baja: t.priorityLow, nominal: t.thPrioNominal };
  const rowCls = `${s.rec} ${s[ROWCLS[prio]]}`;

  if (isPilotMode) {
    return (
      <div className={rowCls}>
        <div className={`${s.recHead} ${s.recStatic}`}>
          <div className={s.recMain}>
            <div className={s.recMeta}>
              <Badge tone={TONE[prio]}>{labels[prio]}</Badge>
            </div>
            <p className={s.recText} style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{rec.pilot_note || rec.problem}</p>
          </div>
          <div className={s.recGain}>
            <div className={s.recGainVal}>{rec.expected_gain}</div>
            <div className={s.recGainLbl}>{t.setupPotential}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={rowCls}>
      <button type="button" className={s.recHead} aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen(o => !o)}>
        <div className={s.recMain}>
          <div className={s.recMeta}>
            <Badge tone={TONE[prio]}>{labels[prio]}</Badge>
            <span className={s.recCat}>{rec.category}</span>
          </div>
          <p className={s.recText}>{rec.problem}</p>
        </div>
        <div className={s.recGain}>
          <div className={s.recGainVal}>{rec.expected_gain}</div>
          <div className={s.recGainLbl}>{t.setupPotential}</div>
        </div>
        <Icon name="chevron" size={16} className={`${s.chev} ${open ? s.chevOpen : ''}`} />
      </button>

      {open && (
        <div id={bodyId} className={s.recBody}>
          <div className={s.cols}>
            <div>
              <div className={s.fieldLbl}>{t.setupRootCause}</div>
              <p className={s.fieldTxt}>{rec.root_cause}</p>
            </div>
            <div>
              <div className={s.fieldLbl}>{t.setupRec}</div>
              <p className={`${s.fieldTxt} ${s.strong}`}>{rec.recommendation}</p>
            </div>
          </div>
          {rec.detail && (
            <>
              <div className={s.fieldLbl} style={{ marginTop: 12 }}>{t.setupData}</div>
              <p className={s.data} style={{ marginTop: 0 }}>{rec.detail}</p>
            </>
          )}
          {rec.solves && (
            <div className={s.solves}>
              <Icon name="check" size={14} />
              <span>{rec.solves}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const AREA_KEY = { nominal: 'areaOk', alta: 'areaHigh', media: 'areaMed', baja: 'areaLow' };

export default function SetupRecommendations({ setup_advisor, source, isPilotMode }) {
  const { t } = useLanguage();
  const [filter, setFilter] = useState('all');

  if (!setup_advisor?.available && !setup_advisor?.areas_status?.length) return null;
  const { recommendations = [], areas_status = [], total_gain_range } = setup_advisor;

  const counts = {
    all:   recommendations.length,
    alta:  recommendations.filter(r => r.priority === 'alta').length,
    media: recommendations.filter(r => r.priority === 'media').length,
    baja:  recommendations.filter(r => r.priority === 'baja').length,
  };
  const visible = filter === 'all' ? recommendations : recommendations.filter(r => r.priority === filter);

  const gain = recommendations.length > 0 && total_gain_range && (
    <div className={s.gain}>
      <span className={s.gainLabel}>{t.setupGainLabel}</span>
      <span className={s.gainValue}>{total_gain_range}s</span>
      <span className={s.gainSub}>{t.setupGainSub}</span>
    </div>
  );

  const filters = [
    { key: 'all',   label: t.setupFilterAll(counts.all) },
    { key: 'alta',  label: t.setupFilterHigh(counts.alta) },
    { key: 'media', label: t.setupFilterMed(counts.media) },
    { key: 'baja',  label: t.setupFilterLow(counts.baja) },
  ];

  return (
    <Panel icon="wrench" title={t.setupTitle} subtitle={t.setupSub(recommendations.length)} actions={gain || null}>
      {source === 'compare' && (
        <div style={{ marginBottom: 12 }}><Badge tone="accent">{t.setupPostLap}</Badge></div>
      )}

      {!isPilotMode && areas_status?.length > 0 && (
        <div className={s.section}>
          <div className={s.sectionHead}><span className={s.sectionTitle}>{t.setupAreaHealth}</span></div>
          <div className={s.chips}>
            {areas_status.map(area => (
              <div key={area.domain} className={s.chip}>
                <div><Badge tone={TONE[area.status] ?? 'accent'}>{t[AREA_KEY[area.status]] ?? t.areaOk}</Badge></div>
                <span className={s.chipLabel}>{area.label}</span>
                {area.n_issues > 0 && <span className={s.chipHint}>{t.setupIssues(area.n_issues)}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className={s.section}>
        {recommendations.length > 0 && (
          <div className={s.filters} role="group" aria-label={t.setupFilterAria}>
            <div className="ui-seg">
              {filters.map(f => (
                <button key={f.key} type="button" className="ui-seg__item" aria-pressed={filter === f.key} onClick={() => setFilter(f.key)}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className={s.stack}>
          {visible.map((rec, i) => <RecCard key={i} rec={rec} isPilotMode={isPilotMode} />)}
        </div>
        {visible.length === 0 && <EmptyState icon="check">{t.setupEmpty}</EmptyState>}
      </div>

      <p className={s.note}>{t.setupDisclaimer}</p>
    </Panel>
  );
}
