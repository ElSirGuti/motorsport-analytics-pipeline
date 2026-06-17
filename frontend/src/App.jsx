import React, { useState, useCallback, useRef, useMemo } from 'react';
import { useLanguage } from './context/LanguageContext';
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
import { analyzeSession, analyzeStint, compareLaps, analyzeTelemetry, compareSessionLaps, downloadPdfReport } from './api/telemetry';
import CornerAnalysisPanel from './components/CornerAnalysisPanel';
import SetupRecommendations from './components/SetupRecommendations';
import TyreDegradationPanel from './components/TyreDegradationPanel';
import RacingLinePanel from './components/RacingLinePanel';

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
  const { t } = useLanguage();
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
        {t.sessionSummary}
      </div>
      <div className="stint-kpi-grid">
        <KpiCard
          label={t.validLaps}
          value={sessionResult.total_laps}
          sub={pitCount > 0 ? t.stintExcluded(pitCount) : t.inRace}
        />
        <KpiCard
          label={t.bestLap}
          value={sessionResult.fastest_lap ? `#${sessionResult.fastest_lap.lap_number}` : '—'}
          sub={fmtTime(bestTime)}
          accent="var(--cyan)"
        />
        <KpiCard label={t.avgTime} value={fmtTime(meanTime)} />
        <KpiCard
          label={t.maxSpeed}
          value={maxSpeed ? `${maxSpeed.toFixed(0)} km/h` : '—'}
          sub={t.inBestLap}
        />
        {tasa != null && (
          <KpiCard
            label={t.degradation}
            value={`${tasa > 0 ? '+' : ''}${tasa.toFixed(3)}s`}
            sub={t.perLap}
            accent={tasa > 0.1 ? 'var(--red)' : tasa > 0 ? 'var(--amber)' : 'var(--green)'}
          />
        )}
      </div>
    </div>
  );
}

function SessionLapTable({ laps, fastestLap, selectedLaps, onToggleLap, onCompare, compareLoading, compareError }) {
  const { t } = useLanguage();
  const [lapA, lapB] = selectedLaps;
  const canCompare = selectedLaps.length === 2 && !compareLoading;

  return (
    <div className="card" style={{ marginBottom: 'var(--s4)' }}>
      <div className="card__title" style={{ flexWrap: 'wrap', gap: 8 }}>
        <span className="card__title-icon">▤</span>
        {t.lapTableTitle}
        {selectedLaps.length === 2 && (
          <button
            className="btn-analyze"
            style={{ marginLeft: 'auto', padding: '6px 18px', fontSize: '0.78rem', minHeight: 32 }}
            onClick={onCompare}
            disabled={!canCompare}
          >
            {compareLoading
              ? <><div className="spinner" style={{ width: 12, height: 12 }} /> {t.compareLoading}</>
              : `⚡ ${t.compareLaps(lapA, lapB)}`
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
          {t.sessionSelectLap(lapA)}
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table className="session-lap-table">
          <thead>
            <tr>
              <th style={{ width: 36, textAlign: 'center' }}>{t.selCol}</th>
              <th>{t.lapCol}</th>
              <th>{t.timeCol}</th>
              <th>{t.maxSpeedCol}</th>
              <th>{t.distanceCol}</th>
              <th>{t.deltaCol}</th>
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
                      <span style={{ marginLeft: 6, color: 'var(--cyan)', fontSize: '0.7rem' }}>{t.lapBadgeBest}</span>
                    )}
                    {isPit && (
                      <span style={{ marginLeft: 6, color: '#FF3D3D', fontSize: '0.65rem' }}>{t.lapBadgePit}</span>
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

function ComparisonSection({ result, comparingLaps, onCornerClick, activeCorner, zoomDomain, fixedDistance, onClearFixed, onChartClick, onResetZoom, copied, onCopyReport, onPdfDownload, pdfLoading }) {
  const { t } = useLanguage();
  const meta = result?.metadata;
  const title = comparingLaps
    ? t.compareSectionTitle(comparingLaps[0], comparingLaps[1])
    : meta ? `${meta.label_a ?? 'A'} vs ${meta.label_b ?? 'B'}` : t.compareTitle;

  const lapLabels = useMemo(() => {
    if (!meta) return {};
    const la = meta.label_a ?? 'A';
    const lb = meta.label_b ?? 'B';
    return {
      speed_a: la, speed_b: lb,
      brake_a: `${t.brakeThrottleBrake} — ${la}`, brake_b: `${t.brakeThrottleBrake} — ${lb}`,
      throttle_a: `${t.brakeThrottleThrottle} — ${la}`, throttle_b: `${t.brakeThrottleThrottle} — ${lb}`,
    };
  }, [meta, t]);

  return (
    <div className="fade-up">
      <div style={{
        padding: 'var(--s4) 0',
        borderTop: '2px solid var(--border-1)',
        marginBottom: 'var(--s4)',
      }}>
        <div className="hero__eyebrow" style={{ marginBottom: 4 }}>
          <span>⚡</span> {t.compareTitle}
        </div>
        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-1)' }}>{title}</div>
        {meta?.venue && (
          <div style={{ color: 'var(--text-3)', fontSize: '0.8rem', marginTop: 4 }}>{meta.venue}</div>
        )}
      </div>

      {meta?.distance_synthetic && (
        <div style={{
          background: 'rgba(255,120,0,0.10)',
          border: '1px solid rgba(255,140,0,0.5)',
          borderRadius: 8,
          padding: '10px 16px',
          marginBottom: 'var(--s3)',
          fontSize: '0.8rem',
          color: '#FF9040',
          lineHeight: 1.5,
        }}>
          <strong>{t.precisionWarning}</strong> {t.precisionDistance} <code>Distance</code> {t.precisionNotAvailable}
          {' '}{t.precisionLine1} {t.precisionLine2} {t.precisionLine3}
        </div>
      )}

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
            {t.zoomLap(zoomDomain[0], zoomDomain[1])}
            {activeCorner != null && ` ${t.zoomCorner(activeCorner)}`}
          </span>
          <button className="zoom-reset-btn" onClick={onResetZoom}>{t.zoomReset}</button>
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
            {t.eventsTitle}
            <span style={{
              marginLeft: 'auto', fontSize: '0.68rem', padding: '3px 8px',
              background: 'rgba(255,61,61,0.1)', color: 'var(--red)',
              border: '1px solid rgba(255,61,61,0.25)', borderRadius: 4,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {t.eventsCount(result.dynamic_events.length)}
            </span>
          </div>
          <div className="dynamic-events-list">
            {result.dynamic_events.map((ev, i) => (
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
              {t.reportTitle}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className={`copy-btn ${copied ? 'copy-btn--copied' : ''}`}
                onClick={onCopyReport}
                aria-label={t.reportCopyAria}
              >
                {copied ? `✓ ${t.copied}` : `⎘ ${t.copyReport}`}
              </button>
              <button
                className="copy-btn"
                onClick={onPdfDownload}
                disabled={pdfLoading}
                aria-label={t.reportDownloadAria}
                style={{ opacity: pdfLoading ? 0.6 : 1 }}
              >
                {pdfLoading ? '⏳' : `⬇ ${t.pdfDownload}`}
              </button>
            </div>
          </div>
          <pre className="text-report">{result.text_report}</pre>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { t, lang, setLang } = useLanguage();
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
  const [pdfLoading, setPdfLoading] = useState(false);

  const isSessionMode = files.length === 1;

  const addFiles = useCallback((incoming) => {
    const csvs = [...incoming].filter(f =>
      f.name.toLowerCase().endsWith('.csv')
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
        // Sequential to avoid V8 memory spike with 1GB files
        let sessSettled, stintSettled;
        try {
          sessSettled = { status: 'fulfilled', value: await analyzeSession(files[0], lang) };
        } catch (e) {
          sessSettled = { status: 'rejected', reason: e };
        }
        try {
          stintSettled = { status: 'fulfilled', value: await analyzeStint([files[0]], lang) };
        } catch (e) {
          stintSettled = { status: 'rejected', reason: e };
        }
        if (sessSettled.status === 'fulfilled') {
          setSessionResult(sessSettled.value);
        } else {
          throw new Error(sessSettled.reason?.message || t.errorSession);
        }
        if (stintSettled.status === 'fulfilled') {
          setStintResult(stintSettled.value);
        }
      } else {
        const [basicSettled, advancedSettled] = await Promise.allSettled([
          compareLaps(files[0], files[1], lang),
          analyzeTelemetry(files[0], files[1], 5, lang),
        ]);
        if (basicSettled.status !== 'fulfilled') {
          throw new Error(basicSettled.reason?.message || t.errorAnalyze);
        }
        const merged = {
          ...basicSettled.value,
          ...(advancedSettled.status === 'fulfilled' ? advancedSettled.value : {}),
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
      setError(err.message || t.errorUnknown);
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
      const data = await compareSessionLaps(files[0], lapA, lapB, lang);
      setCompareResult(data);
    } catch (err) {
      setCompareError(err.message || t.errorCompare);
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

  const handlePdfDownload = async () => {
    if (!compareResult || pdfLoading) return;
    setPdfLoading(true);
    try {
      const blob = await downloadPdfReport(compareResult, lang);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      const meta = compareResult.metadata || {};
      a.href     = url;
      a.download = `report_${meta.label_a || 'A'}_vs_${meta.label_b || 'B'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error downloading PDF:', err);
    } finally {
      setPdfLoading(false);
    }
  };

  const handleCompareBestWorst = async () => {
    if (!files[0] || compareLoading) return;
    setCompareLoading(true);
    setCompareError(null);
    setCompareResult(null);
    setComparingLaps(null);
    setZoomDomain(null);
    setActiveCorner(null);
    setFixedDistance(null);
    try {
      const data = await compareSessionLaps(files[0], 0, 0, lang);
      const meta = data?.metadata || {};
      const lapA = parseInt(meta.label_a?.replace('V', '') || '0');
      const lapB = parseInt(meta.label_b?.replace('V', '') || '0');
      setComparingLaps([lapA, lapB]);
      setCompareResult(data);
    } catch (err) {
      setCompareError(err.message || t.errorCompare);
    } finally {
      setCompareLoading(false);
    }
  };

  return (
    <div className="app">
      {/* Topbar */}
      <div className="topbar">
        <div className="topbar__brand">
          <div className="topbar__logo">⚡</div>
          <span className="topbar__name">{t.appBrand}</span>
          <span className="topbar__version">{t.appVersion}</span>
        </div>
        <div className="topbar__status">
          <div className="topbar__status-dot" />
          {t.systemReady}
        </div>
        <button
          onClick={() => setLang(lang === 'es' ? 'en' : 'es')}
          style={{
            background: 'rgba(0,212,255,0.08)',
            border: '1px solid rgba(0,212,255,0.25)',
            borderRadius: 6,
            color: '#00D4FF',
            cursor: 'pointer',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 1,
            padding: '4px 12px',
            transition: 'background 0.15s',
          }}
          title={t.langSwitchTo}
        >
          {t.langCurrent}
        </button>
      </div>

      {/* Hero */}
      <div className="hero">
        <div className="hero__eyebrow">
          <span>◉</span>
          {t.telemetryEyebrow}
        </div>
        <h1 className="hero__title">{t.appName}</h1>
        <p className="hero__subtitle">
          {t.appSubtitle}
        </p>
      </div>

      {/* ── Upload Zone ── */}
      <section className="section card" aria-label={t.uploadAria}>
        <div className="card__title">
          <span className="card__title-icon">▤</span>
          {t.uploadTitle}
          {files.length > 0 && (
            <span style={{
              marginLeft: 'auto', fontSize: '0.68rem', padding: '3px 9px',
              background: isSessionMode ? 'var(--cyan-dim)' : 'rgba(0,230,118,0.08)',
              color: isSessionMode ? 'var(--cyan)' : 'var(--green)',
              border: `1px solid ${isSessionMode ? 'var(--cyan-border)' : 'rgba(0,230,118,0.2)'}`,
              borderRadius: 4, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
            }}>
              {isSessionMode ? `◎ ${t.modeSession}` : t.modeBadgeCount(files.length)}
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
          <div className="dropzone__label">{t.dropzoneLabel}</div>
          <div className="dropzone__sub">
            {t.dropzoneSub}
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
                  {t.appFileRowNum(isSessionMode, i)}
                </span>
                <span className="stint-file-row__name" title={f.name}>{f.name}</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {(f.size / 1048576).toFixed(1)} MB
                </span>
                <button
                  className="stint-file-row__remove"
                  onClick={e => { e.stopPropagation(); removeFile(i); }}
                  aria-label={t.removeFile(f.name)}
                >×</button>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="error-banner" role="alert">
            <span className="error-banner__icon">✕</span>
            <div className="error-banner__text">
              <div className="error-banner__title">{t.errorTitle}</div>
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
            ? <><div className="spinner" /> {t.appAnalyzeProcessing}</>
            : isSessionMode
              ? t.appAnalyzeSession
              : t.appAnalyzeCompare(files.length)
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
            <div style={{ marginTop: 'var(--s3)', display: 'flex', gap: 'var(--s2)' }}>
              <button
                className="btn-analyze"
                onClick={handleCompareBestWorst}
                disabled={compareLoading}
                style={{ background: 'var(--surface-2)', color: 'var(--accent)', border: '1px solid var(--accent)', fontSize: '0.8rem', padding: '6px 14px' }}
              >
                {compareLoading ? t.appComparing : t.appCompareBestWorst}
              </button>
            </div>
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
              {stintResult.curvas_sesion?.available && (
                <div style={{ marginTop: 'var(--s4)' }}>
                  <CornerAnalysisPanel
                    result={{
                      corners: stintResult.curvas_sesion.corners,
                      setup_advisor: stintResult.setup_sesion,
                    }}
                    metadata={{
                      label_a: `${t.timelineLap} ${stintResult.curvas_sesion.reference_lap} (${t.anomalyReference})`,
                      label_b: `${t.avgTime} ${stintResult.curvas_sesion.n_laps_compared} ${t.timelineLap}`,
                    }}
                    sessionMode
                    referenceLap={stintResult.curvas_sesion.reference_lap}
                    nLaps={stintResult.curvas_sesion.n_laps_compared}
                  />
                </div>
              )}
              {stintResult.setup_sesion?.available && (
                <div style={{ marginTop: 'var(--s4)' }}>
                  <SetupRecommendations setup_advisor={stintResult.setup_sesion} />
                </div>
              )}
              {stintResult.degradacion_neumatico?.available && (
                <div style={{ marginTop: 'var(--s4)' }}>
                  <TyreDegradationPanel data={stintResult.degradacion_neumatico} />
                </div>
              )}
              {stintResult.racing_line_rl?.available && (
                <div style={{ marginTop: 'var(--s4)' }}>
                  <RacingLinePanel data={stintResult.racing_line_rl} />
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
            onPdfDownload={handlePdfDownload}
            pdfLoading={pdfLoading}
          />
        </div>
      )}

    </div>
  );
}
