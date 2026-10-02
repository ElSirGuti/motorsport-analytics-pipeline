import { useState, useCallback, useRef, useMemo } from 'react';
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
import InfoButton from './components/InfoButton';
import TyreDegradationPanel from './components/TyreDegradationPanel';
import RacingLinePanel from './components/RacingLinePanel';
import ThermalManagementPanel from './components/ThermalManagementPanel';
import HealthDashboard from "./components/HealthDashboard";
import PilotEngineerToggle from "./components/PilotEngineerToggle";
import { usePilotMode } from './components/usePilotMode';
import Sidebar from './components/Sidebar';
import { sectionLabel } from './components/navSections';
import { Icon, Panel, Stat, Badge } from './components/ui';
import './styles/shell.css';

const LAP_COLORS = ['var(--lap-a)', 'var(--lap-b)', 'var(--lap-c)', 'var(--lap-d)', 'var(--lap-e)', 'var(--lap-f)'];

function fmtTime(s) {
  if (s == null || isNaN(s) || s <= 0) return '—';
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(3);
  return `${m}:${sec.padStart(6, '0')}`;
}

// Existing i18n strings carry decorative glyphs/emoji (lightning, hourglass...).
// Strip leading/trailing non-alphanumeric symbols so the UI stays glyph-free.
function clean(s) {
  return String(s ?? '')
    .replace(/^[^\p{L}\p{N}]+/u, '')
    .replace(/[^\p{L}\p{N}.)%]+$/u, '');
}

// Bilingual fallback for strings that are not in the i18n files yet.
function useTx() {
  const { t, lang } = useLanguage();
  return useCallback((key, en, es) => t[key] ?? (lang === 'es' ? es : en), [t, lang]);
}

function SectionHeader({ icon, title, sub, actions }) {
  return (
    <div className="shell-section__head">
      {icon && <Icon name={icon} size={18} className="shell-section__icon" />}
      <div>
        <h2 className="shell-section__title">{title}</h2>
        {sub && <div className="shell-section__sub">{sub}</div>}
      </div>
      {actions && <div className="shell-section__actions">{actions}</div>}
    </div>
  );
}

function Alert({ tone = 'info', title, children, role, flush }) {
  const icon = tone === 'info' ? 'info' : 'alert';
  return (
    <div className={`shell-alert shell-alert--${tone}${flush ? ' shell-alert--flush' : ''}`} role={role}>
      <Icon name={icon} size={16} />
      <div>
        {title && <div className="shell-alert__title">{title}</div>}
        {children}
      </div>
    </div>
  );
}

function NoData({ title }) {
  const tx = useTx();
  return (
    <div className="shell-nodata">
      <Icon name="info" size={14} />
      <span>{title ? `${title}: ` : ''}{tx('noDataAvailable', 'No data available', 'Sin datos disponibles')}</span>
    </div>
  );
}

function KpiCard({ label, value, sub, tone }) {
  return (
    <div className="shell-kpi">
      <Stat label={label} value={value} hint={sub} tone={tone} />
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
    <Panel icon="grid" title={t.sessionSummary}>
      <div className="shell-kpis">
        <KpiCard
          label={t.validLaps}
          value={sessionResult.total_laps}
          sub={pitCount > 0 ? t.stintExcluded(pitCount) : t.inRace}
        />
        <KpiCard
          label={t.bestLap}
          value={sessionResult.fastest_lap ? `#${sessionResult.fastest_lap.lap_number}` : '—'}
          sub={fmtTime(bestTime)}
          tone="accent"
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
            tone={tasa > 0.1 ? 'bad' : tasa > 0 ? 'warn' : 'ok'}
          />
        )}
      </div>
    </Panel>
  );
}

function SessionLapTable({ laps, fastestLap, selectedLaps, onToggleLap, onCompare, onCompareBestWorst, compareLoading, compareError }) {
  const { t } = useLanguage();
  const tx = useTx();
  const [lapA, lapB] = selectedLaps;
  const canCompare = selectedLaps.length === 2 && !compareLoading;

  return (
    <Panel icon="stopwatch" title={t.lapTableTitle} flush>
      <div className="shell-lapbar">
        <div className="shell-lapbar__sel" aria-live="polite">
          {selectedLaps.length === 0 && (
            <span>{tx('lapSelectHint', 'Click two laps to compare them (A and B).', 'Haz clic en dos vueltas para compararlas (A y B).')}</span>
          )}
          {selectedLaps.length === 1 && (
            <>
              <span className="shell-lapchip"><i>A</i>{t.lapCol} {lapA}</span>
              <span>{t.sessionSelectLap(lapA)}</span>
            </>
          )}
          {selectedLaps.length === 2 && (
            <>
              <span className="shell-lapchip"><i>A</i>{t.lapCol} {lapA}</span>
              <span className="shell-lapchip"><i>B</i>{t.lapCol} {lapB}</span>
            </>
          )}
        </div>
        <div className="shell-lapbar__actions">
          <button type="button" className="ui-btn ui-btn--sm" onClick={onCompareBestWorst} disabled={compareLoading}>
            {compareLoading ? <span className="shell-spin" /> : <Icon name="trend" size={14} />}
            {compareLoading ? clean(t.appComparing) : clean(t.appCompareBestWorst)}
          </button>
          <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" onClick={onCompare} disabled={!canCompare}>
            {compareLoading
              ? <><span className="shell-spin" /> {t.compareLoading}</>
              : selectedLaps.length === 2 ? t.compareLaps(lapA, lapB) : clean(t.analyzeCompare)}
          </button>
        </div>
      </div>

      {compareError && (
        <div style={{ padding: '0 18px' }}>
          <Alert tone="bad" role="alert" flush>{compareError}</Alert>
        </div>
      )}

      <div className="shell-tablewrap">
        <table className="ui-table">
          <thead>
            <tr>
              <th style={{ width: 48, textAlign: 'center' }}>{t.selCol}</th>
              <th>{t.lapCol}</th>
              <th className="is-num">{t.timeCol}</th>
              <th className="is-num">{t.maxSpeedCol}</th>
              <th className="is-num">{t.distanceCol}</th>
              <th className="is-num">{t.deltaCol}</th>
            </tr>
          </thead>
          <tbody>
            {laps.map(lap => {
              const selIdx = selectedLaps.indexOf(lap.lap_number);
              const isSelected = selIdx !== -1;
              const delta = fastestLap && !lap.is_fastest
                ? lap.lap_time - fastestLap.lap_time
                : null;
              const isPit = lap.is_pit_lap;

              return (
                <tr
                  key={lap.lap_number}
                  onClick={() => !isPit && onToggleLap(lap.lap_number)}
                  className={`shell-laprow${isPit ? ' is-pit' : ''}${isSelected ? ' is-selected' : ''}${lap.is_fastest ? ' is-fastest' : ''}`}
                >
                  <td style={{ textAlign: 'center' }}>
                    <button
                      type="button"
                      className={`shell-pick${selIdx === 1 ? ' is-b' : ''}`}
                      aria-pressed={isSelected}
                      aria-label={`${t.lapCol} ${lap.lap_number}`}
                      disabled={isPit}
                      onClick={e => { e.stopPropagation(); onToggleLap(lap.lap_number); }}
                    >
                      {isSelected ? (selIdx === 0 ? 'A' : 'B') : ''}
                    </button>
                  </td>
                  <td>
                    <span className="num">{lap.lap_number}</span>
                    {lap.is_fastest && <span style={{ marginLeft: 8 }}><Badge tone="ok">{t.lapBadgeBest}</Badge></span>}
                    {isPit && <span style={{ marginLeft: 8 }}><Badge tone="warn">{t.lapBadgePit}</Badge></span>}
                  </td>
                  <td className="is-num shell-time">{fmtTime(lap.lap_time)}</td>
                  <td className="is-num">{lap.max_speed != null ? `${lap.max_speed.toFixed(1)} km/h` : '— km/h'}</td>
                  <td className="is-num" style={{ color: 'var(--ink-3)' }}>
                    {lap.lap_distance != null && lap.lap_distance > 0 ? `${lap.lap_distance.toFixed(0)} m` : '—'}
                  </td>
                  <td className="is-num" style={{ color: delta != null && delta > 0 ? 'var(--bad)' : 'var(--ink-3)' }}>
                    {delta != null && delta > 0 ? `+${delta.toFixed(3)}s` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ModuleWithHelp({ children, title, helpContent }) {
  return (
    <div className="shell-help-slot">
      {children}
      <div className="shell-help-slot__btn">
        <InfoButton title={title} content={helpContent} />
      </div>
    </div>
  );
}

function ComparisonSection({ result, rawTimeDelta, comparingLaps, onCornerClick, activeCorner, zoomDomain, fixedDistance, onClearFixed, onChartClick, onResetZoom, copied, onCopyReport, onPdfDownload, pdfLoading, isPilotMode }) {
  const { t, lang } = useLanguage();
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

  const head = (id, icon, sub) => (
    <SectionHeader icon={icon} title={sectionLabel(id, lang)} sub={sub} />
  );

  return (
    <div>
      <div className="shell-cmphead">
        <div className="ui-eyebrow">{t.compareTitle}</div>
        <h2 className="shell-cmphead__title">{title}</h2>
        {meta?.venue && <div className="shell-cmphead__sub">{meta.venue}</div>}
      </div>

      {meta?.distance_synthetic && (
        <Alert tone="warn" flush>
          <strong>{clean(t.precisionWarning)}:</strong> {t.precisionDistance} <code>Distance</code> {t.precisionNotAvailable}
          {' '}{t.precisionLine1} {t.precisionLine2} {t.precisionLine3}
        </Alert>
      )}

      {result && result.health_summary && <HealthDashboard health_summary={result.health_summary} />}

      <SummaryCard summary={result.summary} metadata={result.metadata} rawTimeDelta={rawTimeDelta} />

      <section id="section-core-lap" className="shell-section shell-gap" style={{ marginTop: 32 }}>
        {head('section-core-lap', 'stopwatch')}
        {result.track_map?.length > 0 && (
          <div>
            <TrackMap
              trackData={result.track_map}
              fixedDistance={fixedDistance}
              onClearFixed={onClearFixed}
            />
          </div>
        )}

        {zoomDomain && (
          <div className="shell-zoom">
            <Icon name="target" size={14} />
            <span>
              {clean(t.zoomLap(zoomDomain[0], zoomDomain[1]))}
              {activeCorner != null && ` · ${t.eventCorner(activeCorner)}`}
            </span>
            <button type="button" className="ui-btn ui-btn--sm" onClick={onResetZoom}>
              <Icon name="x" size={12} /> {clean(t.zoomReset)}
            </button>
          </div>
        )}

        <div className="charts-section" style={{ marginTop: 16 }}>
          <SpeedChart
            data={{ ...result.speed_comparison, lap_labels: lapLabels }}
            zoomDomain={zoomDomain}
            onChartClick={onChartClick}
            labels={t}
          />
          <BrakeThrottleChart
            brakeData={{ ...result.brake_comparison, lap_labels: lapLabels }}
            throttleData={{ ...result.throttle_comparison, lap_labels: lapLabels }}
            zoomDomain={zoomDomain}
            onChartClick={onChartClick}
            labels={t}
          />
          <TimeDeltaChart
            data={result.time_delta_series}
            zoomDomain={zoomDomain}
            onChartClick={onChartClick}
            labels={t}
          />
        </div>

        <CornerReport
          corners={result.corners}
          onCornerClick={onCornerClick}
          activeCorner={activeCorner}
        />

        {result.dynamic_events && result.dynamic_events.length > 0 && (
          <div className="shell-gap">
            <Panel
              icon="alert"
              title={clean(t.eventsTitle)}
              actions={<Badge tone="bad">{t.eventsCount(result.dynamic_events.length)}</Badge>}
            >
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
            </Panel>
          </div>
        )}

        {!isPilotMode && (
          result.curvatura?.length > 0
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title="Circuit Curvature Signature"
                  helpContent={"Shows lateral G intensity (|LateralG|) across the lap. Peaks correspond to corners — numbered dots mark the apex positions. A higher peak means a tighter or faster corner. Compare the profile shape between fast and slow laps to identify where the reference lap carries more or less lateral load."}
                >
                  <CurvatureMap curvatura={result.curvatura} apexes={result.apexes} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Circuit Curvature" />
        )}

        {!isPilotMode && result.sectores?.length > 0 && (
          <div className="shell-gap">
            <SectorTable
              sectores={result.sectores}
              totalDelta={result.metadata?.delta_total_s ?? result.summary?.total_time_delta}
            />
          </div>
        )}
      </section>

      {!isPilotMode && (
        <section id="section-dynamics" className="shell-section">
          {head('section-dynamics', 'gauge')}
          {(result.gg_diagram || result.g_limit)
            ? (
              <div>
                <ModuleWithHelp
                  title="GG Diagram — Grip Utilization"
                  helpContent={"Plots lateral G vs longitudinal G for every telemetry sample. Points near the outer edge of the circle = using the car's full grip. Sparse center = under-driving. The efficiency % shows how each sample compares to the car's grip limit. A well-driven lap fills the outer ring evenly."}
                >
                  <GGDiagramChart ggData={result.gg_diagram} gLimit={result.g_limit} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="GG Diagram" />
          }

          {result.anomaly
            ? (
              <div className="shell-gap">
                <AnomalyReport anomaly={result.anomaly} />
              </div>
            )
            : <NoData title="Anomaly" />
          }

          {result.slip_angle?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title="Slip Angle — Chassis Sideslip"
                  helpContent={"Body sideslip angle β: difference between car heading and velocity direction. High β = sliding. US% = time spent understeering (front slides more). OS% = oversteering (rear slides more). Balance mean > 0 → understeer tendency; < 0 → oversteer. Target: <10% combined US+OS in fast corners."}
                >
                  <SlipAngleChart slip_angle={result.slip_angle} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Slip Angle" />
          }

          {result.suspension?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title="Suspension Analysis — Pitch & Roll"
                  helpContent={"Shows suspension travel in mm. Roll = left/right difference (load transfer in corners). Pitch = front/rear difference (load under braking/acceleration). Bottoming events = damper at full compression — consider raising ride height or increasing bump stiffness. High roll ratio F/R → ARB imbalance."}
                >
                  <SuspensionChart suspension={result.suspension} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Suspension" />
          }
        </section>
      )}

      {!isPilotMode && (
        <section id="section-inputs" className="shell-section">
          {head('section-inputs', 'steering')}
          {result.tyre_analysis?.available
            ? (
              <div>
                <ModuleWithHelp
                  title="Tyre Temperature Analysis"
                  helpContent={"Shows inner / middle / outer tyre temperature per corner. Optimal window: 80–100 °C. Inner hotter than outer → too much negative camber. Outer hotter → too little. Even distribution → camber is well set. Front much hotter than rear → understeer bias or need more rear downforce."}
                >
                  <TyreHeatmap tyre_analysis={result.tyre_analysis} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Tyre Temperature" />
          }

          {result.brake_analysis?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title="Brake Efficiency — Fade Analysis"
                  helpContent={"Ratio of generated deceleration to applied brake pressure. Baseline = 1.0. A progressive drop means thermal fade — the pads/discs are overheating. Highlighted zones fell >15% below baseline. Fix: more brake duct opening, harder compound, or reduce brake bias slightly."}
                >
                  <BrakeFadeChart brake_analysis={result.brake_analysis} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Brake Efficiency" />
          }

          {result.driver_inputs?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title="Driver Inputs — Smoothness Analysis"
                  helpContent={"Nervousness index measures steering micro-corrections via FFT. High-frequency spikes (>5 Hz) → damper rebound too stiff. Mid-frequency (2–5 Hz) → spring rate issue. Brake-throttle overlap target: 8–18% for proper trail braking. Low overlap → driver lifting brake too early before apex."}
                >
                  <DriverInputsChart driver_inputs={result.driver_inputs} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title="Driver Inputs" />
          }
        </section>
      )}

      <section id="section-strategy" className="shell-section">
        {head('section-strategy', 'flag')}
        {result.tiempo_potencial && (
          <div>
            <PotentialLapCard
              tiempoPotencial={result.tiempo_potencial}
              xgboostPred={result.xgboost_pred}
              historySamples={result.metadata?.history_samples}
            />
          </div>
        )}

        {result.thermal_analysis?.available && (
          <div className="shell-gap">
            <ThermalManagementPanel thermal_analysis={result.thermal_analysis} />
          </div>
        )}

        {result.setup_advisor?.available && (
          <div className="shell-gap">
            <SetupRecommendations
              setup_advisor={result.setup_advisor}
              source="compare"
              isPilotMode={isPilotMode}
            />
          </div>
        )}

        {result.text_report && (
          <div className="shell-gap">
            <Panel
              icon="file"
              title={t.reportTitle}
              actions={
                <>
                  <button
                    type="button"
                    className="ui-btn ui-btn--sm"
                    onClick={onCopyReport}
                    aria-label={t.reportCopyAria}
                  >
                    <Icon name={copied ? 'check' : 'file'} size={14} />
                    {copied ? t.copied : t.copyReport}
                  </button>
                  <button
                    type="button"
                    className="ui-btn ui-btn--sm"
                    onClick={onPdfDownload}
                    disabled={pdfLoading}
                    aria-label={t.reportDownloadAria}
                  >
                    {pdfLoading ? <span className="shell-spin" /> : <Icon name="download" size={14} />}
                    {t.pdfDownload}
                  </button>
                </>
              }
            >
              <pre className="shell-report">{result.text_report}</pre>
            </Panel>
          </div>
        )}
        {!result.tiempo_potencial && !result.thermal_analysis?.available && !result.setup_advisor?.available && !result.text_report && (
          <NoData />
        )}
      </section>
    </div>
  );
}

export default function App() {
  const { t, lang, setLang } = useLanguage();
  const tx = useTx();
  const [step, setStep] = useState('session');
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

  const [isPilotMode, togglePilotMode] = usePilotMode();

  const rawTimeDelta = useMemo(() => {
    if (!comparingLaps || !sessionResult?.laps) return null;
    const [a, b] = comparingLaps;
    const lapA = sessionResult.laps.find(l => l.lap_number === a);
    const lapB = sessionResult.laps.find(l => l.lap_number === b);
    if (!lapA || !lapB) return null;
    return Math.round((lapB.lap_time - lapA.lap_time) * 1000) / 1000;
  }, [comparingLaps, sessionResult]);

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
    setStep('session');
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
        setStep('stint');
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
        setStep('compare');
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


  const resetAll = () => {
    setFiles([]);
    setError(null);
    setSessionResult(null);
    setStintResult(null);
    setCompareResult(null);
    setCompareError(null);
    setComparingLaps(null);
    setSelectedLaps([]);
    setZoomDomain(null);
    setActiveCorner(null);
    setFixedDistance(null);
    window.scrollTo({ top: 0 });
  };

  const hasResults = !!(sessionResult || compareResult);
  const fmtMB = (bytes) => `${(bytes / 1048576).toFixed(1)} MB`;

  const modeBadge = files.length > 0 && (
    <Badge tone={isSessionMode ? 'accent' : 'ok'}>
      {isSessionMode ? t.modeSession : clean(t.modeBadgeCount(files.length))}
    </Badge>
  );

  const progressText = step === 'stint'
    ? tx('shellStepStint', 'Analyzing stint: degradation, fuel and corners', 'Analizando stint: degradación, combustible y curvas')
    : step === 'compare'
      ? tx('shellStepCompare', 'Comparing laps and running advanced analysis', 'Comparando vueltas y ejecutando análisis avanzado')
      : tx('shellStepSession', 'Reading session and segmenting laps', 'Leyendo la sesión y segmentando vueltas');
  const progressStep = isSessionMode ? (step === 'stint' ? 2 : 1) : null;

  const analyzeLabel = isSessionMode ? clean(t.appAnalyzeSession) : clean(t.appAnalyzeCompare(files.length));

  return (
    <>
      <header className="shell-appbar">
        <div className="shell-brand">
          <div className="shell-brand__mark"><Icon name="gauge" size={16} /></div>
          <span className="shell-brand__name">{t.appBrand}</span>
          <span className="shell-brand__ver">{t.appVersion}</span>
        </div>
        <div className="shell-appbar__spacer" />
        <div className="shell-appbar__tools">
          <span className="shell-status">
            <span className="shell-status__dot" aria-hidden="true" />
            {t.systemReady}
          </span>
          <div className="ui-seg" role="group" aria-label={t.langSwitchTo} title={t.langSwitchTo}>
            <button type="button" className="ui-seg__item" aria-pressed={lang === 'es'} onClick={() => setLang('es')}>ES</button>
            <button type="button" className="ui-seg__item" aria-pressed={lang !== 'es'} onClick={() => setLang('en')}>EN</button>
          </div>
          <PilotEngineerToggle isPilotMode={isPilotMode} onToggle={togglePilotMode} />
        </div>
      </header>

      <div className={`shell-body${hasResults ? ' shell-body--rail' : ''}`}>
        {hasResults && (
          <Sidebar
            mode={!compareResult ? 'session' : sessionResult ? 'both' : 'compare'}
            isPilotMode={isPilotMode}
            resultKey={`${!!sessionResult}-${!!stintResult}-${!!compareResult}`}
          />
        )}

        <main className={`shell-main${hasResults ? '' : ' shell-main--narrow'}`}>
          {!hasResults && (
            <Panel
              icon="upload"
              title={t.uploadTitle}
              subtitle={t.appName}
              actions={modeBadge}
              className="shell-upload"
            >
              <section aria-label={t.uploadAria}>
                <div
                  role="button"
                  tabIndex={loading ? -1 : 0}
                  aria-label={t.dropzoneLabel}
                  aria-disabled={loading}
                  onDrop={e => { if (loading) { e.preventDefault(); return; } handleDrop(e); }}
                  onDragOver={e => { e.preventDefault(); if (!loading) setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onClick={() => !loading && fileInputRef.current?.click()}
                  onKeyDown={e => {
                    if ((e.key === 'Enter' || e.key === ' ') && !loading) {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  className={`shell-drop${files.length ? ' shell-drop--compact' : ''}${isDragging ? ' is-dragging' : ''}`}
                  style={loading ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
                >
                  <Icon name="upload" size={files.length ? 18 : 24} className="shell-drop__icon" />
                  <div className="shell-drop__label">{t.dropzoneLabel}</div>
                  {!files.length && (
                    <div className="shell-drop__sub">
                      {tx('shellDropHint', 'or click to browse. Only .csv files.', 'o haz clic para buscar. Solo archivos .csv.')}
                    </div>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  multiple
                  hidden
                  tabIndex={-1}
                  aria-hidden="true"
                  onChange={e => { addFiles(e.target.files); e.target.value = ''; }}
                />

                <div className="shell-modes">
                  <div className={`shell-mode${isSessionMode ? ' is-active' : ''}`}>
                    <div className="shell-mode__head">
                      <Icon name="layers" size={16} /> {t.modeSession}
                      <span className="shell-mode__req">{tx('shellOneCsv', '1 CSV', '1 CSV')}</span>
                    </div>
                    <div className="shell-mode__desc">
                      {tx('shellModeSessionDesc',
                        'One CSV with the whole session. Laps are segmented automatically, the stint is analysed and you can pick any two laps to compare.',
                        'Un CSV con toda la sesión. Las vueltas se segmentan automáticamente, se analiza el stint y puedes elegir dos vueltas para comparar.')}
                    </div>
                  </div>
                  <div className={`shell-mode${files.length >= 2 ? ' is-active' : ''}`}>
                    <div className="shell-mode__head">
                      <Icon name="activity" size={16} /> {clean(t.analyzeCompare)}
                      <span className="shell-mode__req">{tx('shellTwoCsv', '2 CSV', '2 CSV')}</span>
                    </div>
                    <div className="shell-mode__desc">
                      {tx('shellModeCompareDesc',
                        'Two single-lap CSVs (reference first, then comparison). Time delta, corners and detailed telemetry between both laps.',
                        'Dos CSV de una vuelta (primero la referencia, luego la comparación). Delta de tiempo, curvas y telemetría detallada entre ambas.')}
                    </div>
                  </div>
                </div>

                {files.length > 0 && (
                  <ul className="shell-files" aria-label={t.uploadTitle}>
                    {files.map((f, i) => (
                      <li key={f.name + f.size} className="shell-file">
                        <span className="shell-file__tag" style={{ color: LAP_COLORS[i % LAP_COLORS.length] }}>
                          {isSessionMode ? 'S' : `V${i + 1}`}
                        </span>
                        <Icon name="file" size={16} className="shell-file__icon" />
                        <span className="shell-file__name shell-trunc" title={f.name}>{f.name}</span>
                        {!isSessionMode && i >= 2 && (
                          <Badge tone="warn">{tx('shellNotUsed', 'not used', 'sin usar')}</Badge>
                        )}
                        <span className="shell-file__size">{fmtMB(f.size)}</span>
                        <button
                          type="button"
                          className="shell-iconbtn"
                          onClick={() => removeFile(i)}
                          disabled={loading}
                          aria-label={t.removeFile(f.name)}
                          title={t.removeFile(f.name)}
                        >
                          <Icon name="x" size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {error && (
                  <Alert tone="bad" role="alert" title={t.errorTitle}>{error}</Alert>
                )}

                {loading && (
                  <div className="shell-progress" role="status" aria-live="polite">
                    <div className="shell-progress__bar" />
                    <div className="shell-progress__text">
                      <span className="shell-spin" />
                      <span>
                        {progressText}
                        {progressStep && ` (${progressStep}/2)`}
                      </span>
                    </div>
                    <div className="shell-progress__hint">
                      {tx('shellProgressHint', 'Large files can take a few minutes. Keep this tab open.', 'Los archivos grandes pueden tardar varios minutos. Mantén esta pestaña abierta.')}
                    </div>
                  </div>
                )}

                <div className="shell-actions">
                  <button
                    type="button"
                    className="ui-btn ui-btn--primary ui-btn--lg"
                    onClick={handleAnalyze}
                    disabled={!files.length || loading}
                  >
                    {loading
                      ? <><span className="shell-spin" /> {clean(t.appAnalyzeProcessing)}</>
                      : <><Icon name="activity" size={16} /> {files.length ? analyzeLabel : clean(t.analyzeSession)}</>
                    }
                  </button>
                  {!files.length && (
                    <span className="shell-actions__note">
                      {tx('shellAddFile', 'Add at least one CSV to start.', 'Añade al menos un CSV para empezar.')}
                    </span>
                  )}
                  {files.length > 2 && !loading && (
                    <span className="shell-actions__note">
                      {tx('shellExtraFiles', 'Only the first two files are compared.', 'Solo se comparan los dos primeros archivos.')}
                    </span>
                  )}
                </div>
              </section>
            </Panel>
          )}

          {hasResults && (
            <div className="shell-filebar" role="region" aria-label={t.uploadTitle}>
              <div className="shell-filebar__files">
                {modeBadge}
                {files.map((f, i) => (
                  <span key={f.name + f.size} className="shell-chip" title={f.name}>
                    <span className="shell-chip__tag" style={{ color: LAP_COLORS[i % LAP_COLORS.length] }}>
                      {isSessionMode ? 'S' : `V${i + 1}`}
                    </span>
                    <span className="shell-trunc">{f.name}</span>
                    <span className="shell-chip__size">{fmtMB(f.size)}</span>
                  </span>
                ))}
              </div>
              <button type="button" className="ui-btn ui-btn--sm" onClick={resetAll} disabled={loading || compareLoading}>
                <Icon name="upload" size={14} />
                {tx('shellNewAnalysis', 'New analysis', 'Nuevo análisis')}
              </button>
            </div>
          )}

          {/* ── Session results ── */}
          {sessionResult && (
            <div>
              <section id="section-overview" className="shell-section">
                <SectionHeader
                  icon="grid"
                  title={sectionLabel('section-overview', lang)}
                  sub={tx('shellOverviewSub', 'Key figures, circuit map and lap list. Select two laps to compare them.', 'Cifras clave, mapa del circuito y lista de vueltas. Selecciona dos vueltas para compararlas.')}
                />
                <SessionKPIs sessionResult={sessionResult} stintResult={stintResult} />

                {sessionResult.track_map?.length > 0 && (
                  <div className="shell-gap">
                    <TrackMap trackData={sessionResult.track_map} />
                  </div>
                )}

                <div className="shell-gap">
                  <SessionLapTable
                    laps={sessionResult.laps}
                    fastestLap={sessionResult.fastest_lap}
                    selectedLaps={selectedLaps}
                    onToggleLap={toggleLapSelection}
                    onCompare={handleCompareLaps}
                    onCompareBestWorst={handleCompareBestWorst}
                    compareLoading={compareLoading}
                    compareError={compareError}
                  />
                </div>
              </section>

              {stintResult && (
                <section id="section-stint" className="shell-section">
                  <SectionHeader icon="trend" title={sectionLabel('section-stint', lang)} />
                  {stintResult.health_summary && <HealthDashboard health_summary={stintResult.health_summary} />}
                  {stintResult.track_evolution?.available && (
                    <Alert tone="info" flush>
                      {tx('shellTrackEvolution', 'Track evolution', 'Evolución de pista')}: {stintResult.track_evolution.note}
                    </Alert>
                  )}
                  <LapTimelineChart
                    degradacion={stintResult.degradacion}
                    montecarlo={stintResult.montecarlo}
                    laps={stintResult.laps}
                  />
                  {stintResult.combustible?.available && (
                    <div className="shell-gap">
                      <PitWindowWidget combustible={stintResult.combustible} />
                    </div>
                  )}
                  {stintResult.curvas_sesion?.available && (
                    <div className="shell-gap">
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
                </section>
              )}

              {stintResult && (stintResult.thermal_analysis?.available || stintResult.setup_sesion?.available || stintResult.degradacion_neumatico?.available || stintResult.racing_line_rl?.available) && (
                <section id="section-setup" className="shell-section">
                  <SectionHeader icon="wrench" title={sectionLabel('section-setup', lang)} />
                  {stintResult.thermal_analysis?.available && (
                    <div>
                      <ThermalManagementPanel thermal_analysis={stintResult.thermal_analysis} />
                    </div>
                  )}
                  {stintResult.setup_sesion?.available && (
                    <div className="shell-gap">
                      <SetupRecommendations setup_advisor={stintResult.setup_sesion} isPilotMode={isPilotMode} />
                    </div>
                  )}
                  {stintResult.degradacion_neumatico?.available && (
                    <div className="shell-gap">
                      <TyreDegradationPanel data={stintResult.degradacion_neumatico} />
                    </div>
                  )}
                  {stintResult.racing_line_rl?.available && (
                    <div className="shell-gap">
                      <RacingLinePanel data={stintResult.racing_line_rl} />
                    </div>
                  )}
                </section>
              )}
            </div>
          )}

          {/* ── Comparison results ── */}
          {compareResult && (
            <div style={{ marginTop: sessionResult ? 16 : 0 }}>
              <ComparisonSection
                result={compareResult}
                rawTimeDelta={rawTimeDelta}
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
                isPilotMode={isPilotMode}
              />
            </div>
          )}
        </main>
      </div>
    </>
  );
}
