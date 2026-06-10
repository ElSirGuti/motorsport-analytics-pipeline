import React, { useState, useCallback, useRef } from 'react';
import SpeedChart from './components/SpeedChart';
import BrakeThrottleChart from './components/BrakeThrottleChart';
import TimeDeltaChart from './components/TimeDeltaChart';
import SummaryCard from './components/SummaryCard';
import CornerReport from './components/CornerReport';
import SessionTab from './components/SessionTab';
import TrackMap from './components/TrackMap';
import { compareLaps } from './api/telemetry';

// ── Palette for the N lap files ──
const LAP_COLORS = ['#00D4FF', '#FF4444', '#00FF88', '#FFAA00', '#FF69B4', '#A78BFA'];
const LAP_LABELS_DEFAULT = ['A (Ref)', 'B', 'C', 'D', 'E', 'F'];

// ── Small file uploader row ──
function LapRow({ index, file, color, label, onFileSelect, onRemove, isRef }) {
  const id = `lap-input-${index}`;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '10px 14px',
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${file ? color + '55' : 'rgba(255,255,255,0.07)'}`,
      borderRadius: '10px',
      transition: 'border-color 0.2s',
    }}>
      <div style={{
        width: 12, height: 12, borderRadius: '50%',
        background: color, flexShrink: 0,
        boxShadow: `0 0 8px ${color}88`,
      }} />
      <span style={{ fontSize: '0.85rem', color: '#94A3B8', minWidth: 90 }}>{label}</span>
      {file
        ? <span style={{ fontSize: '0.82rem', color: '#00FF88', fontFamily: 'monospace', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {file.name}</span>
        : <span style={{ fontSize: '0.82rem', color: '#64748B', flex: 1 }}>Sin archivo</span>
      }
      <label htmlFor={id} style={{ cursor: 'pointer', fontSize: '0.78rem', color: '#00D4FF', background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.25)', borderRadius: '6px', padding: '3px 10px' }}>
        {file ? 'Cambiar' : 'Elegir'}
      </label>
      <input id={id} type="file" accept=".csv" style={{ display: 'none' }}
        onChange={(e) => { if (e.target.files[0]) onFileSelect(index, e.target.files[0]); e.target.value = ''; }}
      />
      {!isRef && (
        <button onClick={() => onRemove(index)}
          style={{ background: 'none', border: 'none', color: '#64748B', cursor: 'pointer', fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}
          title="Quitar vuelta">×</button>
      )}
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('comparison');
  // N laps: each entry is a File or null
  const [laps, setLaps] = useState([null, null]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [zoomDomain, setZoomDomain] = useState(null);
  const [copied, setCopied] = useState(false);
  const [activeCorner, setActiveCorner] = useState(null);

  // ── Lap management ──
  const setLapFile = useCallback((idx, file) => {
    setLaps((prev) => { const n = [...prev]; n[idx] = file; return n; });
  }, []);
  const removeLap = useCallback((idx) => {
    setLaps((prev) => prev.filter((_, i) => i !== idx));
  }, []);
  const addLap = useCallback(() => {
    if (laps.length < 6) setLaps((prev) => [...prev, null]);
  }, [laps.length]);

  // ── Corner zoom toggle ──
  const handleCornerClick = useCallback((domain, cornerNum) => {
    setZoomDomain(domain);
    setActiveCorner(cornerNum);
  }, []);
  const resetZoom = useCallback(() => {
    setZoomDomain(null);
    setActiveCorner(null);
  }, []);

  // ── Analyze ──
  const handleAnalyze = async () => {
    const validLaps = laps.filter(Boolean);
    if (validLaps.length < 2) return;
    setLoading(true);
    setError(null);
    setZoomDomain(null);
    setActiveCorner(null);
    try {
      // Always compare the first two for now; multi-lap backend can be extended later
      const data = await compareLaps(validLaps[0], validLaps[1]);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Error desconocido al analizar la telemetría.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const validCount = laps.filter(Boolean).length;

  // ── Build lap labels for charts (use smart backend labels when available) ──
  const lapLabels = {};
  const la = results?.metadata?.label_a;
  const lb = results?.metadata?.label_b;
  laps.forEach((f, i) => {
    if (f) {
      const suffix = String.fromCharCode(97 + i); // a, b, c …
      const defaultLabel = LAP_LABELS_DEFAULT[i];
      const smartLabel = i === 0 ? (la || defaultLabel) : i === 1 ? (lb || defaultLabel) : defaultLabel;
      lapLabels[`speed_${suffix}`]    = smartLabel;
      lapLabels[`brake_${suffix}`]    = `Freno — ${smartLabel}`;
      lapLabels[`throttle_${suffix}`] = `Gas — ${smartLabel}`;
    }
  });

  return (
    <div className="app">
      <header className="header">
        <div className="header__badge">
          <div className="header__badge-dot" />
          Motorsport Analytics Engine
        </div>
        <h1 className="header__title">El Analista Automatizado</h1>
        <p className="header__subtitle">
          Analiza y compara tus vueltas de telemetría de Assetto Corsa (ACTI) para encontrar tiempo perdido y optimizar tu estilo de conducción.
        </p>

        <div style={{ display: 'flex', gap: '10px', marginTop: '20px', justifyContent: 'center' }}>
          {[
            { key: 'comparison', label: '🏁 Comparar Vueltas', color: '#FF4444' },
            { key: 'session',    label: '📊 Sesión Completa',   color: '#00D4FF' },
          ].map(({ key, label, color }) => (
            <button key={key} onClick={() => setActiveTab(key)} style={{
              padding: '10px 22px',
              backgroundColor: activeTab === key ? color : 'rgba(255,255,255,0.06)',
              color: activeTab === key ? (key === 'comparison' ? '#fff' : '#000') : '#94A3B8',
              border: `1px solid ${activeTab === key ? color : 'rgba(255,255,255,0.1)'}`,
              borderRadius: '8px', cursor: 'pointer', fontWeight: 700,
              fontSize: '0.88rem', letterSpacing: '0.02em',
              transition: 'all 0.2s',
              boxShadow: activeTab === key ? `0 0 16px ${color}55` : 'none',
            }}>
              {label}
            </button>
          ))}
        </div>
      </header>

      <main>
        {activeTab === 'session' && <SessionTab />}

        {activeTab === 'comparison' && (
          <>
            {/* ── File loader ── */}
            <section className="uploader card">
              <h2 className="card__title">
                <span className="card__title-icon">📂</span>
                Cargar Vueltas
              </h2>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                {laps.map((file, idx) => (
                  <LapRow
                    key={idx}
                    index={idx}
                    file={file}
                    color={LAP_COLORS[idx]}
                    label={idx === 0 ? 'Vuelta A (Ref)' : `Vuelta ${LAP_LABELS_DEFAULT[idx]}`}
                    onFileSelect={setLapFile}
                    onRemove={removeLap}
                    isRef={idx === 0}
                  />
                ))}
              </div>

              {laps.length < 6 && (
                <button onClick={addLap} style={{
                  display: 'block', width: '100%', padding: '8px',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px dashed rgba(255,255,255,0.15)',
                  borderRadius: '8px', color: '#64748B',
                  cursor: 'pointer', fontSize: '0.85rem',
                  marginBottom: '16px',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#00D4FF55'; e.currentTarget.style.color = '#00D4FF'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.color = '#64748B'; }}
                >
                  + Agregar vuelta ({laps.length}/6)
                </button>
              )}

              {error && (
                <div className="error-message">⚠️ {error}</div>
              )}

              <button
                className="btn-analyze"
                onClick={handleAnalyze}
                disabled={validCount < 2 || loading}
              >
                {loading ? <div className="spinner" /> : `⚡ Analizar ${validCount} Vuelta${validCount !== 1 ? 's' : ''}`}
              </button>
            </section>

            {/* ── Results ── */}
            {results && (
              <section className="results">
                <SummaryCard summary={results.summary} metadata={results.metadata} />

                {results.track_map && results.track_map.length > 0 && (
                  <TrackMap trackData={results.track_map} />
                )}

                {/* Zoom reset bar */}
                {zoomDomain && (
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    gap: '12px', marginBottom: '1rem',
                    padding: '8px 20px',
                    background: 'rgba(0,212,255,0.07)',
                    border: '1px solid rgba(0,212,255,0.2)',
                    borderRadius: '8px',
                  }}>
                    <span style={{ fontSize: '0.85rem', color: '#00D4FF' }}>
                      🔍 Zoom activo: {zoomDomain[0].toFixed(0)}m – {zoomDomain[1].toFixed(0)}m
                      {activeCorner != null && ` (Curva ${activeCorner})`}
                    </span>
                    <button
                      onClick={resetZoom}
                      style={{
                        padding: '4px 14px', background: 'none',
                        color: '#94A3B8', border: '1px solid rgba(255,255,255,0.15)',
                        borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem',
                      }}
                    >
                      ✕ Ver vuelta completa
                    </button>
                  </div>
                )}

                <div className="charts">
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

                <div className="card" style={{ marginTop: '2rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h2 className="card__title" style={{ margin: 0 }}>📄 Reporte en Texto (Formato Ingeniero)</h2>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(results.text_report).then(() => {
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        });
                      }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '6px 14px',
                        background: copied ? 'rgba(0,255,136,0.12)' : 'rgba(255,255,255,0.05)',
                        border: `1px solid ${copied ? 'rgba(0,255,136,0.4)' : 'rgba(255,255,255,0.12)'}`,
                        borderRadius: '8px',
                        color: copied ? '#00FF88' : '#94A3B8',
                        cursor: 'pointer',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        fontFamily: 'var(--font-mono)',
                        letterSpacing: '0.03em',
                        transition: 'all 0.2s',
                        flexShrink: 0,
                      }}
                    >
                      {copied ? '✓ Copiado!' : '⎘ Copiar'}
                    </button>
                  </div>
                  <pre className="text-report">{results.text_report}</pre>
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
