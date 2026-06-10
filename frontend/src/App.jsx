import { useState, useCallback } from 'react';
import SpeedChart from './components/SpeedChart';
import BrakeThrottleChart from './components/BrakeThrottleChart';
import TimeDeltaChart from './components/TimeDeltaChart';
import SummaryCard from './components/SummaryCard';
import CornerReport from './components/CornerReport';
import SessionTab from './components/SessionTab';
import TrackMap from './components/TrackMap';
import { compareLaps } from './api/telemetry';

const LAP_COLORS = ['#00D4FF', '#FF3D3D', '#00E676', '#FFB300', '#FF69B4', '#A78BFA'];
const LAP_LABELS_DEFAULT = ['A (Ref)', 'B', 'C', 'D', 'E', 'F'];

const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;

function validateCsvFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    return `"${file.name}" no es un archivo CSV.`;
  }
  if (file.size > MAX_FILE_SIZE) {
    return `"${file.name}" supera ${MAX_FILE_SIZE_MB} MB.`;
  }
  return null;
}

function LapRow({ index, file, color, label, onFileSelect, onRemove, isRef }) {
  const id = `lap-input-${index}`;
  const [warn, setWarn] = useState(null);

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const err = validateCsvFile(f);
    if (err) { setWarn(err); e.target.value = ''; return; }
    setWarn(null);
    onFileSelect(index, f);
    e.target.value = '';
  };

  return (
    <>
      <div className={`lap-row ${file ? 'lap-row--loaded' : ''}`}>
        <span
          className="lap-dot"
          style={{ background: color, boxShadow: `0 0 8px ${color}66` }}
        />
        <span className="lap-label">{label}</span>
        <span className={`lap-filename ${file ? '' : 'lap-filename--empty'}`}>
          {file ? file.name : 'Sin archivo'}
        </span>
        <label htmlFor={id} className="lap-choose-btn">
          {file ? 'Cambiar' : 'Elegir'}
        </label>
        <input
          id={id}
          type="file"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={handleChange}
        />
        {!isRef && (
          <button
            className="lap-remove-btn"
            onClick={() => onRemove(index)}
            aria-label={`Quitar vuelta ${label}`}
          >
            ×
          </button>
        )}
      </div>
      {warn && <div className="validation-warn"><span>⚠</span>{warn}</div>}
    </>
  );
}

const ANALYSIS_STEPS = ['Cargando CSV', 'Filtros', 'Alineando', 'Comparando'];

function App() {
  const [activeTab, setActiveTab] = useState('comparison');
  const [laps, setLaps] = useState([null, null]);
  const [loading, setLoading] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(-1);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [zoomDomain, setZoomDomain] = useState(null);
  const [copied, setCopied] = useState(false);
  const [activeCorner, setActiveCorner] = useState(null);

  const setLapFile = useCallback((idx, file) => {
    setLaps((prev) => { const n = [...prev]; n[idx] = file; return n; });
  }, []);

  const removeLap = useCallback((idx) => {
    setLaps((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const addLap = useCallback(() => {
    if (laps.length < 6) setLaps((prev) => [...prev, null]);
  }, [laps.length]);

  const handleCornerClick = useCallback((domain, cornerNum) => {
    setZoomDomain(domain);
    setActiveCorner(cornerNum);
  }, []);

  const resetZoom = useCallback(() => {
    setZoomDomain(null);
    setActiveCorner(null);
  }, []);

  const handleAnalyze = async () => {
    const validLaps = laps.filter(Boolean);
    if (validLaps.length < 2) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setZoomDomain(null);
    setActiveCorner(null);

    // Simulate step progression
    for (let i = 0; i < ANALYSIS_STEPS.length; i++) {
      setAnalysisStep(i);
      await new Promise((r) => setTimeout(r, i === 0 ? 100 : 300));
    }

    try {
      const data = await compareLaps(validLaps[0], validLaps[1]);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Error desconocido al analizar la telemetría.');
    } finally {
      setLoading(false);
      setAnalysisStep(-1);
    }
  };

  const handleCopyReport = () => {
    if (!results?.text_report) return;
    navigator.clipboard.writeText(results.text_report).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 2000); },
      () => { /* clipboard not available — no-op */ }
    );
  };

  const validCount = laps.filter(Boolean).length;

  const lapLabels = {};
  const la = results?.metadata?.label_a;
  const lb = results?.metadata?.label_b;
  laps.forEach((f, i) => {
    if (f) {
      const suffix = String.fromCharCode(97 + i);
      const defaultLabel = LAP_LABELS_DEFAULT[i];
      const smartLabel = i === 0 ? (la || defaultLabel) : i === 1 ? (lb || defaultLabel) : defaultLabel;
      lapLabels[`speed_${suffix}`]    = smartLabel;
      lapLabels[`brake_${suffix}`]    = `Freno — ${smartLabel}`;
      lapLabels[`throttle_${suffix}`] = `Gas — ${smartLabel}`;
    }
  });

  return (
    <div className="app">
      {/* ── Top Bar ── */}
      <div className="topbar">
        <div className="topbar__brand">
          <div className="topbar__logo">⚡</div>
          <span className="topbar__name">Motorsport Analytics</span>
          <span className="topbar__version">v1.1.0</span>
        </div>
        <div className="topbar__status">
          <div className="topbar__status-dot" />
          Sistema Listo
        </div>
      </div>

      {/* ── Hero ── */}
      <div className="hero">
        <div className="hero__eyebrow">
          <span>◉</span>
          Telemetría · Assetto Corsa ACTI
        </div>
        <h1 className="hero__title">El Analista Automatizado</h1>
        <p className="hero__subtitle">
          Compara vueltas, detecta pérdida de tiempo curva a curva y optimiza tu pilotaje con datos de ingeniería de pista.
        </p>

        {/* Tab nav */}
        <div className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'comparison'}
            className={`tab-btn tab-btn--comparison ${activeTab === 'comparison' ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab('comparison')}
          >
            ⚑ Comparar Vueltas
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'session'}
            className={`tab-btn tab-btn--session ${activeTab === 'session' ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab('session')}
          >
            ▦ Sesión Completa
          </button>
        </div>
      </div>

      {/* ── Session Tab ── */}
      {activeTab === 'session' && <SessionTab />}

      {/* ── Comparison Tab ── */}
      {activeTab === 'comparison' && (
        <>
          {/* Upload card */}
          <section className="section card" aria-label="Cargar vueltas">
            <div className="card__title">
              <span className="card__title-icon">▤</span>
              Cargar Archivos de Telemetría
            </div>

            <div className="lap-list">
              {laps.map((file, idx) => (
                <LapRow
                  key={idx}
                  index={idx}
                  file={file}
                  color={LAP_COLORS[idx]}
                  label={idx === 0 ? 'Vuelta A — Referencia' : `Vuelta ${LAP_LABELS_DEFAULT[idx]}`}
                  onFileSelect={setLapFile}
                  onRemove={removeLap}
                  isRef={idx === 0}
                />
              ))}
            </div>

            {laps.length < 6 && (
              <button className="add-lap-btn" onClick={addLap}>
                + Agregar vuelta ({laps.length}/6)
              </button>
            )}

            {/* Analysis step indicators */}
            {loading && analysisStep >= 0 && (
              <div className="progress-steps" aria-live="polite">
                {ANALYSIS_STEPS.map((step, i) => (
                  <div
                    key={step}
                    className={`progress-step ${
                      i < analysisStep
                        ? 'progress-step--done'
                        : i === analysisStep
                        ? 'progress-step--active'
                        : ''
                    }`}
                  >
                    <span className={`progress-step__dot ${i === analysisStep ? 'progress-step__dot--pulse' : ''}`} />
                    {i < analysisStep ? '✓' : ''} {step}
                  </div>
                ))}
              </div>
            )}

            {error && (
              <div className="error-banner" role="alert">
                <span className="error-banner__icon">✕</span>
                <div className="error-banner__text">
                  <div className="error-banner__title">Error de análisis</div>
                  {error}
                </div>
              </div>
            )}

            <button
              className="btn-analyze"
              onClick={handleAnalyze}
              disabled={validCount < 2 || loading}
              aria-label={loading ? 'Analizando...' : `Analizar ${validCount} vueltas`}
            >
              {loading
                ? <><div className="spinner" /> Procesando telemetría...</>
                : `⚡ Analizar ${validCount} Vuelta${validCount !== 1 ? 's' : ''}`
              }
            </button>
          </section>

          {/* Results */}
          {results && (
            <div>
              <SummaryCard summary={results.summary} metadata={results.metadata} />

              {results.track_map && results.track_map.length > 0 && (
                <div className="fade-up fade-up--d1">
                  <TrackMap trackData={results.track_map} />
                </div>
              )}

              {zoomDomain && (
                <div className="zoom-bar">
                  <span className="zoom-bar__label">
                    ⬡ Zoom: {zoomDomain[0].toFixed(0)}m – {zoomDomain[1].toFixed(0)}m
                    {activeCorner != null && ` · Curva ${activeCorner}`}
                  </span>
                  <button className="zoom-reset-btn" onClick={resetZoom}>
                    Vuelta completa ×
                  </button>
                </div>
              )}

              <div className="charts-section fade-up fade-up--d2">
                <SpeedChart
                  data={{ ...results.speed_comparison, lap_labels: lapLabels }}
                  zoomDomain={zoomDomain}
                />
                <BrakeThrottleChart
                  brakeData={{ ...results.brake_comparison, lap_labels: lapLabels }}
                  throttleData={{ ...results.throttle_comparison, lap_labels: lapLabels }}
                  zoomDomain={zoomDomain}
                />
                <TimeDeltaChart data={results.time_delta_series} zoomDomain={zoomDomain} />
              </div>

              <CornerReport
                corners={results.corners}
                onCornerClick={handleCornerClick}
                activeCorner={activeCorner}
              />

              {/* Text Report */}
              <div className="card report-card fade-up fade-up--d5">
                <div className="report-header">
                  <div className="report-title">
                    <span>▤</span>
                    Reporte Técnico — Formato Ingeniero
                  </div>
                  <button
                    className={`copy-btn ${copied ? 'copy-btn--copied' : ''}`}
                    onClick={handleCopyReport}
                    aria-label="Copiar reporte al portapapeles"
                  >
                    {copied ? '✓ Copiado' : '⎘ Copiar'}
                  </button>
                </div>
                <pre className="text-report">{results.text_report}</pre>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;
