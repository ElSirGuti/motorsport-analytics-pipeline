import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { annotateRecommendations } from '../api/setups';
import { analyzeSetupSegments } from '../api/telemetry';
import { fileKey } from '../api/files';
import { setLibraryExtra } from '../api/library';
import { Badge, Icon } from './ui';
import SetupSelector from './SetupSelector';
import SetupChangePicker from './SetupChangePicker';
import SetupSegments from './SetupSegments';
import SetupRecommendations from './SetupRecommendations';
import css from './SetupSegments.module.css';

// Setup changes are remembered per telemetry file (name + size + date); never required for correct behaviour.
const changesKey = (file) => `acSetupChanges:${fileKey(file)}`;

function readChanges(file) {
  try {
    const raw = file ? localStorage.getItem(changesKey(file)) : null;
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((c) => Number.isInteger(c?.fromLap) && c?.setup?.params) : [];
  } catch {
    return [];
  }
}

function writeChanges(file, list) {
  try {
    if (list.length) localStorage.setItem(changesKey(file), JSON.stringify(list));
    else localStorage.removeItem(changesKey(file));
  } catch {
    // storage unavailable or full: the changes just are not remembered
  }
}

const sortChanges = (list) => [...list].sort((a, b) => a.fromLap - b.fromLap);

/**
 * Setup advisor + Assetto Corsa setup linking.
 * `file` is the telemetry file of the session (its header tells car and track); `nLaps` the laps found in it.
 * With `nLaps` the user can say the setup changed at some lap: each range of laps is analysed on its own.
 * Without a file the advisor renders exactly as before.
 */
export default function SetupSection({ file, setup_advisor, source, isPilotMode, savedSetup = null, nLaps = 0, laps = null, savedChanges = null }) {
  const { lang, t } = useLanguage();
  const [sel, setSel] = useState({ file: null, setup: null });
  const [annot, setAnnot] = useState(null);
  const [changesState, setChangesState] = useState({ file: null, list: [] });
  const [editing, setEditing] = useState(null);       // null | 'new' | index of the change being edited
  const [seg, setSeg] = useState({ key: null, data: null, error: '' });

  const handleSelect = useCallback((setup) => setSel({ file, setup }), [file]);
  // Without a file (session opened from the library) the setup saved with the session is used.
  const setup = file ? (sel.file === file ? sel.setup : null) : savedSetup;
  const recs = setup_advisor?.recommendations;

  // Changes of the current file (restored from the browser the first time the file is seen).
  const changes = useMemo(() => {
    if (!file) return sortChanges((savedChanges || []).map((c) => ({ fromLap: c.from_lap, setup: c.setup })));
    return changesState.file === file ? changesState.list : sortChanges(readChanges(file));
  }, [file, changesState, savedChanges]);

  const updateChanges = (list) => {
    const sorted = sortChanges(list);
    setChangesState({ file, list: sorted });
    writeChanges(file, sorted);
  };

  // Registers the chosen setups so "Save to library" stores them (and the library can restore them).
  useEffect(() => {
    if (file) setLibraryExtra('setup', setup);
    return () => { if (file) setLibraryExtra('setup', null); };
  }, [file, setup]);
  useEffect(() => {
    if (file) setLibraryExtra('setup_changes', changes.length ? changes.map((c) => ({ from_lap: c.fromLap, setup: c.setup })) : null);
    return () => { if (file) setLibraryExtra('setup_changes', null); };
  }, [file, changes]);

  useEffect(() => {
    if (!setup || !recs?.length || changes.length) return undefined;
    let alive = true;
    annotateRecommendations(setup, recs, lang)
      .then((data) => { if (alive) setAnnot({ setup, recs, data }); })
      .catch(() => { if (alive) setAnnot(null); });
    return () => { alive = false; };
  }, [setup, recs, lang, changes.length]);

  // Pace + advisor of each range between setup changes.
  const splitsKey = changes.map((c) => c.fromLap).join(',');
  const segKey = `${file ? fileKey(file) : ''}|${splitsKey}|${lang}`;
  useEffect(() => {
    if (!file || !splitsKey) return undefined;
    const ctrl = new AbortController();
    analyzeSetupSegments(file, splitsKey.split(',').map(Number), lang, { signal: ctrl.signal })
      .then((data) => setSeg({ key: segKey, data, error: '' }))
      .catch((e) => { if (!ctrl.signal.aborted) setSeg({ key: segKey, data: null, error: e.message }); });
    return () => ctrl.abort();
  }, [file, splitsKey, lang, segKey]);

  const annotated = setup && annot && annot.setup === setup && annot.recs === recs ? annot.data : null;
  const canEdit = !!file && nLaps >= 3;
  const segState = seg.key === segKey ? seg : { key: null, data: null, error: '' };
  const loadingSeg = changes.length > 0 && file && !segState.data && !segState.error;
  const setups = [setup, ...changes.map((c) => c.setup)];

  const onSaveChange = ({ fromLap, setup: chosen }) => {
    const rest = editing === 'new' ? changes : changes.filter((_, i) => i !== editing);
    updateChanges([...rest.filter((c) => c.fromLap !== fromLap), { fromLap, setup: chosen }]);
    setEditing(null);
  };

  return (
    <div>
      {file && (
        <div style={{ marginBottom: 12 }}>
          <SetupSelector file={file} onChange={handleSelect} />
        </div>
      )}

      {(canEdit || changes.length > 0) && (
        <div className={css.root} style={{ marginTop: 0, marginBottom: 12 }} data-testid="setup-changes">
          <div className={css.head}>
            <h4 className={css.title}>{t.ssTitle}</h4>
            {changes.length === 0 && editing == null && <p className={css.help}>{t.ssHelp}</p>}
          </div>
          {changes.length > 0 && (
            <div className={css.changes}>
              {changes.map((c, i) => (
                <div key={c.fromLap} className={css.change}>
                  <strong>{t.ssFromLabel(c.fromLap)}</strong>
                  <Badge tone="accent">{c.setup.name}</Badge>
                  <span className={css.spacer} />
                  {canEdit && (
                    <>
                      <button type="button" className="ui-btn ui-btn--sm" onClick={() => setEditing(i)}>{t.ssEdit}</button>
                      <button type="button" className="ui-btn ui-btn--sm" onClick={() => updateChanges(changes.filter((_, j) => j !== i))}>{t.ssRemove}</button>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
          {canEdit && editing == null && (
            <div>
              <button type="button" className="ui-btn ui-btn--sm" onClick={() => setEditing('new')} data-testid="setup-change-add">
                <Icon name="wrench" size={14} /> {t.ssAdd}
              </button>
            </div>
          )}
          {canEdit && editing != null && (
            <SetupChangePicker
              key={String(editing)}
              file={file}
              nLaps={nLaps}
              laps={laps}
              initial={editing === 'new' ? null : changes[editing]}
              onSave={onSaveChange}
              onCancel={() => setEditing(null)}
            />
          )}
        </div>
      )}

      {changes.length > 0 && file ? (
        <>
          {loadingSeg && <p className={css.help} role="status">{t.ssAnalysing}</p>}
          {segState.error && <p className={css.note} role="alert">{t.ssError}: {segState.error}</p>}
          {segState.data && (
            <SetupSegments segments={segState.data.segments} setups={setups} isPilotMode={isPilotMode} source={source} />
          )}
        </>
      ) : (
        <SetupRecommendations
          setup_advisor={setup_advisor}
          source={source}
          isPilotMode={isPilotMode}
          setup={setup}
          annotated={annotated}
        />
      )}
    </div>
  );
}
