import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import {
  detectSessionMeta, fetchSetupCandidates, fetchSetupById, uploadSetup,
} from '../api/setups';
import s from './SetupSelector.module.css';

// ── Remembered choice (per car + track), never required for correct behaviour ──
const storeKey = (vehicle, venue) => `acSetup:${vehicle || '?'}|${venue || '?'}`;

function readSaved(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeSaved(key, value) {
  try {
    if (value) localStorage.setItem(key, JSON.stringify(value));
    else localStorage.removeItem(key);
  } catch {
    // storage unavailable (private mode / quota): the choice just is not remembered
  }
}

const fmtDate = (mtime, lang) => (mtime ? new Date(mtime * 1000).toLocaleString(lang, { dateStyle: 'medium', timeStyle: 'short' }) : '');

function DropZone({ onFile, busy, error }) {
  const { t } = useLanguage();
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);
  const pick = (files) => {
    const f = files?.[0];
    if (f) onFile(f);
  };
  return (
    <div>
      <div
        className={`${s.drop} ${over ? s.dropOver : ''}`}
        role="button"
        tabIndex={0}
        aria-label={t.acsDropAria}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click(); } }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      >
        <Icon name="upload" size={22} />
        <div className={s.dropTitle}>{busy ? t.acsLoadingSetup : t.acsDropTitle}</div>
        <div className={s.dropHint}>{t.acsDropHint}</div>
        <input ref={inputRef} type="file" accept=".ini,.sp" hidden onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
      </div>
      {error && <div className={s.err} role="alert"><Icon name="alert" size={14} />{t.acsUploadError}: {error}</div>}
    </div>
  );
}

/**
 * Finds the Assetto Corsa setup used in a session and asks the user to confirm it.
 * onChange(setup | null, { vehicle, venue }) fires when the decision changes.
 */
export default function SetupSelector({ file, onChange }) {
  const { t, lang } = useLanguage();
  const [phase, setPhase] = useState('loading'); // loading | ask | decided | error
  const [meta, setMeta] = useState(null);
  const [cand, setCand] = useState(null);
  const [chosen, setChosen] = useState(null);
  const [fromMemory, setFromMemory] = useState(false);
  const [mode, setMode] = useState('default'); // default | upload
  const [pendingId, setPendingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [reload, setReload] = useState(0);
  const groupId = useId();
  const onChangeRef = useRef(onChange);
  useEffect(() => { onChangeRef.current = onChange; });

  const decide = useCallback((setup, remembered = false) => {
    setChosen(setup);
    setFromMemory(remembered);
    setPhase('decided');
    setMode('default');
    setErr(null);
  }, []);

  // Detect car/track from the CSV header, look up candidates, restore a remembered choice.
  useEffect(() => {
    if (!file) return undefined;
    let alive = true;
    (async () => {
      setPhase('loading');
      setErr(null);
      try {
        const m = await detectSessionMeta(file);
        const c = await fetchSetupCandidates(m.vehicle, m.venue, lang);
        if (!alive) return;
        setMeta(m);
        setCand(c);
        setPendingId(c.track_setups?.[0]?.id ?? null);
        const saved = readSaved(storeKey(m.vehicle, m.venue));
        let restored;
        if (saved?.kind === 'none') {
          restored = null;
          decide(null, true);
        } else if (saved?.kind === 'track' && c.track_setups?.some((x) => x.id === saved.id)) {
          restored = await fetchSetupById(m.vehicle, m.venue, saved.id, lang);
        } else if (saved?.kind === 'generic' && c.generic_last && c.generic_last.mtime === saved.mtime) {
          restored = await fetchSetupById(m.vehicle, m.venue, c.generic_last.id, lang);
        } else if (saved?.kind === 'upload' && saved.text) {
          restored = await uploadSetup(new File([saved.text], saved.name || 'setup.ini'), m.vehicle, lang);
        }
        if (!alive) return;
        if (restored) decide(restored, true);
        else if (!saved || saved.kind !== 'none') setPhase('ask');
      } catch (e) {
        if (!alive) return;
        setErr(e.message);
        setPhase('error');
      }
    })();
    return () => { alive = false; };
  }, [file, lang, reload, decide]);

  useEffect(() => {
    if (phase === 'decided') onChangeRef.current?.(chosen, meta);
  }, [phase, chosen, meta]);

  const key = storeKey(meta?.vehicle, meta?.venue);

  const confirmRemote = async (id, kind, mtime) => {
    setBusy(true);
    setErr(null);
    try {
      const setup = await fetchSetupById(meta.vehicle, meta.venue, id, lang);
      writeSaved(key, { kind, id, mtime });
      decide(setup);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (f) => {
    setBusy(true);
    setErr(null);
    try {
      const setup = await uploadSetup(f, meta?.vehicle, lang);
      let text = null;
      try { text = await f.text(); } catch { /* remembered choice just won't include the file */ }
      writeSaved(key, text && text.length < 300000 ? { kind: 'upload', name: f.name, text } : null);
      decide(setup);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const chooseNone = () => {
    writeSaved(key, { kind: 'none' });
    decide(null);
  };

  const reopen = () => {
    setPhase('ask');
    setMode(cand?.state === 'track_setups' || cand?.state === 'generic_only' ? 'default' : 'upload');
  };

  if (!file) return null;

  if (phase === 'loading') {
    return <div className={s.bar} role="status"><Icon name="info" size={15} /><span>{t.acsSearching}</span></div>;
  }

  if (phase === 'error') {
    return (
      <div className={`${s.bar} ${s.barWarn}`} role="alert">
        <Icon name="alert" size={15} />
        <span>{t.acsError}{err ? `: ${err}` : ''}</span>
        <button type="button" className="ui-btn ui-btn--sm" onClick={() => setReload((n) => n + 1)}>{t.acsRetry}</button>
      </div>
    );
  }

  if (phase === 'decided') {
    const mismatch = chosen?.car_model && meta?.vehicle && chosen.car_model.toLowerCase() !== meta.vehicle.toLowerCase();
    return (
      <div>
        <div className={s.bar}>
          <Icon name={chosen ? 'check' : 'info'} size={15} />
          {chosen ? (
            <span className={s.barText}>
              <span className={s.barLabel}>{t.acsLinkedLabel}</span>{' '}
              <strong>{t.acsLinked(chosen.name, fmtDate(chosen.mtime, lang))}</strong>
              {fromMemory && <span className={s.barSub}> - {t.acsRemembered}</span>}
            </span>
          ) : (
            <span className={s.barText}>{t.acsNoSetupLinked}</span>
          )}
          <button type="button" className="ui-btn ui-btn--sm" onClick={reopen}>{chosen ? t.acsChange : t.acsChoose}</button>
        </div>
        {mismatch && (
          <div className={s.err} role="alert"><Icon name="alert" size={14} />{t.acsCarMismatch(chosen.car_model, meta.vehicle)}</div>
        )}
      </div>
    );
  }

  // phase === 'ask'
  const trackSetups = cand?.track_setups ?? [];
  const generic = cand?.generic_last;
  const showUpload = mode === 'upload' || cand?.state === 'none' || cand?.state === 'no_access';

  return (
    <Panel icon="file" title={t.acsTitle} subtitle={cand?.reason || undefined}>
      {cand?.state === 'no_access' && (
        <div className={s.explain}>
          <div className={s.explainTitle}>{t.acsNoAccessTitle}</div>
          <p>{t.acsNoAccessBody}</p>
        </div>
      )}

      {!showUpload && cand?.state === 'track_setups' && (
        <fieldset className={s.list} aria-labelledby={`${groupId}-t`}>
          <legend id={`${groupId}-t`} className={s.legend}>{t.acsPickTitle}</legend>
          {trackSetups.map((x) => (
            <label key={x.id} className={`${s.opt} ${pendingId === x.id ? s.optOn : ''}`}>
              <input type="radio" name={groupId} checked={pendingId === x.id} onChange={() => setPendingId(x.id)} />
              <span className={s.optBody}>
                <span className={s.optName}>{x.name}</span>
                <span className={s.optMeta}>{fmtDate(x.mtime, lang)} - {t.acsParamsCount(x.n_params)}</span>
                <span className={s.optChips}>
                  {x.summary.map((c) => <Badge key={c.key} title={c.label}>{c.value}</Badge>)}
                </span>
              </span>
            </label>
          ))}
          <div className={s.actions}>
            <button type="button" className="ui-btn ui-btn--primary" disabled={!pendingId || busy} onClick={() => confirmRemote(pendingId, 'track')}>{t.acsUseSelected}</button>
            <button type="button" className="ui-btn" onClick={() => setMode('upload')}>{t.acsChooseOther}</button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={chooseNone}>{t.acsNone}</button>
          </div>
        </fieldset>
      )}

      {!showUpload && cand?.state === 'generic_only' && generic && (
        <div className={s.card}>
          <div className={s.cardTitle}>{t.acsLastFoundTitle}</div>
          <p className={s.cardQ}>{t.acsLastFoundQ(generic.name, fmtDate(generic.mtime, lang))}</p>
          <div className={s.optChips}>
            {generic.summary.map((c) => <Badge key={c.key} title={c.label}>{c.value}</Badge>)}
          </div>
          <div className={s.actions}>
            <button type="button" className="ui-btn ui-btn--primary" disabled={busy} onClick={() => confirmRemote(generic.id, 'generic', generic.mtime)}>{t.acsYes}</button>
            <button type="button" className="ui-btn" onClick={() => setMode('upload')}>{t.acsChooseOther}</button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={chooseNone}>{t.acsNone}</button>
          </div>
        </div>
      )}

      {showUpload && (
        <>
          <DropZone onFile={handleUpload} busy={busy} error={err} />
          <div className={s.actions}>
            {cand?.state !== 'none' && cand?.state !== 'no_access' && (
              <button type="button" className="ui-btn" onClick={() => setMode('default')}>{t.acsPickTitle}</button>
            )}
            <button type="button" className="ui-btn ui-btn--ghost" onClick={chooseNone}>{t.acsNone}</button>
          </div>
        </>
      )}
      {!showUpload && err && <div className={s.err} role="alert"><Icon name="alert" size={14} />{err}</div>}
    </Panel>
  );
}
