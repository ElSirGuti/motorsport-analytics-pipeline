import { useCallback, useEffect, useRef, useState } from 'react';
import { useLanguage } from '../../context/LanguageContext';
import { Icon } from '../ui';
import {
  fingerprintFile, getLibraryExtras, libraryFacets, saveToLibrary, sniffMetadata,
} from '../../api/library';
import css from './Library.module.css';

const AUTO_KEY = 'library.autosave';

function readAuto() {
  try { return localStorage.getItem(AUTO_KEY) === '1'; } catch { return false; }
}
function writeAuto(v) {
  try { localStorage.setItem(AUTO_KEY, v ? '1' : '0'); } catch { /* sin almacenamiento: solo esta sesion */ }
}

const stripExt = (name) => String(name || '').replace(/\.[^.]+$/, '');
const EMPTY = { title: '', venue: '', vehicle: '', driver: '' };

/**
 * Boton "Guardar en biblioteca" de la barra de archivo, con formulario (titulo, circuito, coche,
 * piloto) y opcion de guardado automatico tras analizar.
 */
export default function SaveToLibrary({ file, sessionResult, stintResult }) {
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [facets, setFacets] = useState(null);
  const [auto, setAuto] = useState(readAuto);
  // El estado de guardado pertenece a un resultado concreto: al analizar de nuevo vuelve a "idle".
  const [save, setSave] = useState({ for: null, status: 'idle', error: '' });
  const status = save.for === sessionResult ? save.status : 'idle';
  const error = save.for === sessionResult ? save.error : '';
  const wrapRef = useRef(null);
  const metaRef = useRef({ file: null, promise: null });

  const getMeta = useCallback(() => {
    if (metaRef.current.file !== file) {
      metaRef.current = {
        file,
        promise: sniffMetadata(file).catch(() => ({})),
      };
    }
    return metaRef.current.promise;
  }, [file]);

  const defaults = useCallback(async () => {
    const m = await getMeta();
    const name = stripExt(file.name);
    return {
      title: m.venue && m.vehicle ? `${m.venue} · ${m.vehicle}` : name,
      venue: m.venue || '',
      vehicle: m.vehicle || '',
      driver: m.driver || '',
    };
  }, [file, getMeta]);

  const doSave = useCallback(async (values) => {
    setSave({ for: sessionResult, status: 'saving', error: '' });
    try {
      const sha = await fingerprintFile(file);
      const res = await saveToLibrary({
        title: values.title || stripExt(file.name),
        venue: values.venue || null,
        vehicle: values.vehicle || null,
        driver: values.driver || null,
        source_filename: file.name,
        file_sha256: sha,
        payload: { session: sessionResult, stint: stintResult, extras: getLibraryExtras() },
      }, lang);
      setSave({ for: sessionResult, status: res.duplicate ? 'updated' : 'saved', error: '' });
      return true;
    } catch (e) {
      const msg = e.code === 'network' ? t.libErrNetwork : e.message;
      setSave({ for: sessionResult, status: 'error', error: msg });
      return false;
    }
  }, [file, sessionResult, stintResult, lang, t]);

  // Guardado automatico: una vez por resultado nuevo (la primera instruccion es un await,
  // no se cambia el estado de forma sincrona dentro del efecto).
  const autoDone = useRef(null);
  useEffect(() => {
    if (!auto || !file || !sessionResult || autoDone.current === sessionResult) return;
    autoDone.current = sessionResult;
    (async () => {
      const values = await defaults();
      await doSave(values);
    })();
  }, [auto, file, sessionResult, defaults, doSave]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const openForm = async () => {
    const next = !open;
    setOpen(next);
    if (!next) return;
    libraryFacets().then(setFacets).catch(() => setFacets(null));
    const d = await defaults();
    setForm((f) => ({
      title: f.title || d.title, venue: f.venue || d.venue,
      vehicle: f.vehicle || d.vehicle, driver: f.driver || d.driver,
    }));
  };

  const submit = async (e) => {
    e.preventDefault();
    const ok = await doSave(form);
    if (ok) setOpen(false);
  };

  const toggleAuto = (v) => { setAuto(v); writeAuto(v); };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const busy = status === 'saving';

  const label = busy ? t.libSaving
    : status === 'saved' ? t.libSaved
      : status === 'updated' ? t.libSavedUpdated
        : t.libSave;
  const icon = status === 'saved' || status === 'updated' ? 'check' : 'layers';

  return (
    <div className={css.saveWrap} ref={wrapRef}>
      <button
        type="button"
        className={`ui-btn ui-btn--sm${status === 'saved' || status === 'updated' ? ` ${css.btnOk}` : ''}`}
        onClick={openForm}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={busy}
        title={status === 'updated' ? t.libDuplicateHint : undefined}
      >
        {busy ? <span className="shell-spin" /> : <Icon name={icon} size={14} />}
        {label}
      </button>
      {status === 'error' && !open && (
        <span className={css.inlineErr} role="alert" title={error}>{t.libSaveFailed}</span>
      )}

      {open && (
        <form className={css.pop} role="dialog" aria-label={t.libSave} onSubmit={submit}>
          <div className={css.popTitle}>{t.libSaveTitle}</div>
          <label className={css.field}>
            <span>{t.libFieldTitle}</span>
            <input className={css.input} value={form.title} onChange={set('title')} maxLength={200} required />
          </label>
          <div className={css.fieldRow}>
            <label className={css.field}>
              <span>{t.libFieldVenue}</span>
              <input className={css.input} value={form.venue} onChange={set('venue')} list="lib-venues" maxLength={160} />
            </label>
            <label className={css.field}>
              <span>{t.libFieldVehicle}</span>
              <input className={css.input} value={form.vehicle} onChange={set('vehicle')} list="lib-vehicles" maxLength={160} />
            </label>
          </div>
          <label className={css.field}>
            <span>{t.libFieldDriver}</span>
            <input className={css.input} value={form.driver} onChange={set('driver')} maxLength={160} />
          </label>
          <datalist id="lib-venues">{facets?.venues?.map((v) => <option key={v.value} value={v.value} />)}</datalist>
          <datalist id="lib-vehicles">{facets?.vehicles?.map((v) => <option key={v.value} value={v.value} />)}</datalist>
          <p className={css.hint}>{t.libSaveHint}</p>
          <label className={css.check}>
            <input type="checkbox" checked={auto} onChange={(e) => toggleAuto(e.target.checked)} />
            <span>{t.libAutoSave}</span>
          </label>
          {status === 'error' && <div className={css.formErr} role="alert">{error}</div>}
          <div className={css.popActions}>
            <button type="button" className="ui-btn ui-btn--sm ui-btn--ghost" onClick={() => setOpen(false)}>{t.libCancel}</button>
            <button type="submit" className="ui-btn ui-btn--sm ui-btn--primary" disabled={busy || !form.title.trim()}>
              {busy ? <span className="shell-spin" /> : <Icon name="check" size={14} />}
              {status === 'saved' || status === 'updated' ? t.libUpdate : t.libSave}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
