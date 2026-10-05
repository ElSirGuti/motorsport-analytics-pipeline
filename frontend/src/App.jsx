import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useLanguage } from './context/LanguageContext';
import SpeedChart from './components/SpeedChart';
import BrakeThrottleChart from './components/BrakeThrottleChart';
import TimeDeltaChart from './components/TimeDeltaChart';
import SummaryCard from './components/SummaryCard';
import CornerReport from './components/CornerReport';
import IncidentsPanel from './components/IncidentsPanel';
import { markerCorners } from './utils/cornerKind';
import TrackMap from './components/TrackMap';
import OptimalLapPanel from './components/OptimalLapPanel';
import { StageProgress, StintSkeleton } from './components/PerfProgress';
import { ensureFileId, isCancelled } from './api/files';
import { prefetchOptimalLap } from './api/optimalLap';
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
import { analyzeSession, analyzeStint, compareLaps, analyzeTelemetry, compareSessionLaps, downloadPdfReport, downloadSessionPdfReport } from './api/telemetry';
import CornerAnalysisPanel from './components/CornerAnalysisPanel';
import SetupSection from './components/SetupSection';
import InfoButton from './components/InfoButton';
import TyreDegradationPanel from './components/TyreDegradationPanel';
import RacingLinePanel from './components/RacingLinePanel';
import ThermalManagementPanel from './components/ThermalManagementPanel';
import HealthDashboard from "./components/HealthDashboard";
import DataQualityPanel from "./components/DataQualityPanel";
import PilotEngineerToggle from "./components/PilotEngineerToggle";
import ThemeSwitch from './components/ThemeSwitch';
import { usePilotMode } from './components/usePilotMode';
import Sidebar from './components/Sidebar';
import { sectionLabel } from './components/navSections';
import { Icon, Panel, Stat, Badge } from './components/ui';
import SaveToLibrary from './components/library/SaveToLibrary';
import LibraryView from './components/library/LibraryView';
import CompareSessionsView from './components/library/CompareSessionsView';
import SettingsView from './components/SettingsView';
import { restoreResults } from './api/library';
import FormatBadge from './components/FormatBadge';
import CircuitBadge from './components/CircuitBadge';
import { cornerLabel, cornerNameMap, pickCircuit } from './utils/cornerLabel';
import { isSupportedFile, ACCEPT_ATTR } from './utils/formats';
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
  const { t } = useLanguage();
  return (
    <div className="shell-nodata">
      <Icon name="info" size={14} />
      <span>{title ? `${title}: ` : ''}{t.noDataAvailable}</span>
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

function SessionLapTable({ laps, fastestLap, selectedLaps, onToggleLap, onCompare, onCompareBestWorst, compareLoading, compareError, csvMissing }) {
  const { t } = useLanguage();
  const [lapA, lapB] = selectedLaps;
  const canCompare = selectedLaps.length === 2 && !compareLoading && !csvMissing;

  return (
    <Panel icon="stopwatch" title={t.lapTableTitle} flush>
      <div className="shell-lapbar">
        <div className="shell-lapbar__sel" aria-live="polite">
          {selectedLaps.length === 0 && (
            <span>{t.lapSelectHint}</span>
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
          <button type="button" className="ui-btn ui-btn--sm" onClick={onCompareBestWorst} disabled={compareLoading || csvMissing} title={csvMissing ? t.libCsvRequired : undefined}>
            {compareLoading ? <span className="shell-spin" /> : <Icon name="trend" size={14} />}
            {compareLoading ? clean(t.appComparing) : clean(t.appCompareBestWorst)}
          </button>
          <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" onClick={onCompare} disabled={!canCompare} title={csvMissing ? t.libCsvRequired : undefined}>
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

function ComparisonSection({ result, rawTimeDelta, comparingLaps, onCornerClick, activeCorner, zoomDomain, fixedDistance, onClearFixed, onChartClick, onResetZoom, copied, onCopyReport, onPdfDownload, pdfLoading, isPilotMode, setupFile }) {
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

  const head = (id, icon, sub) => (
    <SectionHeader icon={icon} title={sectionLabel(id, t)} sub={sub} />
  );

  return (
    <div>
      <div className="shell-cmphead">
        <div className="ui-eyebrow">{t.compareTitle}</div>
        <h2 className="shell-cmphead__title">{title}</h2>
        {(result?.circuit?.recognized ? result.circuit.name : meta?.venue) && (
          <div className="shell-cmphead__sub">{result?.circuit?.recognized ? result.circuit.name : meta.venue}</div>
        )}
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
              corners={markerCorners({ corners: result.corners, cornerMap: result.corner_map }).items}
              cornerLengthM={markerCorners({ corners: result.corners, cornerMap: result.corner_map }).lengthM}
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
          cornerMap={result.corner_map}
        />

        {result.dynamic_events && result.dynamic_events.length > 0 && (
          <div className="shell-gap">
            <Panel
              icon="alert"
              title={clean(t.eventsTitle)}
              actions={<Badge tone="bad">{t.eventsCount(result.dynamic_events.length)}</Badge>}
            >
              <div className="dynamic-events-list">
                {result.dynamic_events.map((ev, i) => {
                  // `tipo` / `severidad` come localised from the backend ("subviraje" / "understeer"...).
                  const isUnder = /^(sub|under)/i.test(ev.tipo || '');
                  const sev = /^(crit)/i.test(ev.severidad || '') ? 'critico' : /^(med|mod)/i.test(ev.severidad || '') ? 'media' : 'leve';
                  const cName = cornerNameMap(result.corners)[ev.curva];
                  return (
                    <div key={i} className={`dynamic-event dynamic-event--${isUnder ? 'subviraje' : 'sobreviraje'}`}>
                      <div className="dynamic-event__header">
                        <span className="dynamic-event__tipo">
                          {isUnder ? t.eventSub : t.eventOver}
                        </span>
                        <span className="dynamic-event__curva">{cName ? cornerLabel(t, ev.curva, cName) : t.eventCorner(ev.curva)}</span>
                        <span className="dynamic-event__dist">{ev.distancia?.toFixed(0)}m</span>
                        <span className={`dynamic-event__severidad dynamic-event__severidad--${sev}`}>
                          {ev.severidad?.toUpperCase()}
                        </span>
                      </div>
                      <div className="dynamic-event__diagnostico">{ev.diagnostico}</div>
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>
        )}

        {!isPilotMode && (
          result.curvatura?.length > 0
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title={t.curvatureTitle}
                  helpContent={t.helpCurvature}
                >
                  <CurvatureMap curvatura={result.curvatura} apexes={result.apexes} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.curvatureTitle} />
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
                  title={t.ggTitle}
                  helpContent={t.helpGG}
                >
                  <GGDiagramChart ggData={result.gg_diagram} gLimit={result.g_limit} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.ggTitle} />
          }

          {result.anomaly
            ? (
              <div className="shell-gap">
                <AnomalyReport anomaly={result.anomaly} />
              </div>
            )
            : <NoData title={t.anomalyTitle} />
          }

          {result.slip_angle?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title={t.slipAngleTitle}
                  helpContent={t.helpSlip}
                >
                  <SlipAngleChart slip_angle={result.slip_angle} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.slipAngleTitle} />
          }

          {result.suspension?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title={t.suspensionTitle}
                  helpContent={t.helpSuspension}
                >
                  <SuspensionChart suspension={result.suspension} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.suspensionTitle} />
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
                  title={t.tyreTitle}
                  helpContent={t.helpTyre}
                >
                  <TyreHeatmap tyre_analysis={result.tyre_analysis} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.tyreTitle} />
          }

          {result.brake_analysis?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title={t.brakeFadeTitle}
                  helpContent={t.helpBrake}
                >
                  <BrakeFadeChart brake_analysis={result.brake_analysis} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.brakeFadeTitle} />
          }

          {result.driver_inputs?.available
            ? (
              <div className="shell-gap">
                <ModuleWithHelp
                  title={t.driverInputsTitle}
                  helpContent={t.helpDriver}
                >
                  <DriverInputsChart driver_inputs={result.driver_inputs} metadata={meta} />
                </ModuleWithHelp>
              </div>
            )
            : <NoData title={t.driverInputsTitle} />
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
            <SetupSection
              file={setupFile}
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
  const [step, setStep] = useState('session');
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [sessionResult, setSessionResult] = useState(null);
  const [stintResult, setStintResult] = useState(null);

  // Progressive analysis: the file is uploaded once, then session / stint / optimal lap run in parallel.
  // `stages` drives the progress bar; `runRef` + `abortRef` discard and cancel work of a previous file.
  const [stages, setStages] = useState(null);
  const runRef = useRef(0);
  const abortRef = useRef(null);
  useEffect(() => () => abortRef.current?.abort(), []);
  const cancelAnalysis = useCallback(() => {
    runRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setStages(null);
    setLoading(false);
  }, []);

  const [compareResult, setCompareResult] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState(null);
  const [comparingLaps, setComparingLaps] = useState(null);

  const [selectedLaps, setSelectedLaps] = useState([]);

  // Biblioteca de sesiones: vista activa, sesion restaurada y pareja preseleccionada para comparar
  const [view, setView] = useState('analysis');
  useEffect(() => {   // the setups panel links here when it cannot find the folder
    const open = () => setView('settings');
    window.addEventListener('open-settings', open);
    return () => window.removeEventListener('open-settings', open);
  }, []);
  const [savedSession, setSavedSession] = useState(null);
  const [compareSeed, setCompareSeed] = useState(null);

  const [zoomDomain, setZoomDomain] = useState(null);
  const [activeCorner, setActiveCorner] = useState(null);
  const [fixedDistance, setFixedDistance] = useState(null);
  const [copied, setCopied] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [sessionPdfLoading, setSessionPdfLoading] = useState(false);

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
    const csvs = [...incoming].filter(isSupportedFile);
    setFiles(prev => {
      const seen = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...csvs.filter(f => !seen.has(f.name + f.size))];
    });
  }, []);

  const removeFile = useCallback((idx) => {
    cancelAnalysis(); // pending requests of the removed file (optimal lap, ...) are cancelled
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
  }, [cancelAnalysis]);

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

    // A new run supersedes (and cancels) whatever was still in flight for a previous file.
    const run = ++runRef.current;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const live = () => runRef.current === run;
    const patch = (p) => { if (live()) setStages((s) => (s ? { ...s, ...p } : s)); };
    setStages(null);

    try {
      if (isSessionMode) {
        const file = files[0];
        setStages({ upload: 0, uploadState: 'running', session: 'pending', stint: 'pending', optimal: 'pending' });

        // 1. Upload the file once (POST /api/files). null = endpoint unavailable -> classic flow below.
        let meta = null;
        try {
          meta = await ensureFileId(file, {
            signal: ctrl.signal, retryFailed: true, onProgress: (p) => patch({ upload: p }),
          });
        } catch (e) {
          if (isCancelled(e) || !live()) return;
          throw e;
        }
        if (!live()) return;

        if (meta) {
          // 2. Session, stint and optimal lap are independent: run them in parallel and show each
          //    result as soon as it arrives (the stint sections show a skeleton until theirs does).
          patch({ uploadState: 'done', upload: 1, session: 'running', stint: 'running', optimal: 'running' });
          setStep('stint');
          prefetchOptimalLap(file, lang, { signal: ctrl.signal })
            .then((ok) => patch({ optimal: ok ? 'done' : 'error' }));
          const sessP = analyzeSession(file, lang, { signal: ctrl.signal }).then((value) => {
            if (live()) { setSessionResult(value); patch({ session: 'done' }); }
            return value;
          });
          const stintP = analyzeStint([file], lang, { signal: ctrl.signal }).then((value) => {
            if (live()) { setStintResult(value); patch({ stint: 'done' }); }
          }).catch(() => patch({ stint: 'error' })); // a failed stint never hides the session results
          const [sessSettled] = await Promise.allSettled([sessP, stintP]);
          if (!live()) return;
          if (sessSettled.status === 'rejected') {
            patch({ session: 'error' });
            if (isCancelled(sessSettled.reason)) return;
            throw new Error(sessSettled.reason?.message || t.errorSession);
          }
        } else {
          // Fallback (no /api/files): the previous sequential flow, file sent in each request.
          // Sequential to avoid V8 memory spike with 1GB files
          patch({ uploadState: 'skipped', session: 'running' });
          let sessSettled, stintSettled;
          try {
            sessSettled = { status: 'fulfilled', value: await analyzeSession(file, lang, { signal: ctrl.signal }) };
          } catch (e) {
            sessSettled = { status: 'rejected', reason: e };
          }
          if (!live()) return;
          setStep('stint');
          patch({ session: sessSettled.status === 'fulfilled' ? 'done' : 'error', stint: 'running' });
          try {
            stintSettled = { status: 'fulfilled', value: await analyzeStint([file], lang, { signal: ctrl.signal }) };
          } catch (e) {
            stintSettled = { status: 'rejected', reason: e };
          }
          if (!live()) return;
          if (sessSettled.status === 'fulfilled') {
            setSessionResult(sessSettled.value);
          } else {
            throw new Error(sessSettled.reason?.message || t.errorSession);
          }
          if (stintSettled.status === 'fulfilled') {
            setStintResult(stintSettled.value);
          }
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
          // Both endpoints return `metadata` with different keys (driver_a/vehicle_a/same_vehicle vs
          // driver_fast/vehicle_fast/...): merge them instead of letting the advanced one replace the basic one.
          metadata: {
            ...(advancedSettled.status === 'fulfilled' ? advancedSettled.value.metadata : {}),
            ...basicSettled.value.metadata,
          },
        };
        setCompareResult(merged);
      }
    } catch (err) {
      if (live() && !isCancelled(err)) setError(err.message || t.errorUnknown);
    } finally {
      if (live()) setLoading(false);
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

  const handleSessionPdfDownload = async () => {
    if (!sessionResult || sessionPdfLoading) return;
    setSessionPdfLoading(true);
    try {
      const { blob, filename } = await downloadSessionPdfReport(
        { session: sessionResult, stint: stintResult, comparison: compareResult, metadata: { file: files[0]?.name } },
        lang,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error downloading session report:', err);
    } finally {
      setSessionPdfLoading(false);
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
      const lapA = parseInt(meta.label_a?.replace(/\D/g, '') || '0');
      const lapB = parseInt(meta.label_b?.replace(/\D/g, '') || '0');
      setComparingLaps([lapA, lapB]);
      setCompareResult(data);
    } catch (err) {
      setCompareError(err.message || t.errorCompare);
    } finally {
      setCompareLoading(false);
    }
  };


  // Abre una sesion guardada: restaura los resultados sin subir el CSV.
  const handleOpenSaved = (detail) => {
    const { sessionResult: sess, stintResult: stint, extras } = restoreResults(detail);
    cancelAnalysis();
    setFiles([]);
    setError(null);
    setSessionResult(sess);
    setStintResult(stint);
    setCompareResult(null);
    setCompareError(null);
    setComparingLaps(null);
    setSelectedLaps([]);
    setZoomDomain(null);
    setActiveCorner(null);
    setFixedDistance(null);
    setSavedSession({ id: detail.id, title: detail.title, extras });
    setView('analysis');
    window.scrollTo({ top: 0 });
  };

  const resetAll = () => {
    cancelAnalysis();
    setSavedSession(null);
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
    ? t.shellStepStint
    : step === 'compare'
      ? t.shellStepCompare
      : t.shellStepSession;
  const progressStep = isSessionMode ? (step === 'stint' ? 2 : 1) : null;

  // Per-stage progress of the session flow (upload once, then session / stint / optimal lap in parallel).
  const stageList = stages && isSessionMode ? [
    ...(stages.uploadState !== 'skipped'
      ? [{ id: 'upload', label: t.perfStageUpload, state: stages.uploadState, pct: stages.upload }] : []),
    { id: 'session', label: t.perfStageSession, state: stages.session },
    { id: 'stint', label: t.perfStageStint, state: stages.stint },
    ...(stages.uploadState === 'done'
      ? [{ id: 'optimal', label: t.perfStageOptimal, state: stages.optimal, counts: false }] : []),
  ] : null;

  const analyzeLabel = isSessionMode ? clean(t.appAnalyzeSession) : clean(t.appAnalyzeCompare(files.length));

  return (
    <>
      <header className="shell-appbar">
        <div className="shell-brand">
          <div className="shell-brand__mark"><Icon name="gauge" size={16} /></div>
          <span className="shell-brand__name">{t.appBrand}</span>
          <span className="shell-brand__ver">{t.appVersion}</span>
        </div>
        <nav className="ui-seg" aria-label={t.libViewSwitch}>
          <button type="button" className="ui-seg__item" aria-pressed={view === 'analysis'} onClick={() => setView('analysis')}>{t.libNavAnalysis}</button>
          <button type="button" className="ui-seg__item" aria-pressed={view === 'library'} onClick={() => setView('library')}>{t.libNavLibrary}</button>
          <button type="button" className="ui-seg__item" aria-pressed={view === 'compare'} onClick={() => { setCompareSeed(null); setView('compare'); }}>{t.libNavCompare}</button>
          <button type="button" className="ui-seg__item" aria-pressed={view === 'settings'} onClick={() => setView('settings')}>{t.libNavSettings}</button>
        </nav>
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
          <ThemeSwitch />
          <PilotEngineerToggle isPilotMode={isPilotMode} onToggle={togglePilotMode} />
        </div>
      </header>

      <div className={`shell-body${hasResults && view === 'analysis' ? ' shell-body--rail' : ''}`}>
        {view === 'library' && (
          <main className="shell-main">
            <LibraryView
              onOpen={handleOpenSaved}
              onCompare={(a, b) => { setCompareSeed({ a, b, k: Date.now() }); setView('compare'); }}
              openedId={savedSession?.id}
            />
          </main>
        )}
        {view === 'settings' && (
          <main className="shell-main">
            <SettingsView />
          </main>
        )}
        {view === 'compare' && (
          <main className="shell-main">
            <CompareSessionsView key={compareSeed?.k ?? 'free'} seed={compareSeed} />
          </main>
        )}
        {hasResults && view === 'analysis' && (
          <Sidebar
            mode={!compareResult ? 'session' : sessionResult ? 'both' : 'compare'}
            isPilotMode={isPilotMode}
            resultKey={`${!!sessionResult}-${!!stintResult}-${!!compareResult}`}
          />
        )}

        <main className={`shell-main${hasResults ? '' : ' shell-main--narrow'}`} hidden={view !== 'analysis'}>
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
                      {t.shellDropHint}
                    </div>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT_ATTR}
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
                      <span className="shell-mode__req">{t.shellOneCsv}</span>
                    </div>
                    <div className="shell-mode__desc">
                      {t.shellModeSessionDesc}
                    </div>
                  </div>
                  <div className={`shell-mode${files.length >= 2 ? ' is-active' : ''}`}>
                    <div className="shell-mode__head">
                      <Icon name="activity" size={16} /> {clean(t.analyzeCompare)}
                      <span className="shell-mode__req">{t.shellTwoCsv}</span>
                    </div>
                    <div className="shell-mode__desc">
                      {t.shellModeCompareDesc}
                    </div>
                  </div>
                </div>

                {files.length > 0 && (
                  <ul className="shell-files" aria-label={t.uploadTitle}>
                    {files.map((f, i) => (
                      <li key={f.name + f.size} className="shell-file">
                        <span className="shell-file__tag" style={{ color: LAP_COLORS[i % LAP_COLORS.length] }}>
                          {isSessionMode ? 'S' : `${t.lapTag}${i + 1}`}
                        </span>
                        <Icon name="file" size={16} className="shell-file__icon" />
                        <span className="shell-file__name shell-trunc" title={f.name}>{f.name}</span>
                        {!isSessionMode && i >= 2 && (
                          <Badge tone="warn">{t.shellNotUsed}</Badge>
                        )}
                        <FormatBadge file={f} />
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

                {loading && stageList && <StageProgress stages={stageList} />}

                {loading && !stageList && (
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
                      {t.shellProgressHint}
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
                      {t.shellAddFile}
                    </span>
                  )}
                  {files.length > 2 && !loading && (
                    <span className="shell-actions__note">
                      {t.shellExtraFiles}
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
                      {isSessionMode ? 'S' : `${t.lapTag}${i + 1}`}
                    </span>
                    <span className="shell-trunc">{f.name}</span>
                    <span className="shell-chip__size">{fmtMB(f.size)}</span>
                  </span>
                ))}
                <CircuitBadge circuit={pickCircuit(stintResult, sessionResult, compareResult)} />
                {savedSession && (
                  <span className="shell-chip" title={t.libSavedFromLibrary(savedSession.title)}>
                    <span style={{ flexShrink: 0, whiteSpace: 'nowrap' }}><Badge tone="accent">{t.libSavedSession}</Badge></span>
                    <span className="shell-trunc">{savedSession.title}</span>
                  </span>
                )}
              </div>
              {isSessionMode && sessionResult && !savedSession && !loading && (
                <SaveToLibrary file={files[0]} sessionResult={sessionResult} stintResult={stintResult} />
              )}
              <button type="button" className="ui-btn ui-btn--sm" onClick={resetAll} disabled={loading || compareLoading}>
                <Icon name="upload" size={14} />
                {t.shellNewAnalysis}
              </button>
            </div>
          )}

          {hasResults && (
            <DataQualityPanel
              session={stintResult?.data_quality ?? sessionResult?.data_quality}
              compare={compareResult?.data_quality}
            />
          )}

          {/* Stage progress stays visible while the remaining stages (stint, optimal lap) finish */}
          {hasResults && loading && stageList && <StageProgress stages={stageList} />}

          {/* ── Session results ── */}
          {sessionResult && (
            <div>
              <section id="section-overview" className="shell-section">
                <SectionHeader
                  icon="grid"
                  title={sectionLabel('section-overview', t)}
                  sub={t.shellOverviewSub}
                  actions={(
                    <button
                      type="button"
                      className="ui-btn ui-btn--sm"
                      onClick={handleSessionPdfDownload}
                      disabled={sessionPdfLoading || loading}
                      aria-label={t.pdfSessionDownloadAria}
                    >
                      {sessionPdfLoading ? <span className="shell-spin" /> : <Icon name="download" size={14} />}
                      {t.pdfSessionDownload}
                    </button>
                  )}
                />
                <SessionKPIs sessionResult={sessionResult} stintResult={stintResult} />

                {sessionResult.track_map?.length > 0 && (
                  <div className="shell-gap">
                    <TrackMap
                      trackData={sessionResult.track_map}
                      corners={markerCorners({ cornerMap: sessionResult.corner_map }).items}
                      cornerLengthM={markerCorners({ cornerMap: sessionResult.corner_map }).lengthM}
                    />
                  </div>
                )}

                {files[0] && (
                  <div className="shell-gap">
                    <OptimalLapPanel file={files[0]} />
                  </div>
                )}
                {!files[0] && savedSession?.extras?.optimal_lap?.available && (
                  <div className="shell-gap">
                    <OptimalLapPanel preloaded={savedSession.extras.optimal_lap} />
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
                    csvMissing={!!savedSession}
                  />
                  {savedSession && <Alert tone="info">{t.libSavedCsvNote}</Alert>}
                </div>
              </section>

              {!stintResult && loading && stages?.stint === 'running' && (
                <section id="section-stint" className="shell-section" aria-busy="true">
                  <SectionHeader icon="trend" title={sectionLabel('section-stint', t)} />
                  <StintSkeleton />
                </section>
              )}

              {stintResult && (
                <section id="section-stint" className="shell-section">
                  <SectionHeader icon="trend" title={sectionLabel('section-stint', t)} />
                  {stintResult.health_summary && <HealthDashboard health_summary={stintResult.health_summary} />}
                  {stintResult.track_evolution?.available && (
                    <Alert tone="info" flush>
                      {t.shellTrackEvolution}: {stintResult.track_evolution.note}
                    </Alert>
                  )}
                  <LapTimelineChart
                    degradacion={stintResult.degradacion}
                    montecarlo={stintResult.montecarlo}
                    laps={stintResult.laps}
                  />
                  {(stintResult.incidents?.available || sessionResult.incidents?.available) && (
                    <div className="shell-gap">
                      <IncidentsPanel data={stintResult.incidents?.available ? stintResult.incidents : sessionResult.incidents} />
                    </div>
                  )}
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
                        cornerMap={stintResult.corner_map}
                        metadata={{
                          label_a: `${t.timelineLap} ${stintResult.curvas_sesion.reference_lap} (${t.anomalyReference})`,
                          label_b: t.avgOfLaps(stintResult.curvas_sesion.n_laps_compared),
                        }}
                        sessionMode
                        referenceLap={stintResult.curvas_sesion.reference_lap}
                        nLaps={stintResult.curvas_sesion.n_laps_compared}
                      />
                    </div>
                  )}
                </section>
              )}

              {stintResult && (stintResult.thermal_analysis?.available || stintResult.setup_sesion?.available || (stintResult.degradacion_neumatico?.available || stintResult.degradacion_neumatico?.reason) || stintResult.racing_line_rl?.available) && (
                <section id="section-setup" className="shell-section">
                  <SectionHeader icon="wrench" title={sectionLabel('section-setup', t)} />
                  {stintResult.thermal_analysis?.available && (
                    <div>
                      <ThermalManagementPanel thermal_analysis={stintResult.thermal_analysis} />
                    </div>
                  )}
                  {stintResult.setup_sesion?.available && (
                    <div className="shell-gap">
                      <SetupSection file={files[0]} setup_advisor={stintResult.setup_sesion} isPilotMode={isPilotMode} savedSetup={!files[0] ? (savedSession?.extras?.setup ?? null) : null} />
                    </div>
                  )}
                  {(stintResult.degradacion_neumatico?.available || stintResult.degradacion_neumatico?.reason) && (
                    <div className="shell-gap">
                      <TyreDegradationPanel data={stintResult.degradacion_neumatico} />
                    </div>
                  )}
                  {stintResult.racing_line_rl?.available && (
                    <div className="shell-gap">
                      <RacingLinePanel data={stintResult.racing_line_rl} cornerMap={stintResult.corner_map} />
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
                setupFile={files[0]}
              />
            </div>
          )}
        </main>
      </div>
    </>
  );
}
