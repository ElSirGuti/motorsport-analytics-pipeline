import React, { useState, useCallback, useRef, useMemo } from 'react';
import SpeedChart from './components/SpeedChart';
import BrakeThrottleChart from './components/BrakeThrottleChart';
import TimeDeltaChart from './components/TimeDeltaChart';
import SummaryCard from './components/SummaryCard';
import CornerReport from './components/CornerReport';
import TrackMap from './components/TrackMap';
import LapTimelineChart from './components/LapTimelineChart';
import PitWindowWidget from './components/PitWindowWidget';
import CurvatureMap from './components/CurvatureMap';
import SectorTable from './components/SectorTable';
import GGDiagramChart from './components/GGDiagramChart';
import AnomalyReport from './components/AnomalyReport';
import PotentialLapCard from './components/PotentialLapCard';
import TyreHeatmap from './components/TyreHeatmap';
import BrakeFadeChart from './components/BrakeFadeChart';
import DriverInputsChart from './components/DriverInputsChart';
import SuspensionChart from './components/SuspensionChart';
import SlipAngleChart from './components/SlipAngleChart';
import { analyzeSession, analyzeStint, compareLaps, analyzeTelemetry, compareSessionLaps } from './api/telemetry';

const MAX_FILE_SIZE = 100 * 1024 * 1024;
const LAP_COLORS = ['#00D4FF', '#FF3D3D', '#00E676', '#FFB300', '#FF69B4', '#A78BFA'];

function fmtTime(s) {
  if (s == null || isNaN(s) || s <= 0) return '—';
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(3);
  return `${m}:${sec.padStart(6, '0')}`;
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

function SessionKPIs({ sessionResult, stintResult }) {
  const laps = sessionResult?.laps ?? [];
  const pitCount = laps.filter(l => l.is_pit_lap).length;
  const racingLaps = stintResult?.laps?.filter(l => !l.is_pit_lap) ?? [];
  const bestTime = sessionResult?.fastest_lap?.lap_time;
  const meanTime = racingLaps.length
    ? racingLaps.reduce((s, l) => s + (l.lap_time_s || 0), 0) / racingLaps.length
    : null;
  const maxSpeed = sessionResult?.fastest_lap?.max_speed;
  const tasa = stintResult?.degradacion?.available ? stintResult.degradacion.tasa_s_per_lap : null;

  return (
    <div className="card" style={{ marginBottom: 'var(--s4)' }}>
      <div className="card__title">
        <span className="card__title-icon">▦</span>
        Resumen de Sesión
      </div>
      <div className="stint-kpi-grid">
        <KpiCard
          label="Vueltas Válidas"
          value={sessionResult.total_laps}
          sub={pitCount > 0 ? `${pitCount} pit/outlier excluidas` : 'en carrera'}
        />
        <KpiCard
          label="Mejor Vuelta"
          value={sessionResult.fastest_lap ? `#${sessionResult.fastest_lap.lap_number}` : '—'}
          sub={fmtTime(bestTime)}
          accent="var(--cyan)"
        />
        <KpiCard label="Tiempo Medio" value={fmtTime(meanTime)} />
        <KpiCard
          label="Vel. Máxima"
          value={maxSpeed ? `${maxSpeed.toFixed(0)} km/h` : '—'}
          sub="en mejor vuelta"
        />
        {tasa != null && (
          <KpiCard
            label="Degradación"
            value={`${tasa > 0 ? '+' : ''}${tasa.toFixed(3)}s`}
            sub="por vuelta"
            accent={tasa > 0.1 ? 'var(--red)' : tasa > 0 ? 'var(--amber)' : 'var(--green)'}
          />
        )}
      </div>
    </div>
  );
}

function SessionLapTable({ laps, fastestLap, selectedLaps, onToggleLap, onCompare, compareLoading, compareError }) {
  const [lapA, lapB] = selectedLaps;
  const canCompare = selectedLaps.length === 2 && !compareLoading;

  return (
    <div className="card" style={{ marginBottom: 'var(--s4)' }}>
      <div className="card__title" style={{ flexWrap: 'wrap', gap: 8 }}>
        <span className="card__title-icon">▤</span>
        Vueltas · Selecciona 2 para comparar
        {selectedLaps.length === 2 && (
          <button
            className="btn-analyze"
            style={{ marginLeft: 'auto', padding: '6px 18px', fontSize: '0.78rem', minHeight: 32 }}
            onClick={onCompare}
            disabled={!canCompare}
          >
            {compareLoading
              ? <><div className="spinner" style={{ width: 12, height: 12 }} /> Comparando...</>
              : `⚡ Comparar V${lapA} vs V${lapB}`
            }
          </button>
        )}
      </div>

      {compareError && (
        <div className="error-banner" role="alert" style={{ marginBottom: 'var(--s3)' }}>
          <span className="error-banner__icon">✕</span>
          <div className="error-banner__text">{compareError}</div>
        </div>
      )}

      {selectedLaps.length === 1 && (
        <div style={{
          fontSize: '0.72rem', color: 'var(--cyan)', fontFamily: "'JetBrains Mono', monospace",
          padding: '4px 8px', marginBottom: 8,
          background: 'var(--cyan-dim)', borderRadius: 4, border: '1px solid var(--cyan-border)',
        }}>
          V{lapA} seleccionada — elige una segunda vuelta para comparar
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table className="session-lap-table">
          <thead>
            <tr>
              <th style={{ width: 36, textAlign: 'center' }}>Sel.</th>
              <th>Vuelta</th>
              <th>Tiempo</th>
              <th>Vel. Máx.</th>
              <th>Distancia</th>
              <th>Δ vs Mejor</th>
            </tr>
          </thead>
          <tbody>
            {laps.map(lap => {
              const isSelected = selectedLaps.includes(lap.lap_number);
              const selIdx = selectedLaps.indexOf(lap.lap_number);
              const delta = fastestLap && !lap.is_fastest
                ? lap.lap_time - fastestLap.lap_time
                : null;
              const isPit = lap.is_pit_lap;

              return (
                <tr
                  key={lap.lap_number}
                  onClick={() => !isPit && onToggleLap(lap.lap_number)}
                  className={lap.is_fastest ? 'row-fastest' : ''}
                  style={{
                    cursor: isPit ? 'default' : 'pointer',
                    opacity: isPit ? 0.45 : 1,
                    background: isSelected ? 'rgba(0,212,255,0.07)' : undefined,
                    outline: isSelected ? '1px solid rgba(0,212,255,0.25)' : undefined,
                    transition: 'background 0.12s, opacity 0.12s',
                  }}
                >
                  <td style={{ textAlign: 'center', padding: '6px 8px' }}>
                    {isPit ? (
                      <span style={{ color: '#FF3D3D', fontSize: '0.8rem' }}>🔧</span>
                    ) : (
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        width: 18, height: 18, borderRadius: 3, border: '2px solid',
                        borderColor: isSelected ? 'var(--cyan)' : 'rgba(255,255,255,0.18)',
                        background: isSelected
                          ? (selIdx === 0 ? 'var(--cyan)' : 'rgba(0,212,255,0.35)')
                          : 'transparent',
                        fontSize: '0.6rem', color: selIdx === 0 ? '#000' : 'var(--cyan)',
                        fontWeight: 700, transition: 'all 0.12s',
                      }}>
                        {isSelected ? (selIdx === 0 ? 'A' : 'B') : ''}
                      </span>
                    )}
                  </td>
                  <td className="td-lap-num">
                    {lap.lap_number}
                    {lap.is_fastest && (
                      <span style={{ marginLeft: 6, color: 'var(--cyan)', fontSize: '0.7rem' }}>BEST</span>
                    )}
                    {isPit && (
                      <span style={{ marginLeft: 6, color: '#FF3D3D', fontSize: '0.65rem' }}>PIT</span>
                    )}
                  </td>
                  <td className="td-time">{fmtTime(lap.lap_time)}</td>
                  <td>{lap.max_speed?.toFixed(1) ?? '—'} km/h</td>
                  <td style={{ color: 'var(--text-3)' }}>
                    {lap.lap_distance != null && lap.lap_distance > 0
                      ? `${lap.lap_distance.toFixed(0)} m`
                      : '—'
                    }
                  </td>
                  <td style={{ color: delta != null && delta > 0 ? 'var(--red)' : 'var(--text-3)' }}>
                    {delta != null && delta > 0 ? `+${delta.toFixed(3)}s` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ComparisonSection({ result, comparingLaps, onCornerClick, activeCorner, zoomDomain, fixedDistance, onClearFixed, onChartClick, onResetZoom, copied, onCopyReport }) {
  const meta = result?.metadata;
  const title = comparingLaps
    ? `Vuelta ${comparingLaps[0]} vs Vuelta ${comparingLaps[1]}`
    : meta ? `${meta.label_a ?? 'A'} vs ${meta.label_b ?? 'B'}` : 'Comparación de Telemetría';

  const lapLabels = useMemo(() => {
    if (!meta) return {};
    const la = meta.label_a ?? 'A';
    const lb = meta.label_b ?? 'B';
    return {
      speed_a: la, speed_b: lb,
      brake_a: `Freno — ${la}`, brake_b: `Freno — ${lb}`,
      throttle_a: `Gas — ${la}`, throttle_b: `Gas — ${lb}`,
    };
  }, [meta]);

  return (
    <div className="fade-up">
      <div style={{
        padding: 'var(--s4) 0',
        borderTop: '2px solid var(--border-1)',
        marginBottom: 'var(--s4)',
      }}>
        <div className="hero__eyebrow" style={{ marginBottom: 4 }}>
          <span>⚡</span> Comparación de Telemetría
        </div>
        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-1)' }}>{title}</div>
        {meta?.venue && (
          <div style={{ color: 'var(--text-3)', fontSize: '0.8rem', marginTop: 4 }}>{meta.venue}</div>
        )}
      </div>

      <SummaryCard summary={result.summary} metadata={result.metadata} />

      {result.track_map?.length > 0 && (
        <div className="fade-up fade-up--d1" style={{ marginTop: 'var(--s4)' }}>
          <TrackMap
            trackData={result.track_map}
            fixedDistance={fixedDistance}
            onClearFixed={onClearFixed}
          />
        </div>
      )}

      {zoomDomain && (
        <div className="zoom-bar">
          <span className="zoom-bar__label">
            ⬡ Zoom: {zoomDomain[0].toFixed(0)}m – {zoomDomain[1].toFixed(0)}m
            {activeCorner != null && ` · Curva ${activeCorner}`}
          </span>
          <button className="zoom-reset-btn" onClick={onResetZoom}>Vuelta completa ×</button>
        </div>
      )}

      <div className="charts-section fade-up fade-up--d2" style={{ marginTop: 'var(--s4)' }}>
        <SpeedChart
          data={{ ...result.speed_comparison, lap_labels: lapLabels }}
          zoomDomain={zoomDomain}
          onChartClick={onChartClick}
        />
        <BrakeThrottleChart
          brakeData={{ ...result.brake_comparison, lap_labels: lapLabels }}
          throttleData={{ ...result.throttle_comparison, lap_labels: lapLabels }}
          zoomDomain={zoomDomain}
          onChartClick={onChartClick}
        />
        <TimeDeltaChart
          data={result.time_delta_series}
          zoomDomain={zoomDomain}
          onChartClick={onChartClick}
        />
      </div>

      <CornerReport
        corners={result.corners}
        onCornerClick={onCornerClick}
        activeCorner={activeCorner}
      />

      {result.dynamic_events && result.dynamic_events.length > 0 && (
        <div className="card fade-up fade-up--d4" style={{ marginTop: 'var(--s4)' }}>
          <div className="card__title">
            <span className="card__title-icon">⚠</span>
            Eventos de Conducción — Subviraje y Sobreviraje
            <span style={{
              marginLeft: 'auto', fontSize: '0.68rem', padding: '3px 8px',
              background: 'rgba(255,61,61,0.1)', color: 'var(--red)',
              border: '1px solid rgba(255,61,61,0.25)', borderRadius: 4,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {result.dynamic_events.length} evento{result.dynamic_events.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="dynamic-events-list">
            {result.dynamic_events.map((ev, i) => (
              <div key={i} className={`dynamic-event dynamic-event--${ev.tipo}`}>
                <div className="dynamic-event__header">
                  <span className="dynamic-event__tipo">
                    {ev.tipo === 'subviraje' ? 'SUB' : 'OVER'}
                  </span>
                  <span className="dynamic-event__curva">Curva {ev.curva}</span>
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
      )}

      {result.curvatura?.length > 0 && (
        <div className="fade-up fade-up--d4" style={{ marginTop: 'var(--s4)' }}>
          <CurvatureMap curvatura={result.curvatura} apexes={result.apexes} />
        </div>
      )}

      {result.sectores?.length > 0 && (
        <div className="fade-up fade-up--d4" style={{ marginTop: 'var(--s4)' }}>
          <SectorTable
            sectores={result.sectores}
            totalDelta={result.metadata?.delta_total_s ?? result.summary?.total_time_delta}
          />
        </div>
      )}

      {(result.gg_diagram || result.g_limit) && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <GGDiagramChart ggData={result.gg_diagram} gLimit={result.g_limit} />
        </div>
      )}

      {result.anomaly && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <AnomalyReport anomaly={result.anomaly} />
        </div>
      )}

      {result.tyre_analysis?.available && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <TyreHeatmap tyre_analysis={result.tyre_analysis} metadata={meta} />
        </div>
      )}

      {result.brake_analysis?.available && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <BrakeFadeChart brake_analysis={result.brake_analysis} metadata={meta} />
        </div>
      )}

      {result.driver_inputs?.available && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <DriverInputsChart driver_inputs={result.driver_inputs} metadata={meta} />
        </div>
      )}

      {result.suspension?.available && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <SuspensionChart suspension={result.suspension} metadata={meta} />
        </div>
      )}

      {result.slip_angle?.available && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <SlipAngleChart slip_angle={result.slip_angle} metadata={meta} />
        </div>
      )}

      {result.tiempo_potencial && (
        <div className="fade-up fade-up--d5" style={{ marginTop: 'var(--s4)' }}>
          <PotentialLapCard
            tiempoPotencial={result.tiempo_potencial}
            xgboostPred={result.xgboost_pred}
            historySamples={result.metadata?.history_samples}
          />
        </div>
      )}

      {result.text_report && (
        <div className="card report-card fade-up fade-up--d5">
          <div className="report-header">
            <div className="report-title">
              <span>▤</span>
              Reporte Técnico — Formato Ingeniero
            </div>
            <button
              className={`copy-btn ${copied ? 'copy-btn--copied' : ''}`}
              onClick={onCopyReport}
              aria-label="Copiar reporte al portapapeles"
            >
              {copied ? '✓ Copiado' : '⎘ Copiar'}
            </button>
          </div>
          <pre className="text-report">{result.text_report}</pre>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [sessionResult, setSessionResult] = useState(null);
  const [stintResult, setStintResult] = useState(null);

  const [compareResult, setCompareResult] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState(null);
  const [comparingLaps, setComparingLaps] = useState(null);

  const [selectedLaps, setSelectedLaps] = useState([]);

  const [zoomDomain, setZoomDomain] = useState(null);
  const [activeCorner, setActiveCorner] = useState(null);
  const [fixedDistance, setFixedDistance] = useState(null);
  const [copied, setCopied] = useState(false);

  const isSessionMode = files.length === 1;

  const addFiles = useCallback((incoming) => {
    const csvs = [...incoming].filter(f =>
      f.name.toLowerCase().endsWith('.csv') && f.size <= MAX_FILE_SIZE
    );
    setFiles(prev => {
      const seen = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...csvs.filter(f => !seen.has(f.name + f.size))];
    });
  }, []);

  const removeFile = useCallback((idx) => {
    setFiles(prev => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        setSessionResult(null);
        setStintResult(null);
        setCompareResult(null);
        setSelectedLaps([]);
      }
      return next;
    });
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleAnalyze = async () => {
    if (!files.length || loading) return;
    setLoading(true);
    setError(null);
    setSessionResult(null);
    setStintResult(null);
    setCompareResult(null);
    setSelectedLaps([]);
    setComparingLaps(null);
    setZoomDomain(null);
    setActiveCorner(null);
    setFixedDistance(null);

    try {
      if (isSessionMode) {
        const [sessSettled, stintSettled] = await Promise.allSettled([
          analyzeSession(files[0]),
          analyzeStint([files[0]]),
        ]);
        if (sessSettled.status === 'fulfilled') {
          setSessionResult(sessSettled.value);
        } else {
          throw new Error(sessSettled.reason?.message || 'Error al analizar la sesión');
        }
        if (stintSettled.status === 'fulfilled') {
          setStintResult(stintSettled.value);
        }
      } else {
        const [basicSettled, advancedSettled] = await Promise.allSettled([
          compareLaps(files[0], files[1]),
          analyzeTelemetry(files[0], files[1]),
        ]);
        if (basicSettled.status !== 'fulfilled') {
          throw new Error(basicSettled.reason?.message || 'Error al comparar vueltas');
        }
        const merged = {
          ...basicSettled.value,
          ...(advancedSettled.status === 'fulfilled' ? advancedSettled.value : {}),
          // keep basic summary and chart series (advanced result may override corners with richer data)
          summary: basicSettled.value.summary,
          speed_comparison: basicSettled.value.speed_comparison,
          brake_comparison: basicSettled.value.brake_comparison,
          throttle_comparison: basicSettled.value.throttle_comparison,
          time_delta_series: basicSettled.value.time_delta_series,
          text_report: basicSettled.value.text_report,
          track_map: basicSettled.value.track_map,
        };
        setCompareResult(merged);
      }
    } catch (err) {
      setError(err.message || 'Error desconocido al analizar.');
    } finally {
      setLoading(false);
    }
  };

  const toggleLapSelection = useCallback((lapNum) => {
    setSelectedLaps(prev => {
      if (prev.includes(lapNum)) return prev.filter(n => n !== lapNum);
      if (prev.length >= 2) return [prev[prev.length - 1], lapNum];
      return [...prev, lapNum];
    });
    setCompareResult(null);
    setCompareError(null);
    setComparingLaps(null);
  }, []);

  const handleCompareLaps = async () => {
    if (selectedLaps.length !== 2 || !files[0] || compareLoading) return;
    const [lapA, lapB] = selectedLaps;
    setCompareLoading(true);
    setCompareError(null);
    setCompareResult(null);
    setComparingLaps([lapA, lapB]);
    setZoomDomain(null);
    setActiveCorner(null);
    setFixedDistance(null);

    try {
      const data = await compareSessionLaps(files[0], lapA, lapB);
      setCompareResult(data);
    } catch (err) {
      setCompareError(err.message || 'Error al comparar las vueltas.');
      setComparingLaps(null);
    } finally {
      setCompareLoading(false);
    }
  };

  const handleCornerClick = useCallback((domain, cornerNum) => {
    setZoomDomain(domain);
    setActiveCorner(cornerNum);
  }, []);

  const resetZoom = useCallback(() => { setZoomDomain(null); setActiveCorner(null); }, []);
  const handleChartClick = useCallback((dist) => {
    if (dist == null) return;
    setFixedDistance(prev => prev === dist ? null : dist);
  }, []);
  const handleClearFixed = useCallback(() => setFixedDistance(null), []);

  const handleCopyReport = () => {
    if (!compareResult?.text_report) return;
    navigator.clipboard.writeText(compareResult.text_report).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 2000); },
      () => {}
    );
  };

  return (
    <div className="app">
      {/* Topbar */}
      <div className="topbar">
        <div className="topbar__brand">
          <div className="topbar__logo">⚡</div>
          <span className="topbar__name">Motorsport Analytics</span>
          <span className="topbar__version">v2.0.0</span>
        </div>
        <div className="topbar__status">
          <div className="topbar__status-dot" />
          Sistema Listo
        </div>
      </div>

      {/* Hero */}
      <div className="hero">
        <div className="hero__eyebrow">
          <span>◉</span>
          Telemetría · Assetto Corsa ACTI
        </div>
        <h1 className="hero__title">El Analista Automatizado</h1>
        <p className="hero__subtitle">
          Sube un CSV de sesión para análisis completo y comparación de vueltas.
          O arrastra múltiples vueltas para comparar directamente.
        </p>
      </div>

      {/* ── Upload Zone ── */}
      <section className="section card" aria-label="Cargar telemetría">
        <div className="card__title">
          <span className="card__title-icon">▤</span>
          Cargar Telemetría
          {files.length > 0 && (
            <span style={{
              marginLeft: 'auto', fontSize: '0.68rem', padding: '3px 9px',
              background: isSessionMode ? 'var(--cyan-dim)' : 'rgba(0,230,118,0.08)',
              color: isSessionMode ? 'var(--cyan)' : 'var(--green)',
              border: `1px solid ${isSessionMode ? 'var(--cyan-border)' : 'rgba(0,230,118,0.2)'}`,
              borderRadius: 4, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
            }}>
              {isSessionMode ? '◎ Modo Sesión' : `⚡ ${files.length} Vueltas`}
            </span>
          )}
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onClick={() => fileInputRef.current?.click()}
          className="dropzone"
          style={{
            borderColor: isDragging ? 'var(--green)' : undefined,
            background: isDragging ? 'var(--green-dim)' : undefined,
            cursor: 'pointer',
            marginBottom: files.length ? 'var(--s3)' : 0,
          }}
        >
          <div className="dropzone__icon">◎</div>
          <div className="dropzone__label">Arrastra archivos CSV aquí</div>
          <div className="dropzone__sub">
            1 CSV → análisis de sesión + selección de vueltas · 2+ CSV → comparación directa
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          multiple
          style={{ display: 'none' }}
          onChange={e => { addFiles(e.target.files); e.target.value = ''; }}
        />

        {files.length > 0 && (
          <div className="stint-file-list">
            {files.map((f, i) => (
              <div key={i} className="stint-file-row">
                <span className="stint-file-row__num" style={{ color: LAP_COLORS[i % LAP_COLORS.length] }}>
                  {isSessionMode ? '◉' : `V${i + 1}`}
                </span>
                <span className="stint-file-row__name" title={f.name}>{f.name}</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {(f.size / 1048576).toFixed(1)} MB
                </span>
                <button
                  className="stint-file-row__remove"
                  onClick={e => { e.stopPropagation(); removeFile(i); }}
                  aria-label={`Quitar ${f.name}`}
                >×</button>
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
          disabled={!files.length || loading}
        >
          {loading
            ? <><div className="spinner" /> Procesando telemetría...</>
            : isSessionMode
              ? '◉ Analizar Sesión Completa'
              : `⚡ Comparar ${files.length} Vuelta${files.length !== 1 ? 's' : ''}`
          }
        </button>
      </section>

      {/* ── Session Results ── */}
      {sessionResult && (
        <div className="fade-up">
          <div className="section">
            <SessionKPIs sessionResult={sessionResult} stintResult={stintResult} />
          </div>

          {sessionResult.track_map?.length > 0 && (
            <div className="section fade-up fade-up--d1">
              <TrackMap trackData={sessionResult.track_map} />
            </div>
          )}

          <div className="section fade-up fade-up--d2">
            <SessionLapTable
              laps={sessionResult.laps}
              fastestLap={sessionResult.fastest_lap}
              selectedLaps={selectedLaps}
              onToggleLap={toggleLapSelection}
              onCompare={handleCompareLaps}
              compareLoading={compareLoading}
              compareError={compareError}
            />
          </div>

          {stintResult && (
            <div className="section fade-up fade-up--d3">
              <LapTimelineChart
                degradacion={stintResult.degradacion}
                montecarlo={stintResult.montecarlo}
                laps={stintResult.laps}
              />
              {stintResult.combustible?.available && (
                <div style={{ marginTop: 'var(--s4)' }}>
                  <PitWindowWidget combustible={stintResult.combustible} />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Direct Multi-File Comparison or Session-Lap Comparison ── */}
      {compareResult && (
        <div className="section" style={{ marginTop: sessionResult ? 'var(--s6)' : 0 }}>
          <ComparisonSection
            result={compareResult}
            comparingLaps={comparingLaps}
            onCornerClick={handleCornerClick}
            activeCorner={activeCorner}
            zoomDomain={zoomDomain}
            fixedDistance={fixedDistance}
            onClearFixed={handleClearFixed}
            onChartClick={handleChartClick}
            onResetZoom={resetZoom}
            copied={copied}
            onCopyReport={handleCopyReport}
          />
        </div>
      )}

    </div>
  );
}
