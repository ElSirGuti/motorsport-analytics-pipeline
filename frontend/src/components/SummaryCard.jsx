import { useLanguage } from '../context/LanguageContext';

const SummaryCard = ({ summary, metadata, rawTimeDelta }) => {
  const { t } = useLanguage();
  if (!summary) return null;

  const { total_time_delta, worst_corner, worst_corner_loss, num_corners_analyzed } = summary;
  const displayDelta = rawTimeDelta ?? total_time_delta;
  const isPositive = displayDelta > 0;
  const isNegative = displayDelta < 0;

  const labelB = metadata?.label_b || 'Piloto B';

  return (
    <div className="fade-up">
      {metadata && (
        <div className="identity-bar">
          <div className="identity-card identity-card--a">
            <div className="identity-card__badge">{t.summaryLapA}</div>
            <div className="identity-card__driver">{metadata.driver_a || '—'}</div>
            <div className="identity-card__vehicle">{metadata.vehicle_a || '—'}</div>
            {metadata.venue && (
              <div className="identity-card__venue">▶ {metadata.venue}</div>
            )}
          </div>

          <div className="identity-vs">{t.summaryVS}</div>

          <div className="identity-card identity-card--b">
            <div className="identity-card__badge">{t.summaryLapB}</div>
            <div className="identity-card__driver">{metadata.driver_b || '—'}</div>
            <div className="identity-card__vehicle">{metadata.vehicle_b || '—'}</div>
          </div>
        </div>
      )}

      {metadata && !metadata.same_vehicle && (
        <div className="alert-banner alert-banner--warning">
          <span className="alert-banner__icon">⚠</span>
          <span>
            <strong>{t.summaryDifferentVehicles(metadata.vehicle_a, metadata.vehicle_b)}</strong>
          </span>
        </div>
      )}

      {metadata && !metadata.same_driver && metadata.same_vehicle && (
        <div className="alert-banner alert-banner--info">
          <span className="alert-banner__icon">ℹ</span>
          <span>
            {t.summarySameDriver(metadata.driver_a, metadata.driver_b)}
          </span>
        </div>
      )}

      <div className="kpi-grid">
        <div className={`kpi-card ${isPositive ? 'kpi-card--positive' : isNegative ? 'kpi-card--negative' : 'kpi-card--neutral'}`}>
          <div className="kpi-card__label">{t.summaryDelta}</div>
          <div className={`kpi-card__value ${isPositive ? 'kpi-card__value--positive' : isNegative ? 'kpi-card__value--negative' : 'kpi-card__value--neutral'}`}>
            {displayDelta > 0 ? '+' : ''}{displayDelta.toFixed(3)}s
          </div>
          <div className="kpi-card__sub">
            {isPositive
              ? t.summarySlower(labelB)
              : isNegative
              ? t.summaryFaster(labelB)
              : t.summaryIdentical}
          </div>
        </div>

        <div className="kpi-card kpi-card--info">
          <div className="kpi-card__label">{t.summaryWorstCorner}</div>
          <div className="kpi-card__value kpi-card__value--positive">#{worst_corner}</div>
          <div className="kpi-card__sub">{t.summaryLoss(worst_corner_loss)}</div>
        </div>

        <div className="kpi-card kpi-card--info">
          <div className="kpi-card__label">{t.summaryCornersAnalyzed}</div>
          <div className="kpi-card__value kpi-card__value--neutral">{num_corners_analyzed}</div>
          <div className="kpi-card__sub">{t.summaryAutoDetected}</div>
        </div>

        {metadata?.air_temp !== undefined && (
          <div className="kpi-card kpi-card--info">
            <div className="kpi-card__label">{t.summaryTemperature}</div>
            <div className="kpi-card__value kpi-card__value--info" style={{ fontSize: '1.5rem' }}>
              {metadata.air_temp.toFixed(1)}°C
            </div>
            <div className="kpi-card__sub">
              {t.summaryTrack} {metadata.road_temp ? `${metadata.road_temp.toFixed(1)}°C` : t.summaryNA}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SummaryCard;
