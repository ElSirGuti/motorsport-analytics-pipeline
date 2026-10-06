import { useEffect, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { annotateRecommendations } from '../api/setups';
import { Badge } from './ui';
import SetupRecommendations from './SetupRecommendations';
import { setupDiff } from '../utils/setupDiff';
import css from './SetupSegments.module.css';

const MAX_DIFF = 12;
const fmtTime = (s) => {
  if (s == null) return '—';
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toFixed(3).padStart(6, '0')}`;
};
const fmtVal = (v) => (v == null ? '—' : typeof v === 'number' ? String(Math.round(v * 1000) / 1000) : String(v));

function Diff({ prev, cur }) {
  const { t } = useLanguage();
  if (!prev || !cur) return null;
  const rows = setupDiff(prev, cur);
  return (
    <div>
      <span className={css.label}>{t.ssChanged}</span>
      {rows.length === 0 ? (
        <p className={css.muted}>{t.ssNoDiff}</p>
      ) : (
        <ul className={css.diff}>
          {rows.slice(0, MAX_DIFF).map((r) => (
            <li key={r.key}>{r.label}: <code>{fmtVal(r.from)}</code> → <code>{fmtVal(r.to)}</code>{r.unit ? ` ${r.unit}` : ''}</li>
          ))}
          {rows.length > MAX_DIFF && <li>{t.ssMore(rows.length - MAX_DIFF)}</li>}
        </ul>
      )}
    </div>
  );
}

function Pace({ seg }) {
  const { t } = useLanguage();
  const p = seg.pace || {};
  if (!p.n_valid) return null;
  const d = seg.vs_previous?.median_delta_s;
  return (
    <div>
      <span className={css.label}>{t.ssPace}</span>
      <div className={css.kpis}>
        <div className={css.kpi}><span className={css.kpiVal}>{fmtTime(p.median_s)}</span><span className={css.kpiLbl}>{t.ssMedian}</span></div>
        <div className={css.kpi}><span className={css.kpiVal}>{fmtTime(p.best_s)}</span><span className={css.kpiLbl}>{t.ssBest}</span></div>
        {p.std_s != null && <div className={css.kpi}><span className={css.kpiVal}>±{p.std_s.toFixed(2)} s</span><span className={css.kpiLbl}>{t.ssConsistency}</span></div>}
      </div>
      <div className={css.muted} style={{ marginTop: 6 }}>
        {t.ssValidLaps(p.n_valid, p.n_laps)}{p.n_incident_laps > 0 ? ` · ${t.ssIncidentLaps(p.n_incident_laps)}` : ''}
      </div>
      {d != null && (
        <div className={`${css.delta} ${d < -0.005 ? css.good : d > 0.005 ? css.bad : ''}`}>
          {Math.abs(d) <= 0.005 ? t.ssSame : d < 0 ? t.ssFaster(-d) : t.ssSlower(d)} {t.ssVsPrevious}
          <div className={css.muted}>{t.ssPaceCaveat}</div>
        </div>
      )}
    </div>
  );
}

function Recs({ seg, setup, isPilotMode, source }) {
  const { t, lang } = useLanguage();
  const [annot, setAnnot] = useState(null);
  const advisor = seg.setup_advisor;
  const recs = advisor?.recommendations;

  useEffect(() => {
    if (!setup || !recs?.length) return undefined;
    let alive = true;
    annotateRecommendations(setup, recs, lang)
      .then((data) => { if (alive) setAnnot({ setup, recs, data }); })
      .catch(() => { if (alive) setAnnot(null); });
    return () => { alive = false; };
  }, [setup, recs, lang]);

  if (!advisor?.available) {
    const key = { few_laps: t.ssFewLaps(3), no_data: t.ssNoData, error: t.ssAdvisorError }[seg.advisor_reason];
    return key ? <p className={css.note}>{key}</p> : null;
  }
  const annotated = setup && annot && annot.setup === setup && annot.recs === recs ? annot.data : null;
  return (
    <div>
      <span className={css.label}>{t.ssRecsOf}</span>
      <SetupRecommendations setup_advisor={advisor} source={source} isPilotMode={isPilotMode} setup={setup} annotated={annotated} />
    </div>
  );
}

/** One card per range of laps between setup changes: setup, pace, what changed and its own recommendations. */
export default function SetupSegments({ segments, setups, isPilotMode, source }) {
  const { t } = useLanguage();
  return (
    <div className={css.root} data-testid="setup-segments">
      {segments.map((seg, i) => {
        const setup = setups[i] ?? null;
        return (
          <section key={seg.index} className={css.seg} data-testid="setup-segment">
            <header className={css.segHead}>
              <span className={css.segLaps}>{t.ssLapsRange(seg.from_lap, seg.to_lap)}</span>
              <Badge tone={setup ? 'accent' : undefined}>{setup ? setup.name : t.ssNoSetup}</Badge>
            </header>
            <div className={css.segBody}>
              <Pace seg={seg} />
              {i > 0 && <Diff prev={setups[i - 1]} cur={setup} />}
              <Recs seg={seg} setup={setup} isPilotMode={isPilotMode} source={source} />
            </div>
          </section>
        );
      })}
    </div>
  );
}
