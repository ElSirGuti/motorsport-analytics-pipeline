import { useLanguage } from '../context/LanguageContext';
import { Panel, Stat, Badge, Icon } from './ui';
import { clean } from './chartTheme';
import styles from './SummaryCard.module.css';

const SummaryCard = ({ summary, metadata, rawTimeDelta }) => {
  const { t } = useLanguage();
  if (!summary) return null;

  const { total_time_delta, worst_corner, worst_corner_loss, num_corners_analyzed } = summary;
  const displayDelta = rawTimeDelta ?? total_time_delta;
  const isPositive = displayDelta > 0;
  const isNegative = displayDelta < 0;

  const labelB = metadata?.label_b || 'Piloto B';

  return (
    <div className={`${styles.root} fade-up`}>
      {metadata && (
        <div className={styles.identity}>
          <div className={`${styles.id} ${styles.idA}`}>
            <Badge tone="accent">{clean(t.summaryLapA)}</Badge>
            <div className={styles.driver}>{metadata.driver_a || '—'}</div>
            <div className={styles.vehicle}>{metadata.vehicle_a || '—'}</div>
            {metadata.venue && (
              <div className={styles.venue}><Icon name="flag" size={12} />{metadata.venue}</div>
            )}
          </div>

          <div className={styles.vs} aria-hidden="true">{t.summaryVS}</div>

          <div className={`${styles.id} ${styles.idB}`}>
            <Badge>{clean(t.summaryLapB)}</Badge>
            <div className={styles.driver}>{metadata.driver_b || '—'}</div>
            <div className={styles.vehicle}>{metadata.vehicle_b || '—'}</div>
          </div>
        </div>
      )}

      {metadata && !metadata.same_vehicle && (
        <div className={`${styles.alert} ${styles.alertWarn}`} role="status">
          <Icon name="alert" size={16} />
          <strong>{t.summaryDifferentVehicles(metadata.vehicle_a, metadata.vehicle_b)}</strong>
        </div>
      )}

      {metadata && !metadata.same_driver && metadata.same_vehicle && (
        <div className={`${styles.alert} ${styles.alertInfo}`} role="status">
          <Icon name="info" size={16} />
          <span>{t.summarySameDriver(metadata.driver_a, metadata.driver_b)}</span>
        </div>
      )}

      <div className="ui-grid ui-grid--4">
        <Panel>
          <Stat
            label={t.summaryDelta}
            tone={isPositive ? 'bad' : isNegative ? 'ok' : undefined}
            value={`${displayDelta > 0 ? '+' : ''}${displayDelta.toFixed(3)} s`}
            hint={isPositive ? t.summarySlower(labelB) : isNegative ? t.summaryFaster(labelB) : t.summaryIdentical}
          />
        </Panel>

        <Panel>
          <Stat label={t.summaryWorstCorner} tone="warn" value={`#${worst_corner}`} hint={t.summaryLoss(worst_corner_loss)} />
        </Panel>

        <Panel>
          <Stat label={t.summaryCornersAnalyzed} value={num_corners_analyzed} hint={t.summaryAutoDetected} />
        </Panel>

        {metadata?.air_temp !== undefined && (
          <Panel>
            <Stat
              label={t.summaryTemperature}
              value={`${metadata.air_temp.toFixed(1)} °C`}
              hint={`${t.summaryTrack} ${metadata.road_temp ? `${metadata.road_temp.toFixed(1)} °C` : t.summaryNA}`}
            />
          </Panel>
        )}
      </div>
    </div>
  );
};

export default SummaryCard;
