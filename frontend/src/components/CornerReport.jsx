import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import { cornerLabel } from '../utils/cornerLabel';
import { cornerMapIndex, withMapInfo, hasPhase, isNoPhase } from '../utils/cornerKind';
import { CornerTags, CornerMapNotice, NoPhaseNote } from './CornerMeta';
import { isDim } from '../utils/cornerTips';
import styles from './CornerReport.module.css';

const SEV_MAP = { leve: 'severityLeve', media: 'severityMedia', critico: 'severityCritico' };
const SEV_TONE = { leve: 'ok', media: 'warn', critico: 'bad' };

const toneClass = (tone) => (tone === 'good' ? styles.good : tone === 'bad' ? styles.bad : styles.neutral);

const CornerReport = ({ corners: rawCorners, onCornerClick, activeCorner, dynamicEvents, cornerClusters, xgboostPred, cornerMap }) => {
  const { t } = useLanguage();

  const CLUSTER_TONE = {
    [t.clusterAttack]:       'ok',
    [t.clusterAggressive]:   'warn',
    [t.clusterConservative]: 'accent',
    [t.clusterLateExit]:     'warn',
    [t.clusterErratic]:      'bad',
    [t.clusterConsistent]:   'accent',
  };

  if (!rawCorners || rawCorners.length === 0) return null;
  const mapIdx = cornerMapIndex(cornerMap);
  const corners = rawCorners.map((c) => withMapInfo(c, mapIdx));

  const eventsByCorner = {};
  if (dynamicEvents && dynamicEvents.length > 0) {
    dynamicEvents.forEach((ev) => {
      if (!eventsByCorner[ev.curva]) eventsByCorner[ev.curva] = [];
      eventsByCorner[ev.curva].push(ev);
    });
  }

  const clusterByCorner = {};
  if (cornerClusters && cornerClusters.length > 0) {
    cornerClusters.forEach((c) => { clusterByCorner[c.corner_number] = c; });
  }

  const xgbByCorner = {};
  if (xgboostPred?.corner_predictions) {
    xgboostPred.corner_predictions.forEach((p) => { xgbByCorner[p.corner_number] = p; });
  }

  const activeName = corners.find((c) => c.corner_number === activeCorner)?.corner_name;

  return (
    <Panel
      icon="flag"
      title={t.cornerReportTitle}
      actions={activeCorner != null && <Badge tone="accent">{t.cornerReportSelected(activeCorner)}{activeName ? ` · ${activeName}` : ''}</Badge>}
      className="fade-up fade-up--d4"
    >
      <CornerMapNotice cornerMap={cornerMap} />
      <div className={styles.grid}>
        {[...corners].sort((a, b) => a.corner_number - b.corner_number).map((corner) => {
          const isLoss   = corner.time_loss_seconds > 0.01;
          const isGain   = corner.time_loss_seconds < -0.01;
          const isActive = activeCorner === corner.corner_number;
          const hasZoom  = corner.start_distance != null && corner.end_distance != null;

          const status = isLoss ? styles.loss : isGain ? styles.gain : '';
          const deltaTone = isLoss ? styles.bad : isGain ? styles.good : styles.neutral;

          const noPhase = isNoPhase(corner);
          const brakeOk = hasPhase(corner, 'braking');
          const apexOk = hasPhase(corner, 'apex');
          const throttleOk = hasPhase(corner, 'throttle');
          const brakeDelta = corner.braking_delta_meters;
          const apexDelta  = corner.apex_speed_delta_kmh;
          const throttleDelta = corner.throttle_delta_meters;
          const cluster = clusterByCorner[corner.corner_number];
          const consistency = corner.consistency_pct;
          const consTone = consistency >= 80 ? styles.good : consistency >= 50 ? styles.warn : styles.bad;
          const consBar = consistency >= 80 ? 'var(--ok)' : consistency >= 50 ? 'var(--warn)' : 'var(--bad)';

          return (
            <div
              key={corner.corner_number}
              className={`${styles.card} ${status} ${hasZoom ? styles.clickable : ''} ${isActive ? styles.active : ''} ${isDim(corner) ? styles.dim : ''}`}
              onClick={() => {
                if (!onCornerClick || !hasZoom) return;
                onCornerClick(
                  isActive ? null : [Math.max(0, corner.start_distance - 50), corner.end_distance + 50],
                  isActive ? null : corner.corner_number
                );
              }}
              role={hasZoom ? 'button' : undefined}
              aria-label={hasZoom ? cornerLabel(t, corner.corner_number, corner.corner_name) : undefined}
              aria-pressed={hasZoom ? isActive : undefined}
              tabIndex={hasZoom ? 0 : undefined}
              onKeyDown={hasZoom ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } } : undefined}
              title={hasZoom ? (isActive ? t.cornerReportZoomOut : t.cornerReportZoomIn) : ''}
            >
              <div className={styles.head}>
                <div>
                  <div className={styles.name}>{cornerLabel(t, corner.corner_number, corner.corner_name)}</div>
                  <CornerTags corner={corner} />
                  {corner.start_distance != null && (
                    <div className={styles.zone}>
                      {corner.start_distance.toFixed(0)} – {corner.end_distance.toFixed(0)} m
                    </div>
                  )}
                </div>
                <div className={styles.headRight}>
                  <div className={`${styles.delta} ${deltaTone}`}>
                    {corner.time_loss_seconds > 0 ? '+' : ''}{corner.time_loss_seconds.toFixed(3)} s
                  </div>
                  {hasZoom && (
                    <span className={styles.zoomHint}>
                      <Icon name={isActive ? 'x' : 'target'} size={12} />
                      {isActive ? t.zoomBadge : ''}
                    </span>
                  )}
                </div>
              </div>

              {noPhase ? <NoPhaseNote corner={corner} /> : (
              <dl className={styles.metrics}>
                <div className={styles.metric}>
                  <dt>{t.cornerReportBrakePoint}</dt>
                  <dd className={toneClass(brakeOk && brakeDelta < -2 ? 'bad' : brakeOk && brakeDelta > 2 ? 'good' : 'n')} title={brakeOk ? undefined : t.cmNoPhaseTip}>
                    {!brakeOk ? '—' : brakeDelta < 0
                      ? t.cornerReportBefore(Math.abs(brakeDelta).toFixed(0))
                      : brakeDelta > 0
                      ? t.cornerReportAfter(brakeDelta.toFixed(0))
                      : t.cornerReportSimilar}
                  </dd>
                </div>
                <div className={styles.metric}>
                  <dt>{t.cornerReportApexSpeed}</dt>
                  <dd className={toneClass(apexOk && apexDelta < -1 ? 'bad' : apexOk && apexDelta > 1 ? 'good' : 'n')} title={apexOk ? undefined : t.cmNoPhaseTip}>
                    {apexOk ? `${apexDelta > 0 ? '+' : ''}${apexDelta.toFixed(1)} km/h` : '—'}
                  </dd>
                </div>
                <div className={styles.metric}>
                  <dt>{t.cornerReportAcceleration}</dt>
                  <dd className={toneClass(throttleOk && throttleDelta > 2 ? 'bad' : throttleOk && throttleDelta < -2 ? 'good' : 'n')} title={throttleOk ? undefined : t.cmNoPhaseTip}>
                    {!throttleOk ? '—' : throttleDelta > 0
                      ? t.cornerReportAfter(throttleDelta.toFixed(0))
                      : throttleDelta < 0
                      ? t.cornerReportBefore(Math.abs(throttleDelta).toFixed(0))
                      : t.cornerReportSimilar}
                  </dd>
                </div>
              </dl>
              )}

              {(eventsByCorner[corner.corner_number] || cluster) && (
                <div className={styles.badges}>
                  {(eventsByCorner[corner.corner_number] || []).map((ev, ei) => (
                    <Badge key={ei} tone={SEV_TONE[ev.severidad] || 'warn'} title={ev.diagnostico}>
                      {ev.tipo === 'subviraje' ? t.eventSub : t.eventOver} · {t[SEV_MAP[ev.severidad]] || ev.severidad?.toUpperCase()}
                    </Badge>
                  ))}
                  {cluster && <Badge tone={CLUSTER_TONE[cluster.perfil]}>{cluster.perfil}</Badge>}
                </div>
              )}

              {consistency != null && corner.n_hist_samples >= 3 && (
                <div className={styles.consistency}>
                  <div className={styles.bar}>
                    <div className={styles.barFill} style={{ width: `${consistency}%`, background: consBar }} />
                  </div>
                  <span className={consTone}>{t.cornerReportConsistent(consistency.toFixed(0))}</span>
                  <span className={styles.muted}>{t.cornerReportLaps(corner.n_hist_samples)}</span>
                </div>
              )}

              {xgbByCorner[corner.corner_number]?.explanations?.length > 0 && (
                <ul className={styles.chips}>
                  {xgbByCorner[corner.corner_number].explanations.map((exp, ei) => (
                    <li key={ei} className={styles.chip}>
                      <span className={styles.chipFeature}>{exp.feature}</span>
                      <span className={styles.bad}>{exp.gap > 0 ? '+' : ''}{exp.gap.toFixed(1)}{exp.unit}</span>
                      <span className={styles.muted}>{t.cornerReportOptimal} {exp.optimal.toFixed(1)}{exp.unit}</span>
                    </li>
                  ))}
                </ul>
              )}

              {corner.description && <div className={styles.desc}>{corner.description}</div>}
            </div>
          );
        })}
      </div>
    </Panel>
  );
};

export default CornerReport;
