import { useState, useCallback } from 'react';
import { analyzeTelemetry } from '../api/telemetry';
import TimeDeltaChart from './TimeDeltaChart';
import CurvatureMap from './CurvatureMap';
import SectorTable from './SectorTable';
import SpeedChart from './SpeedChart';
import BrakeThrottleChart from './BrakeThrottleChart';
import CornerReport from './CornerReport';
import GGDiagramChart from './GGDiagramChart';

const LAP_COLORS = ['#00D4FF', '#FF3D3D'];

function validateCsv(file) {
  if (!file?.name?.toLowerCase().endsWith('.csv')) return 'El archivo debe ser .csv';
  if (file.size > 100 * 1024 * 1024) return 'El archivo supera 100 MB';
  return null;
}

function FileSlot({ label, color, file, onChange }) {
  const [warn, setWarn] = useState(null);
  const id = `adv-${label.replace(/\s+/g, '-')}`;

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const err = validateCsv(f);
    if (err) { setWarn(err); e.target.value = ''; return; }
    setWarn(null);
    onChange(f);
    e.target.value = '';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div className="lap-row" style={{ border: file ? `1px solid ${color}44` : undefined }}>
        <span className="lap-dot" style={{ background: color, boxShadow: `0 0 8px ${color}66` }} />
        <span className="lap-label">{label}</span>
        <span className={`lap-filename ${file ? '' : 'lap-filename--empty'}`}>
          {file ? file.name : 'Sin archivo'}
        </span>
        <label htmlFor={id} className="lap-choose-btn">
          {file ? 'Cambiar' : 'Elegir'}
        </label>
        <input id={id} type="file" accept=".csv" style={{ display: 'none' }} onChange={handleChange} />
      </div>
      {warn && <div className="validation-warn"><span>⚠</span>{warn}</div>}
    </div>
  );
}

/* ── Tarjetas de metadatos ─────────────────────────────────── */
function MetaCards({ meta }) {
  if (!meta) return null;
  const { driver_fast, driver_slow, vehicle_fast, vehicle_slow,
          venue, delta_total_s, apexes_detected, samples_fast, samples_slow } = meta;

  const sign = delta_total_s > 0 ? '+' : '';
  const deltaColor = delta_total_s > 0 ? 'var(--red)' : 'var(--green)';

  return (
    <div className="summary-grid" style={{ marginBottom: 0 }}>
      <div className="summary-card summary-card--highlight">
        <div className="summary-card__label">⏱ Time Delta Total</div>
        <div className="summary-card__value" style={{ color: deltaColor, fontSize: '2rem' }}>
          {sign}{delta_total_s?.toFixed(3)}s
        </div>
        <div className="summary-card__sub">
          {delta_total_s > 0 ? 'Vuelta lenta pierde tiempo' : 'Vuelta lenta recupera tiempo'}
        </div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">🏁 Circuito</div>
        <div className="summary-card__value" style={{ fontSize: '1.1rem' }}>{venue || '—'}</div>
        <div className="summary-card__sub">{apexes_detected} curvas detectadas</div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">🔵 Vuelta Rápida</div>
        <div className="summary-card__value" style={{ fontSize: '1rem', color: LAP_COLORS[0] }}>
          {driver_fast}
        </div>
        <div className="summary-card__sub">{vehicle_fast} · {samples_fast} muestras</div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">🔴 Vuelta Lenta</div>
        <div className="summary-card__value" style={{ fontSize: '1rem', color: LAP_COLORS[1] }}>
          {driver_slow}
        </div>
        <div className="summary-card__sub">{vehicle_slow} · {samples_slow} muestras</div>
      </div>
    </div>
  );
}

/* ── Tabla de Apexes ───────────────────────────────────────── */
function ApexTable({ apexes }) {
  if (!apexes || apexes.length === 0) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>📍</span> Mapa de Curvas Detectadas</div>
      </div>
      <div className="sector-table">
        <div className="sector-table__head">
          <span>#</span>
          <span>Distancia</span>
          <span>V-Apex</span>
          <span>Throttle</span>
          <span>Radio</span>
          <span>Tipo</span>
        </div>
        {apexes.map((a, i) => {
          const radio = a.Curvature > 0 ? 1 / a.Curvature : Infinity;
          const tipo = radio > 90 ? 'Rápida' : radio > 40 ? 'Media' : 'Lenta';
          const tipoColor = radio > 90 ? 'var(--green)' : radio > 40 ? '#FFB300' : 'var(--red)';
          return (
            <div key={i} className="sector-row">
              <span className="sector-row__num">{i + 1}</span>
              <span className="sector-row__desc">{a.Distance?.toFixed(0)}m</span>
              <span className="sector-row__dist">{a.Speed?.toFixed(1)} km/h</span>
              <span className="sector-row__dist">{a.Throttle?.toFixed(1)}%</span>
              <span className="sector-row__dist">{isFinite(radio) ? radio.toFixed(0) + 'm' : '∞'}</span>
              <span className="sector-row__delta" style={{ color: tipoColor }}>{tipo}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Panel principal ────────────────────────────────────────── */
const STEPS = ['Cargando CSVs', 'Geometría de pista', 'Time Delta',
                'Círculo fricción', 'Eventos dinámicos', 'Compresión'];

const AdvancedComparePanel = () => {
  const [lapFast, setLapFast] = useState(null);
  const [lapSlow, setLapSlow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [zoomDomain, setZoomDomain] = useState(null);

  const handleAnalyze = async () => {
    if (!lapFast || !lapSlow) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setZoomDomain(null);

    for (let i = 0; i < STEPS.length; i++) {
      setStep(i);
      await new Promise((r) => setTimeout(r, i === 0 ? 80 : 250));
    }

    try {
      const data = await analyzeTelemetry(lapFast, lapSlow, 5);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Error desconocido');
    } finally {
      setLoading(false);
      setStep(-1);
    }
  };

  /* Adaptar datos al formato esperado por TimeDeltaChart */
  const deltaData = results
    ? {
        distance: (results.telemetria || []).map((r) => r.Distance),
        delta:    (results.telemetria || []).map((r) => r.Delta_Time),
      }
    : null;

  /* Adaptar datos de velocidad al formato de SpeedChart */
  const speedData = results
    ? {
        distance:  (results.telemetria || []).map((r) => r.Distance),
        speed_a:   (results.telemetria || []).map((r) => r.Speed_Fast),
        speed_b:   (results.telemetria || []).map((r) => r.Speed_Slow),
        lap_labels: { speed_a: results.metadata?.driver_fast || 'Rápida', speed_b: results.metadata?.driver_slow || 'Lenta' },
      }
    : null;

  /* Adaptar datos de pedales */
  const brakeData = results
    ? {
        distance:    (results.telemetria || []).map((r) => r.Distance),
        brake_a:     (results.telemetria || []).map((r) => r.Brake_Fast),
        brake_b:     (results.telemetria || []).map((r) => r.Brake_Slow),
        lap_labels: { brake_a: `Freno — ${results.metadata?.driver_fast || 'Rápida'}`, brake_b: `Freno — ${results.metadata?.driver_slow || 'Lenta'}` },
      }
    : null;

  const throttleData = results
    ? {
        distance:      (results.telemetria || []).map((r) => r.Distance),
        throttle_a:    (results.telemetria || []).map((r) => r.Throttle_Fast),
        throttle_b:    (results.telemetria || []).map((r) => r.Throttle_Slow),
        lap_labels: { throttle_a: `Gas — ${results.metadata?.driver_fast || 'Rápida'}`, throttle_b: `Gas — ${results.metadata?.driver_slow || 'Lenta'}` },
      }
    : null;

  const handleApexClick = useCallback((apex, idx) => {
    const dist = apex.Distance;
    if (!dist) return;
    setZoomDomain([Math.max(0, dist - 200), dist + 200]);
  }, []);

  return (
    <div>
      {/* ── Upload ── */}
      <section className="section card" aria-label="Análisis avanzado">
        <div className="card__title">
          <span className="card__title-icon">⚡</span>
          Análisis Avanzado — Geometría + Time Delta
        </div>
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem', marginBottom: '1rem', lineHeight: 1.6 }}>
          Carga la <strong>vuelta rápida</strong> (referencia) y la <strong>vuelta lenta</strong>.
          El motor aplicará Savitzky-Golay, detectará Apexes con curvatura dinámica y calculará
          el Time Delta acumulado metro a metro.
        </p>

        <div className="lap-list">
          <FileSlot label="Vuelta Rápida — Referencia" color={LAP_COLORS[0]} file={lapFast} onChange={setLapFast} />
          <FileSlot label="Vuelta Lenta — Comparar" color={LAP_COLORS[1]} file={lapSlow} onChange={setLapSlow} />
        </div>

        {loading && step >= 0 && (
          <div className="progress-steps" aria-live="polite">
            {STEPS.map((s, i) => (
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
          disabled={!lapFast || !lapSlow || loading}
          aria-label={loading ? 'Analizando...' : 'Ejecutar análisis avanzado'}
        >
          {loading
            ? <><div className="spinner" /> Procesando geometría...</>
            : '⚡ Ejecutar Análisis Avanzado'
          }
        </button>
      </section>

      {/* ── Resultados ── */}
      {results && (
        <div className="fade-up">
          {/* Metadatos */}
          <section className="section">
            <MetaCards meta={results.metadata} />
          </section>

          {/* Huella de curvatura */}
          <section className="section">
            <CurvatureMap curvatura={results.curvatura} apexes={results.apexes} />
          </section>

          {/* Tabla de Apexes */}
          <section className="section">
            <ApexTable apexes={results.apexes} onApexClick={handleApexClick} />
          </section>

          {/* Sectorización */}
          <section className="section">
            <SectorTable
              sectores={results.sectores}
              totalDelta={results.metadata?.delta_total_s}
            />
          </section>

          {/* Insights Automatizados (Corner Report) */}
          <section className="section">
            <CornerReport
              corners={results.corners}
              onCornerClick={handleApexClick}
              activeCorner={null}
              dynamicEvents={results.dynamic_events}
            />
          </section>

          {/* Diagrama G-G */}
          {(results.gg_diagram || results.g_limit) && (
            <section className="section">
              <GGDiagramChart ggData={results.gg_diagram} gLimit={results.g_limit} />
            </section>
          )}

          {/* Eventos Dinámicos */}
          {results.dynamic_events && results.dynamic_events.length > 0 && (
            <section className="section">
              <div className="chart-card">
                <div className="chart-header">
                  <div className="chart-title"><span>⚠</span> Eventos de Subviraje y Sobreviraje</div>
                  <div className="chart-zoom-badge">{results.dynamic_events.length} eventos</div>
                </div>
                <div className="dynamic-events-list">
                  {results.dynamic_events.map((ev, i) => (
                    <div key={i} className={`dynamic-event dynamic-event--${ev.tipo}`}>
                      <div className="dynamic-event__header">
                        <span className="dynamic-event__tipo">
                          {ev.tipo === 'subviraje' ? 'SUB' : 'OVER'}
                        </span>
                        <span className="dynamic-event__curva">Curva {ev.curva}</span>
                        <span className="dynamic-event__dist">{ev.distancia.toFixed(0)}m</span>
                        <span className={`dynamic-event__severidad dynamic-event__severidad--${ev.severidad}`}>
                          {ev.severidad.toUpperCase()}
                        </span>
                      </div>
                      <div className="dynamic-event__diagnostico">{ev.diagnostico}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Controles de Zoom */}
          {zoomDomain && (
            <div className="zoom-bar">
              <span className="zoom-bar__label">
                ⬡ Zoom: {zoomDomain[0].toFixed(0)}m – {zoomDomain[1].toFixed(0)}m
              </span>
              <button className="zoom-reset-btn" onClick={() => setZoomDomain(null)}>
                Vuelta completa ×
              </button>
            </div>
          )}

          {/* Gráficas */}
          <div className="charts-section">
            <TimeDeltaChart data={deltaData} zoomDomain={zoomDomain} />
            {speedData && <SpeedChart data={speedData} zoomDomain={zoomDomain} />}
            {brakeData && throttleData && (
              <BrakeThrottleChart
                brakeData={brakeData}
                throttleData={throttleData}
                zoomDomain={zoomDomain}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdvancedComparePanel;
