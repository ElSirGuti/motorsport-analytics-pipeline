import { useEffect, useId, useMemo, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Icon } from './ui';
import { detectSessionMeta, fetchSetupCandidates, fetchSetupById, uploadSetup } from '../api/setups';
import { DropZone } from './SetupSelector';
import s from './SetupSelector.module.css';

const fmtDate = (mtime, lang) => (mtime ? new Date(mtime * 1000).toLocaleString(lang, { dateStyle: 'medium', timeStyle: 'short' }) : '');

/**
 * Form to add (or change) a setup change: the lap where it starts and which setup it is
 * (one saved by the game for this car and track, or an uploaded .ini).
 * onSave({ fromLap, setup }) | onCancel()
 */
const fmtLap = (s) => {
  if (s == null || !Number.isFinite(Number(s))) return '';
  const m = Math.floor(Number(s) / 60);
  return `${m}:${(Number(s) % 60).toFixed(3).padStart(6, '0')}`;
};

/** Laps 2..n the user can pick (the first lap cannot start a change), with time and pit / best marks. */
function lapOptions(laps, nLaps) {
  const byNum = new Map((laps || []).map((l) => [Number(l.lap_number), l]));
  const times = (laps || []).filter((l) => !l.is_pit_lap && l.lap_time_s).map((l) => Number(l.lap_time_s));
  const best = times.length ? Math.min(...times) : null;
  return Array.from({ length: Math.max(0, nLaps - 1) }, (_, i) => {
    const n = i + 2;
    const l = byNum.get(n);
    return { n, time: l?.lap_time_s ?? null, pit: !!l?.is_pit_lap, best: best != null && l && Number(l.lap_time_s) === best,
             afterPit: !!byNum.get(n - 1)?.is_pit_lap };
  });
}

export default function SetupChangePicker({ file, nLaps, laps, initial, onSave, onCancel }) {
  const { t, lang } = useLanguage();
  const groupId = useId();
  const lapList = useMemo(() => lapOptions(laps, nLaps), [laps, nLaps]);
  // Setups are changed in the pits: suggest the lap that starts right after the first pit stop.
  const suggested = lapList.find((o) => o.afterPit)?.n;
  const [lap, setLap] = useState(initial?.fromLap ? String(initial.fromLap) : (suggested ? String(suggested) : ''));
  const [meta, setMeta] = useState(null);
  const [cand, setCand] = useState(null);
  const [pick, setPick] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const m = await detectSessionMeta(file);
        const c = await fetchSetupCandidates(m.vehicle, m.venue, lang);
        if (!alive) return;
        setMeta(m);
        setCand(c);
        setPick(c.track_setups?.[0]?.id ?? null);
      } catch (e) {
        if (alive) setErr(e.message);
      }
    })();
    return () => { alive = false; };
  }, [file, lang]);

  const lapNum = Number(lap);
  const lapOk = Number.isInteger(lapNum) && lapNum >= 2 && lapNum <= nLaps;

  const options = [
    ...(cand?.track_setups || []).map((x) => ({ ...x, kind: 'track' })),
    ...(cand?.generic_last ? [{ ...cand.generic_last, kind: 'generic' }] : []),
  ];

  const useCandidate = async () => {
    setBusy(true);
    setErr('');
    try {
      const setup = await fetchSetupById(meta.vehicle, meta.venue, pick, lang);
      onSave({ fromLap: lapNum, setup });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const upload = async (f) => {
    if (!lapOk) { setErr(t.ssFromLapHint(nLaps)); return; }
    setBusy(true);
    setErr('');
    try {
      const setup = await uploadSetup(f, meta?.vehicle, lang);
      onSave({ fromLap: lapNum, setup });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={s.card} data-testid="setup-change-form">
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, maxWidth: 260 }}>
        <span className={s.barLabel}>{t.ssFromLap}</span>
        <select
          value={lap}
          onChange={(e) => setLap(e.target.value)}
          data-testid="setup-change-lap"
          style={{ padding: '8px 10px', font: 'inherit', background: 'var(--surface-1)', color: 'var(--ink-1)', border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)' }}
        >
          <option value="">{t.ssChooseLap}</option>
          {lapList.map((o) => (
            <option key={o.n} value={String(o.n)}>
              {t.ssLapOption(o.n, fmtLap(o.time), [o.pit && t.ssTagPit, o.best && t.ssTagBest, o.afterPit && t.ssTagAfterPit].filter(Boolean))}
            </option>
          ))}
        </select>
        {suggested && <span className={s.optMeta}>{t.ssSuggested(suggested)}</span>}
      </label>

      {options.length > 0 ? (
        <fieldset className={s.list} aria-labelledby={`${groupId}-t`}>
          <legend id={`${groupId}-t`} className={s.legend}>{t.ssPick}</legend>
          {options.map((o) => (
            <label key={o.id} className={`${s.opt} ${pick === o.id ? s.optOn : ''}`}>
              <input type="radio" name={groupId} checked={pick === o.id} onChange={() => setPick(o.id)} />
              <span className={s.optBody}>
                <span className={s.optName}>{o.name}</span>
                <span className={s.optMeta}>{fmtDate(o.mtime, lang)}</span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : (
        cand && <p className={s.cardQ}>{t.ssNoCandidates}</p>
      )}

      <div className={s.actions}>
        {options.length > 0 && (
          <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" onClick={useCandidate} disabled={busy || !lapOk || !pick} data-testid="setup-change-use">
            {t.ssUseCandidate}
          </button>
        )}
        <button type="button" className="ui-btn ui-btn--sm" onClick={onCancel}>{t.ssCancel}</button>
      </div>

      <DropZone onFile={upload} busy={busy} error={null} />
      {err && <div className={s.err} role="alert"><Icon name="alert" size={14} />{err}</div>}
    </div>
  );
}
