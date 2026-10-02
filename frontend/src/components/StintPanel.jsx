import { useState, useRef, useCallback } from 'react';
import { analyzeStint } from '../api/telemetry';
import { useLanguage } from '../context/LanguageContext';
import LapTimelineChart from './LapTimelineChart';
import PitWindowWidget from './PitWindowWidget';
import CornerAnalysisPanel from './CornerAnalysisPanel';
import SetupRecommendations from './SetupRecommendations';
import { Icon, Panel, Stat, Badge } from './ui';
import css from './StintPanel.module.css';

function sigmaNote(sigma, laps, t) {
  if (!sigma || laps < 3) return null;
  if (sigma < 0.3) return t.stintSigmaNoteVery;
  if (sigma < 0.8) return t.stintSigmaNoteNormal;
  return t.stintSigmaNoteHigh;
}

/** Strip leading decorative glyphs/emoji that legacy i18n strings may carry. */
const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');

function fmtLaptime(s) {
  if (!s || isNaN(s) || s <= 0) return '—';
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(3);
  return `${m}:${sec.padStart(6, '0')}`;
}

export default function StintPanel() {
  const { t } = useLanguage();
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const addFiles = useCallback((newFiles) => {
    const csvs = [...newFiles].filter(f => f.name.toLowerCase().endsWith('.csv'));
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      const fresh = csvs.filter(f => !existing.has(f.name + f.size));
      return [...prev, ...fresh];
    });
  }, []);

  const removeFile = useCallback((idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  const handleFileInput = (e) => {
    addFiles(e.target.files);
    e.target.value = '';
  };

  const isSessionMode = files.length === 1;
  const canAnalyze = isSessionMode || files.length >= 3;
  const steps = t.stintSteps;

  const handleAnalyze = async () => {
    if (!canAnalyze) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setStep(0);

    const stepDelay = (i) => new Promise(r => setTimeout(r, i === 0 ? 80 : 250));

    try {
      for (let i = 0; i < steps.length; i++) {
        setStep(i);
        await stepDelay(i);
      }
      const data = await analyzeStint(files);
      setResult(data);
    } catch (err) {
      setError(err.message || t.errorUnknown);
    } finally {
      setLoading(false);
      setStep(-1);
    }
  };

  const racingLaps = result?.laps?.filter(l => !l.is_pit_lap) ?? [];
  const validTimes = racingLaps.map(l => l.lap_time_s).filter(v => v && !isNaN(v));

  const bestTime = validTimes.length ? Math.min(...validTimes) : null;

  const meanTime = racingLaps.length
    ? racingLaps.reduce((s, l) => s + (l.lap_time_s || 0), 0) / racingLaps.length
    : null;

  const sigma = result?.montecarlo?.sigma_real_s;
  const tasa = result?.degradacion?.tasa_s_per_lap;
  const sigmaTone = sigma == null ? undefined : sigma < 0.3 ? 'ok' : sigma < 0.8 ? 'warn' : 'bad';
  const r2 = result?.degradacion?.r_squared;

  return (
    <div className={css.root}>
      <Panel icon="layers" title={clean(t.stintTitle)}>
        <button
          type="button"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`${css.dropzone} ${dragging ? css.dropzoneActive : ''}`}
        >
          <Icon name="upload" size={24} className={css.dropIcon} />
          <span>
            <span className={css.dropLabel}>{clean(t.stintDropLabel)}</span>
            <span className={css.dropSub}>{clean(t.stintDropSub)}</span>
          </span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          multiple
          className={css.hidden}
          onChange={handleFileInput}
        />

        {files.length > 0 && (
          <>
            {isSessionMode && (
              <div className={css.mode}><Badge tone="accent">{clean(t.stintSessionMode)}</Badge></div>
            )}
            <div className={css.files}>
              {files.map((f, i) => (
                <div key={f.name + f.size} className={css.fileRow}>
                  <span className={css.fileTag}>{isSessionMode ? 'CSV' : `V${i + 1}`}</span>
                  <span className={css.fileName} title={f.name}>{f.name}</span>
                  <span className={css.fileSize}>{(f.size / 1024).toFixed(0)} KB</span>
                  <button type="button" className={css.remove} onClick={() => removeFile(i)} aria-label={t.stintRemoveAria(isSessionMode, i)}>
                    <Icon name="x" size={14} />
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {loading && step >= 0 && (
          <ol className={css.steps} aria-live="polite">
            {steps.map((s, i) => (
              <li
                key={s}
                className={`${css.step} ${i < step ? css.stepDone : i === step ? css.stepActive : ''}`}
              >
                {i < step ? <Icon name="check" size={13} /> : <span className={css.dot} />}
                {clean(s)}
              </li>
            ))}
          </ol>
        )}

        {error && (
          <div className={css.error} role="alert">
            <Icon name="alert" size={16} />
            <div>
              <div className={css.errorTitle}>{clean(t.errorTitle)}</div>
              {error}
            </div>
          </div>
        )}

        <div className={css.actions}>
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={handleAnalyze}
            disabled={!canAnalyze || loading}
            aria-label={isSessionMode && !loading ? t.stintAnalyzeAria('session') : t.stintAnalyzeAria('analyze')}
          >
            {loading
              ? <><span className={css.spin} /> {clean(t.stintProcessing)}</>
              : <><Icon name="activity" size={16} /> {clean(isSessionMode ? t.stintAnalyzeSession : t.stintAnalyzeN(files.length))}</>
            }
          </button>
          {files.length > 1 && files.length < 3 && !loading && (
            <span className={css.hint}>{clean(t.stintNeedMore(3 - files.length))}</span>
          )}
        </div>
      </Panel>

      {result && (
        <>
          <Panel flush>
            <div className={css.kpis}>
              <div className={css.kpi}>
                <Stat
                  label={t.stintKpiTotal}
                  value={racingLaps.length}
                  hint={result.n_laps > racingLaps.length
                    ? t.stintExcluded(result.n_laps - racingLaps.length)
                    : t.stintRacing}
                />
              </div>
              <div className={css.kpi}><Stat label={t.stintKpiBest} value={fmtLaptime(bestTime)} tone="accent" /></div>
              <div className={css.kpi}><Stat label={t.stintKpiMean} value={fmtLaptime(meanTime)} /></div>
              <div className={css.kpi}>
                <Stat
                  label={t.stintKpiDeg}
                  value={tasa != null ? `${tasa > 0 ? '+' : ''}${tasa.toFixed(3)}s` : '—'}
                  hint={t.perLap}
                  tone={tasa != null ? (tasa > 0.1 ? 'bad' : tasa > 0 ? 'warn' : 'ok') : undefined}
                />
              </div>
              <div className={css.kpi}>
                <Stat
                  label={t.stintKpiSigma}
                  value={sigma != null ? `${sigma.toFixed(3)}s` : '—'}
                  hint={sigma == null ? undefined : sigma < 0.3 ? t.stintConsistencyVery : sigma < 0.8 ? t.stintConsistencyNormal : t.stintConsistencyHigh}
                  tone={sigmaTone}
                />
              </div>
            </div>
          </Panel>

          <LapTimelineChart
            degradacion={result.degradacion}
            montecarlo={result.montecarlo}
            laps={result.laps}
          />

          {result.combustible && <PitWindowWidget combustible={result.combustible} />}

          {sigma != null && (
            <Panel>
              <div className={css.note}>
                <Icon name="info" size={16} />
                <div>
                  <div className={css.noteMain}><strong className="num">σ = {sigma.toFixed(3)}s</strong> — {sigmaNote(sigma, result.n_laps, t)}</div>
                  {r2 != null && (
                    <div className={css.noteSub}>
                      <Badge tone={r2 > 0.8 ? 'ok' : r2 > 0.5 ? 'warn' : 'bad'}>R²</Badge>
                      {t.stintRSquared(r2)}
                      {` ${r2 > 0.8 ? t.stintRSquaredExcellent : r2 > 0.5 ? t.stintRSquaredModerate : t.stintRSquaredPoor}`}
                    </div>
                  )}
                </div>
              </div>
            </Panel>
          )}

          {result.curvas_sesion?.available && (
            <CornerAnalysisPanel
              result={{
                corners: result.curvas_sesion.corners,
                setup_advisor: result.setup_sesion,
              }}
              metadata={{
                label_a: `${t.timelineLap} ${result.curvas_sesion.reference_lap} (${t.anomalyReference})`,
                label_b: t.avgOfLaps(result.curvas_sesion.n_laps_compared),
              }}
              sessionMode
              referenceLap={result.curvas_sesion.reference_lap}
              nLaps={result.curvas_sesion.n_laps_compared}
            />
          )}

          {result.setup_sesion?.available && (
            <SetupRecommendations setup_advisor={result.setup_sesion} />
          )}
        </>
      )}
    </div>
  );
}
