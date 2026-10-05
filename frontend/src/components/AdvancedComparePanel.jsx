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
import { Panel, Stat, Badge, Icon } from './ui';
import { LAP_COLORS, clean } from './chartTheme';
import styles from './AdvancedComparePanel.module.css';
import FormatBadge from './FormatBadge';
import CircuitBadge from './CircuitBadge';
import { cornerShort, cornerLabel, cornerNameMap } from '../utils/cornerLabel';
import { CornerTags } from './CornerMeta';
import { isDim } from '../utils/cornerTips';
import { isSupportedFile, ACCEPT_ATTR, MAX_FILE_MB } from '../utils/formats';

function FileSlot({ label, color, file, onChange, t }) {
  const [warn, setWarn] = useState(null);
  const id = `adv-${label.replace(/\s+/g, '-')}`;

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!isSupportedFile(f)) { setWarn(t.advValidateCsv); e.target.value = ''; return; }
    if (f.size > MAX_FILE_MB * 1024 * 1024) { setWarn(t.advValidateSize); e.target.value = ''; return; }
    setWarn(null);
    onChange(f);
    e.target.value = '';
  };

  return (
    <div className={styles.slotWrap}>
      <div className={`${styles.slot} ${file ? styles.slotFilled : ''}`} style={{ '--slot-color': color }}>
        <span className={styles.slotDot} />
        <span className={styles.slotLabel}>{clean(label)}</span>
        <span className={`${styles.slotFile} ${file ? '' : styles.slotEmpty}`} title={file?.name}>
          {file ? file.name : t.advNoFile}
        </span>
        {file && <FormatBadge file={file} />}
        <label htmlFor={id} className={`ui-btn ui-btn--sm ${styles.slotBtn}`}>
          <Icon name={file ? 'file' : 'upload'} size={14} />
          {file ? t.advChange : t.advChoose}
        </label>
        <input id={id} type="file" accept={ACCEPT_ATTR} className={styles.srOnly} onChange={handleChange} />
      </div>
      {warn && <div className={styles.warn} role="alert"><Icon name="alert" size={14} />{warn}</div>}
    </div>
  );
}

function MetaCards({ meta, circuit, t }) {
  if (!meta) return null;
  const { driver_fast, driver_slow, vehicle_fast, vehicle_slow,
          venue, delta_total_s, apexes_detected, samples_fast, samples_slow } = meta;

  const sign = delta_total_s > 0 ? '+' : '';

  return (
    <div className="ui-grid ui-grid--4">
      <Panel>
        <Stat
          label={clean(t.advTimeDelta)}
          tone={delta_total_s > 0 ? 'bad' : 'ok'}
          value={`${sign}${delta_total_s?.toFixed(3)} s`}
          hint={delta_total_s > 0 ? t.advSlowLoses : t.advSlowGains}
        />
      </Panel>
      <Panel>
        <Stat label={clean(t.advCircuit)} value={circuit?.recognized ? <CircuitBadge circuit={circuit} /> : <span className={styles.statText}>{venue || '—'}</span>} hint={t.advCornersDetected(apexes_detected)} />
      </Panel>
      <Panel className={styles.lapA}>
        <Stat label={clean(t.advFastLap)} value={<span className={styles.statText}>{driver_fast}</span>} hint={t.advSamples(vehicle_fast, samples_fast)} />
      </Panel>
      <Panel className={styles.lapB}>
        <Stat label={clean(t.advSlowLap)} value={<span className={styles.statText}>{driver_slow}</span>} hint={t.advSamples(vehicle_slow, samples_slow)} />
      </Panel>
    </div>
  );
}

function ApexTable({ apexes, t }) {
  if (!apexes || apexes.length === 0) return null;
  return (
    <Panel icon="map" title={clean(t.advApexMap)} flush>
      <div className={styles.tableScroll}>
        <table className="ui-table">
          <thead>
            <tr>
              <th>{t.advApexNumber}</th>
              <th className="is-num">{t.advApexDistance}</th>
              <th className="is-num">{t.advApexSpeed}</th>
              <th className="is-num">{t.advApexThrottle}</th>
              <th className="is-num">{t.advApexRadius}</th>
              <th>{t.advApexType}</th>
            </tr>
          </thead>
          <tbody>
            {apexes.map((a, i) => {
              const radio = typeof a.min_radius_m === 'number' ? a.min_radius_m : (a.Curvature > 0 ? 1 / a.Curvature : Infinity);
              const tipo = radio > 90 ? t.advCornerTypeFast : radio > 40 ? t.advCornerTypeMedium : t.advCornerTypeSlow;
              const tone = radio > 90 ? 'ok' : radio > 40 ? 'warn' : 'bad';
              return (
                <tr key={a.corner_number ?? i} style={isDim(a) ? { opacity: 0.78 } : undefined}>
                  <td className={styles.muted}>
                    <span className={styles.cornerCell}>{cornerShort(a.corner_number ?? i + 1, a.corner_name)} <CornerTags corner={a} /></span>
                  </td>
                  <td className="is-num">{a.Distance?.toFixed(0)} m</td>
                  <td className="is-num">{a.Speed?.toFixed(1)} km/h</td>
                  <td className="is-num">{a.Throttle?.toFixed(1)} %</td>
                  <td className="is-num">{isFinite(radio) ? `${radio.toFixed(0)} m` : '∞'}</td>
                  <td><Badge tone={tone}>{tipo}</Badge></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

const SEV_TONE = { leve: 'ok', media: 'warn', critico: 'bad' };

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

  const fastName = clean(t.advFastLap);
  const slowName = clean(t.advSlowLap);

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
        lap_labels: { speed_a: results.metadata?.driver_fast || t.fastLabelFallback, speed_b: results.metadata?.driver_slow || t.slowLabelFallback },
      }
    : null;

  const brakeData = results
    ? {
        distance:    (results.telemetria || []).map((r) => r.Distance),
        brake_a:     (results.telemetria || []).map((r) => r.Brake_Fast),
        brake_b:     (results.telemetria || []).map((r) => r.Brake_Slow),
        lap_labels: { brake_a: `${t.brakeThrottleBrake} — ${results.metadata?.driver_fast || fastName}`, brake_b: `${t.brakeThrottleBrake} — ${results.metadata?.driver_slow || slowName}` },
      }
    : null;

  const throttleData = results
    ? {
        distance:      (results.telemetria || []).map((r) => r.Distance),
        throttle_a:    (results.telemetria || []).map((r) => r.Throttle_Fast),
        throttle_b:    (results.telemetria || []).map((r) => r.Throttle_Slow),
        lap_labels: { throttle_a: `${t.brakeThrottleThrottle} — ${results.metadata?.driver_fast || fastName}`, throttle_b: `${t.brakeThrottleThrottle} — ${results.metadata?.driver_slow || slowName}` },
      }
    : null;

  const handleCornerClick = useCallback((domain, cornerNum) => {
    setZoomDomain(domain);
    setActiveCorner(cornerNum ?? null);
  }, []);

  return (
    <div className={styles.root}>
      {/* Upload */}
      <Panel icon="upload" title={clean(t.advTitle)} id="adv-upload" className={styles.upload}>
        <p className={styles.lead}>{t.advDescription}</p>

        <div className={styles.slots}>
          <FileSlot label={t.advFastLabel} color={LAP_COLORS[0]} file={lapFast} onChange={setLapFast} t={t} />
          <FileSlot label={t.advSlowLabel} color={LAP_COLORS[1]} file={lapSlow} onChange={setLapSlow} t={t} />
        </div>

        {loading && step >= 0 && (
          <ol className={styles.steps} aria-live="polite">
            {steps.map((s, i) => (
              <li
                key={s}
                className={`${styles.step} ${i < step ? styles.stepDone : i === step ? styles.stepActive : ''}`}
                aria-current={i === step ? 'step' : undefined}
              >
                <span className={styles.stepMark}>
                  {i < step ? <Icon name="check" size={12} strokeWidth={2.5} /> : i === step ? <span className={styles.spinner} /> : null}
                </span>
                {s}
              </li>
            ))}
          </ol>
        )}

        {error && (
          <div className={styles.error} role="alert">
            <Icon name="alert" size={16} />
            <div>
              <div className={styles.errorTitle}>{t.advErrorTitle}</div>
              {error}
            </div>
          </div>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={handleAnalyze}
            disabled={!lapFast || !lapSlow || loading}
            aria-label={loading ? t.advAnalyzing : clean(t.advRunAnalysis)}
          >
            {loading
              ? <><span className={styles.spinner} /> {t.advProcessing}</>
              : <><Icon name="activity" size={16} />{clean(t.advRunAnalysis)}</>}
          </button>
        </div>
      </Panel>

      {/* Results */}
      {results && (
        <div className={`${styles.results} fade-up`}>
          <MetaCards meta={results.metadata} circuit={results.circuit} t={t} />

          <CurvatureMap curvatura={results.curvatura} apexes={results.apexes} />

          <ApexTable apexes={results.apexes} t={t} />

          <SectorTable
            sectores={results.sectores}
            totalDelta={results.metadata?.delta_total_s}
          />

          <CornerReport
            corners={results.corners}
            onCornerClick={handleCornerClick}
            activeCorner={activeCorner}
            dynamicEvents={results.dynamic_events}
            cornerClusters={results.corner_clusters}
            cornerMap={results.corner_map}
            xgboostPred={results.xgboost_pred}
          />

          {(results.gg_diagram || results.g_limit) && (
            <GGDiagramChart ggData={results.gg_diagram} gLimit={results.g_limit} />
          )}

          {results.dynamic_events && results.dynamic_events.length > 0 && (
            <Panel
              icon="alert"
              title={clean(t.advUndersteerOversteer)}
              actions={<Badge>{t.advEvents(results.dynamic_events.length)}</Badge>}
            >
              <ul className={styles.events}>
                {results.dynamic_events.map((ev, i) => (
                  <li key={i} className={styles.event} style={{ borderLeftColor: `var(--${SEV_TONE[ev.severidad] || 'warn'})` }}>
                    <div className={styles.eventHead}>
                      <strong>{ev.tipo === 'subviraje' ? t.eventSub : t.eventOver}</strong>
                      <span className={styles.muted}>{cornerNameMap(results.corners)[ev.curva] ? cornerLabel(t, ev.curva, cornerNameMap(results.corners)[ev.curva]) : t.eventCorner(ev.curva)}</span>
                      <span className={styles.mono}>{ev.distancia?.toFixed(0)} m</span>
                      <Badge tone={SEV_TONE[ev.severidad]}>{ev.severidad?.toUpperCase()}</Badge>
                    </div>
                    <div className={styles.eventDiag}>{ev.diagnostico}</div>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {results.anomaly && <AnomalyReport anomaly={results.anomaly} />}

          {results.tiempo_potencial && (
            <PotentialLapCard
              tiempoPotencial={results.tiempo_potencial}
              xgboostPred={results.xgboost_pred}
              historySamples={results.metadata?.history_samples}
            />
          )}

          {zoomDomain && (
            <div className={styles.zoomBar} role="status">
              <Icon name="target" size={16} />
              <span className={styles.zoomLabel}>
                {t.advZoom(zoomDomain[0], zoomDomain[1])}
                {activeCorner != null && ` ${t.advZoomCorner(zoomDomain[0], zoomDomain[1], activeCorner)}`}
              </span>
              <button type="button" className="ui-btn ui-btn--sm" onClick={() => { setZoomDomain(null); setActiveCorner(null); }}>
                <Icon name="x" size={14} />
                {t.advFullLap}
              </button>
            </div>
          )}

          <div className={styles.charts}>
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
