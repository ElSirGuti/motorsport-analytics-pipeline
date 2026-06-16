import { useState, useCallback } from 'react';
import { analyzeTelemetry } from '../api/telemetry';
import { useLanguage } from '../context/LanguageContext';
import TimeDeltaChart from './TimeDeltaChart';
import CurvatureMap from './CurvatureMap';
import SectorTable from './SectorTable';
import SpeedChart from './SpeedChart';
import BrakeThrottleChart from './BrakeThrottleChart';
import CornerReport from './CornerReport';
import GGDiagramChart from './GGDiagramChart';
import AnomalyReport from './AnomalyReport';
import PotentialLapCard from './PotentialLapCard';

const LAP_COLORS = ['#00D4FF', '#FF3D3D'];

function FileSlot({ label, color, file, onChange, t }) {
  const [warn, setWarn] = useState(null);
  const id = `adv-${label.replace(/\s+/g, '-')}`;

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!f.name?.toLowerCase().endsWith('.csv')) { setWarn(t.advValidateCsv); e.target.value = ''; return; }
    if (f.size > 100 * 1024 * 1024) { setWarn(t.advValidateSize); e.target.value = ''; return; }
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
          {file ? file.name : t.advNoFile}
        </span>
        <label htmlFor={id} className="lap-choose-btn">
          {file ? t.advChange : t.advChoose}
        </label>
        <input id={id} type="file" accept=".csv" style={{ display: 'none' }} onChange={handleChange} />
      </div>
      {warn && <div className="validation-warn"><span>⚠</span>{warn}</div>}
    </div>
  );
}

function MetaCards({ meta, t }) {
  if (!meta) return null;
  const { driver_fast, driver_slow, vehicle_fast, vehicle_slow,
          venue, delta_total_s, apexes_detected, samples_fast, samples_slow } = meta;

  const sign = delta_total_s > 0 ? '+' : '';
  const deltaColor = delta_total_s > 0 ? 'var(--red)' : 'var(--green)';

  return (
    <div className="summary-grid" style={{ marginBottom: 0 }}>
      <div className="summary-card summary-card--highlight">
        <div className="summary-card__label">{t.advTimeDelta}</div>
        <div className="summary-card__value" style={{ color: deltaColor, fontSize: '2rem' }}>
          {sign}{delta_total_s?.toFixed(3)}s
        </div>
        <div className="summary-card__sub">
          {delta_total_s > 0 ? t.advSlowLoses : t.advSlowGains}
        </div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">{t.advCircuit}</div>
        <div className="summary-card__value" style={{ fontSize: '1.1rem' }}>{venue || '—'}</div>
        <div className="summary-card__sub">{t.advCornersDetected(apexes_detected)}</div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">{t.advFastLap}</div>
        <div className="summary-card__value" style={{ fontSize: '1rem', color: LAP_COLORS[0] }}>
          {driver_fast}
        </div>
        <div className="summary-card__sub">{t.advSamples(vehicle_fast, samples_fast)}</div>
      </div>
      <div className="summary-card">
        <div className="summary-card__label">{t.advSlowLap}</div>
        <div className="summary-card__value" style={{ fontSize: '1rem', color: LAP_COLORS[1] }}>
          {driver_slow}
        </div>
        <div className="summary-card__sub">{t.advSamples(vehicle_slow, samples_slow)}</div>
      </div>
    </div>
  );
}

function ApexTable({ apexes, t }) {
  if (!apexes || apexes.length === 0) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>📍</span> {t.advApexMap}</div>
      </div>
      <div className="sector-table">
        <div className="sector-table__head">
          <span>{t.advApexNumber}</span>
          <span>{t.advApexDistance}</span>
          <span>{t.advApexSpeed}</span>
          <span>{t.advApexThrottle}</span>
          <span>{t.advApexRadius}</span>
          <span>{t.advApexType}</span>
        </div>
        {apexes.map((a, i) => {
          const radio = a.Curvature > 0 ? 1 / a.Curvature : Infinity;
          const tipo = radio > 90 ? t.advCornerTypeFast : radio > 40 ? t.advCornerTypeMedium : t.advCornerTypeSlow;
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

const AdvancedComparePanel = () => {
  const { t } = useLanguage();
  const [lapFast, setLapFast] = useState(null);
  const [lapSlow, setLapSlow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [zoomDomain, setZoomDomain] = useState(null);
  const [activeCorner, setActiveCorner] = useState(null);

  const steps = t.advSteps;

  const handleAnalyze = async () => {
    if (!lapFast || !lapSlow) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setZoomDomain(null);
    setActiveCorner(null);

    for (let i = 0; i < steps.length; i++) {
      setStep(i);
      await new Promise((r) => setTimeout(r, i === 0 ? 80 : 250));
    }

    try {
      const data = await analyzeTelemetry(lapFast, lapSlow, 5);
      setResults(data);
    } catch (err) {
      setError(err.message || t.advUnknownError);
    } finally {
      setLoading(false);
      setStep(-1);
    }
  };

  const deltaData = results
    ? {
        distance: (results.telemetria || []).map((r) => r.Distance),
        delta:    (results.telemetria || []).map((r) => r.Delta_Time),
      }
    : null;

  const speedData = results
    ? {
        distance:  (results.telemetria || []).map((r) => r.Distance),
        speed_a:   (results.telemetria || []).map((r) => r.Speed_Fast),
        speed_b:   (results.telemetria || []).map((r) => r.Speed_Slow),
        lap_labels: { speed_a: results.metadata?.driver_fast || 'Fast', speed_b: results.metadata?.driver_slow || 'Slow' },
      }
    : null;

  const brakeData = results
    ? {
        distance:    (results.telemetria || []).map((r) => r.Distance),
        brake_a:     (results.telemetria || []).map((r) => r.Brake_Fast),
        brake_b:     (results.telemetria || []).map((r) => r.Brake_Slow),
        lap_labels: { brake_a: `${t.brakeThrottleBrake} — ${results.metadata?.driver_fast || t.advFastLap}`, brake_b: `${t.brakeThrottleBrake} — ${results.metadata?.driver_slow || t.advSlowLap}` },
      }
    : null;

  const throttleData = results
    ? {
        distance:      (results.telemetria || []).map((r) => r.Distance),
        throttle_a:    (results.telemetria || []).map((r) => r.Throttle_Fast),
        throttle_b:    (results.telemetria || []).map((r) => r.Throttle_Slow),
        lap_labels: { throttle_a: `${t.brakeThrottleThrottle} — ${results.metadata?.driver_fast || t.advFastLap}`, throttle_b: `${t.brakeThrottleThrottle} — ${results.metadata?.driver_slow || t.advSlowLap}` },
      }
    : null;

  const handleApexClick = useCallback((apex) => {
    const dist = apex?.Distance;
    if (!dist) return;
    setZoomDomain([Math.max(0, dist - 200), dist + 200]);
  }, []);

  const handleCornerClick = useCallback((domain, cornerNum) => {
    setZoomDomain(domain);
    setActiveCorner(cornerNum ?? null);
  }, []);

  return (
    <div>
      {/* ── Upload ── */}
      <section className="section card" aria-label={t.uploadAria}>
        <div className="card__title">
          <span className="card__title-icon">⚡</span>
          {t.advTitle}
        </div>
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem', marginBottom: '1rem', lineHeight: 1.6 }}>
          {t.advDescription}
        </p>

        <div className="lap-list">
          <FileSlot label={t.advFastLabel} color={LAP_COLORS[0]} file={lapFast} onChange={setLapFast} t={t} />
          <FileSlot label={t.advSlowLabel} color={LAP_COLORS[1]} file={lapSlow} onChange={setLapSlow} t={t} />
        </div>

        {loading && step >= 0 && (
          <div className="progress-steps" aria-live="polite">
            {steps.map((s, i) => (
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
              <div className="error-banner__title">{t.advErrorTitle}</div>
              {error}
            </div>
          </div>
        )}

        <button
          className="btn-analyze"
          onClick={handleAnalyze}
          disabled={!lapFast || !lapSlow || loading}
          aria-label={loading ? t.advAnalyzing : t.advRunAnalysis}
        >
          {loading
            ? <><div className="spinner" /> {t.advProcessing}</>
            : t.advRunAnalysis
          }
        </button>
      </section>

      {/* ── Resultados ── */}
      {results && (
        <div className="fade-up">
          <section className="section">
            <MetaCards meta={results.metadata} t={t} />
          </section>

          <section className="section">
            <CurvatureMap curvatura={results.curvatura} apexes={results.apexes} />
          </section>

          <section className="section">
            <ApexTable apexes={results.apexes} t={t} />
          </section>

          <section className="section">
            <SectorTable
              sectores={results.sectores}
              totalDelta={results.metadata?.delta_total_s}
            />
          </section>

          <section className="section">
            <CornerReport
              corners={results.corners}
              onCornerClick={handleCornerClick}
              activeCorner={activeCorner}
              dynamicEvents={results.dynamic_events}
              cornerClusters={results.corner_clusters}
              xgboostPred={results.xgboost_pred}
            />
          </section>

          {(results.gg_diagram || results.g_limit) && (
            <section className="section">
              <GGDiagramChart ggData={results.gg_diagram} gLimit={results.g_limit} />
            </section>
          )}

          {results.dynamic_events && results.dynamic_events.length > 0 && (
            <section className="section">
              <div className="chart-card">
                <div className="chart-header">
                  <div className="chart-title"><span>⚠</span> {t.advUndersteerOversteer}</div>
                  <div className="chart-zoom-badge">{t.advEvents(results.dynamic_events.length)}</div>
                </div>
                <div className="dynamic-events-list">
                  {results.dynamic_events.map((ev, i) => (
                    <div key={i} className={`dynamic-event dynamic-event--${ev.tipo}`}>
                      <div className="dynamic-event__header">
                        <span className="dynamic-event__tipo">
                          {ev.tipo === 'subviraje' ? t.eventSub : t.eventOver}
                        </span>
                        <span className="dynamic-event__curva">{t.eventCorner(ev.curva)}</span>
                        <span className="dynamic-event__dist">{ev.distancia?.toFixed(0)}m</span>
                        <span className={`dynamic-event__severidad dynamic-event__severidad--${ev.severidad}`}>
                          {ev.severidad?.toUpperCase()}
                        </span>
                      </div>
                      <div className="dynamic-event__diagnostico">{ev.diagnostico}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {results.anomaly && (
            <section className="section">
              <AnomalyReport anomaly={results.anomaly} />
            </section>
          )}

          {results.tiempo_potencial && (
            <section className="section">
              <PotentialLapCard
                tiempoPotencial={results.tiempo_potencial}
                xgboostPred={results.xgboost_pred}
                historySamples={results.metadata?.history_samples}
              />
            </section>
          )}

          {zoomDomain && (
            <div className="zoom-bar">
              <span className="zoom-bar__label">
                {t.advZoom(zoomDomain[0], zoomDomain[1])}
                {activeCorner != null && ` ${t.advZoomCorner(zoomDomain[0], zoomDomain[1], activeCorner)}`}
              </span>
              <button className="zoom-reset-btn" onClick={() => { setZoomDomain(null); setActiveCorner(null); }}>
                {t.advFullLap}
              </button>
            </div>
          )}

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
