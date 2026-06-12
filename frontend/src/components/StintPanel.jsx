import React, { useState, useRef, useCallback } from 'react';
import { analyzeStint } from '../api/telemetry';
import LapTimelineChart from './LapTimelineChart';
import PitWindowWidget from './PitWindowWidget';

const STINT_STEPS = ['Cargando vueltas', 'Extrayendo métricas', 'Analizando degradación', 'Simulación Monte Carlo'];

function sigmaNote(sigma, laps) {
  if (!sigma || laps < 3) return null;
  if (sigma < 0.3) return 'Piloto muy consistente. Las proyecciones son altamente fiables.';
  if (sigma < 0.8) return 'Consistencia normal de carrera. Las bandas MC reflejan variación típica de stint.';
  return 'Alta variabilidad entre vueltas. Las bandas de proyección son amplias — revisar factores externos (tráfico, errores).';
}

function KpiCard({ label, value, sub, accent }) {
  return (
    <div className="stint-kpi">
      <div className="stint-kpi__label">{label}</div>
      <div className="stint-kpi__value" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="stint-kpi__sub">{sub}</div>}
    </div>
  );
}

export default function StintPanel() {
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

  const handleAnalyze = async () => {
    if (!canAnalyze) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setStep(0);

    const stepDelay = (i) => new Promise(r => setTimeout(r, i === 0 ? 80 : 250));

    try {
      for (let i = 0; i < STINT_STEPS.length; i++) {
        setStep(i);
        await stepDelay(i);
      }
      const data = await analyzeStint(files);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Error desconocido al analizar el stint.');
    } finally {
      setLoading(false);
      setStep(-1);
    }
  };

  const racingLaps = result?.laps?.filter(l => !l.is_pit_lap) ?? [];

  const bestTime = racingLaps.length
    ? Math.min(...racingLaps.map(l => l.lap_time_s).filter(t => t && !isNaN(t)))
    : null;

  const meanTime = racingLaps.length
    ? racingLaps.reduce((s, l) => s + (l.lap_time_s || 0), 0) / racingLaps.length
    : null;

  function fmtLaptime(s) {
    if (!s || isNaN(s) || s <= 0) return '—';
    const m = Math.floor(s / 60);
    const sec = (s % 60).toFixed(3);
    return `${m}:${sec.padStart(6, '0')}`;
  }

  const sigma = result?.montecarlo?.sigma_real_s;
  const tasa = result?.degradacion?.tasa_s_per_lap;

  return (
    <div className="section">
      {/* Upload card */}
      <div className="card" style={{ marginBottom: 'var(--s4)' }}>
        <div className="card__title">
          <span className="card__title-icon">◉</span>
          Análisis de Stint — Degradación y Estrategia
        </div>

        {/* Dropzone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className="dropzone"
          style={{
            borderColor: dragging ? 'var(--green)' : undefined,
            background: dragging ? 'var(--green-dim)' : undefined,
            cursor: 'pointer',
            marginBottom: files.length ? 'var(--s3)' : 0,
          }}
        >
          <div className="dropzone__icon">◎</div>
          <div className="dropzone__label">Arrastra los CSVs de telemetría aquí</div>
          <div className="dropzone__sub">
            Un CSV de sesión completa · o varios CSVs (mínimo 3) en orden cronológico
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileInput}
        />

        {/* File list */}
        {files.length > 0 && (
          <div className="stint-file-list">
            {isSessionMode && (
              <div style={{
                fontSize: '0.7rem', color: 'var(--cyan)', fontFamily: "'JetBrains Mono', monospace",
                padding: '4px 8px', marginBottom: 4,
                background: 'var(--cyan-dim)', borderRadius: 4, border: '1px solid var(--cyan-border)',
              }}>
                ◎ Modo sesión — las vueltas se segmentarán automáticamente
              </div>
            )}
            {files.map((f, i) => (
              <div key={i} className="stint-file-row">
                <span className="stint-file-row__num">{isSessionMode ? '◉' : `V${i + 1}`}</span>
                <span className="stint-file-row__name" title={f.name}>{f.name}</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {(f.size / 1024).toFixed(0)} KB
                </span>
                <button className="stint-file-row__remove" onClick={(e) => { e.stopPropagation(); removeFile(i); }} aria-label={`Quitar ${isSessionMode ? 'sesión' : `vuelta ${i + 1}`}`}>
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Progress steps */}
        {loading && step >= 0 && (
          <div className="progress-steps" aria-live="polite">
            {STINT_STEPS.map((s, i) => (
              <div
                key={s}
                className={`progress-step ${i < step ? 'progress-step--done' : i === step ? 'progress-step--active' : ''}`}
              >
                <span className={`progress-step__dot ${i === step ? 'progress-step__dot--pulse' : ''}`} />
                {i < step ? '✓' : ''} {s}
              </div>
            ))}
          </div>
        )}

        {/* Error */}
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
          disabled={!canAnalyze || loading}
          aria-label={loading ? 'Analizando stint...' : isSessionMode ? 'Analizar sesión completa' : `Analizar ${files.length} vueltas`}
        >
          {loading
            ? <><div className="spinner" /> Procesando stint...</>
            : isSessionMode
              ? '◉ Analizar Sesión Completa'
              : `◉ Analizar Stint · ${files.length} Vuelta${files.length !== 1 ? 's' : ''}`
          }
        </button>

        {files.length > 1 && files.length < 3 && !loading && (
          <div style={{ marginTop: 8, fontSize: '0.72rem', color: 'var(--amber)',
            fontFamily: "'JetBrains Mono', monospace", textAlign: 'center' }}>
            Agrega {3 - files.length} vuelta{3 - files.length !== 1 ? 's' : ''} más para habilitar el análisis
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="fade-up">
          {/* KPI grid */}
          <div className="stint-kpi-grid">
            <KpiCard
              label="Total Vueltas"
              value={racingLaps.length}
              sub={result.n_laps > racingLaps.length
                ? `${result.n_laps - racingLaps.length} pit/outlier excluidas`
                : 'en carrera'}
            />
            <KpiCard
              label="Mejor Tiempo"
              value={fmtLaptime(bestTime)}
              accent="var(--cyan)"
            />
            <KpiCard
              label="Tiempo Medio"
              value={fmtLaptime(meanTime)}
            />
            <KpiCard
              label="Degradación"
              value={tasa != null ? `${tasa > 0 ? '+' : ''}${tasa.toFixed(3)}s` : '—'}
              sub="por vuelta"
              accent={tasa != null ? (tasa > 0.1 ? 'var(--red)' : tasa > 0 ? 'var(--amber)' : 'var(--green)') : undefined}
            />
            <KpiCard
              label="σ Consistencia"
              value={sigma != null ? `${sigma.toFixed(3)}s` : '—'}
              sub={sigma < 0.3 ? 'Muy consistente' : sigma < 0.8 ? 'Normal' : 'Alta variación'}
              accent="var(--purple)"
            />
          </div>

          {/* Timeline chart */}
          <div style={{ marginBottom: 'var(--s4)' }}>
            <LapTimelineChart
              degradacion={result.degradacion}
              montecarlo={result.montecarlo}
              laps={result.laps}
            />
          </div>

          {/* Pit window */}
          {result.combustible && (
            <PitWindowWidget combustible={result.combustible} />
          )}

          {/* Sigma note */}
          {sigma != null && (
            <div className="stint-sigma-note">
              <strong>σ = {sigma.toFixed(3)}s</strong> — {sigmaNote(sigma, result.n_laps)}
              {result.degradacion?.r_squared != null && (
                <span style={{ display: 'block', marginTop: 4, color: 'var(--text-3)', fontSize: '0.72rem' }}>
                  R² del modelo de degradación: {result.degradacion.r_squared.toFixed(3)}
                  {result.degradacion.r_squared > 0.8 ? ' — ajuste excelente' : result.degradacion.r_squared > 0.5 ? ' — ajuste moderado' : ' — baja correlación, ruido alto'}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
