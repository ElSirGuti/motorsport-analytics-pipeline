import { useState } from 'react';
import FileUploader from './FileUploader';
import TrackMap from './TrackMap';
import { analyzeSession } from '../api/telemetry';
import { useLanguage } from '../context/LanguageContext';

const SessionTab = () => {
  const { t } = useLanguage();
  const [sessionFile, setSessionFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const handleAnalyze = async () => {
    if (!sessionFile) return;
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeSession(sessionFile);
      setResults(data);
    } catch (err) {
      setError(err.message || t.errorSession);
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds) => {
    if (seconds == null) return '—';
    const m = Math.floor(seconds / 60);
    const s = (seconds % 60).toFixed(3);
    return m > 0 ? `${m}:${s.padStart(6, '0')}` : `${Number(s).toFixed(3)}s`;
  };

  return (
    <div>
      {/* Upload section */}
      <section className="section card" aria-label={t.uploadAria}>
        <div className="card__title">
          <span className="card__title-icon">▦</span>
          {t.sessionLoadTitle}
        </div>

        <div style={{ marginBottom: 'var(--s4)' }}>
          <FileUploader
            label={t.sessionCsvLabel}
            selectedFile={sessionFile}
            onFileSelect={setSessionFile}
          />
        </div>

        {error && (
          <div className="error-banner" role="alert" style={{ marginBottom: 'var(--s3)' }}>
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
          disabled={!sessionFile || loading}
          aria-label={loading ? t.sessionAnalyzingAria : t.sessionAnalyzeAria}
        >
          {loading
            ? <><div className="spinner" /> {t.sessionProcessing}</>
            : `⚡ ${t.analyzeSession}`
          }
        </button>
      </section>

      {/* Results */}
      {results && (
        <div className="fade-up">
          {/* KPI summary */}
          <div className="kpi-grid" style={{ marginBottom: 'var(--s5)' }}>
            <div className="kpi-card kpi-card--info">
              <div className="kpi-card__label">{t.validLaps}</div>
              <div className="kpi-card__value kpi-card__value--neutral">{results.total_laps}</div>
            </div>

            {results.fastest_lap && (
              <div className="kpi-card kpi-card--negative">
                <div className="kpi-card__label">{t.bestLap}</div>
                <div className="kpi-card__value kpi-card__value--neutral">
                  #{results.fastest_lap.lap_number}
                </div>
                <div className="kpi-card__sub">{formatTime(results.fastest_lap.lap_time)}</div>
              </div>
            )}

            {results.fastest_lap && (
              <div className="kpi-card kpi-card--info">
                <div className="kpi-card__label">{t.maxSpeed}</div>
                <div className="kpi-card__value kpi-card__value--info" style={{ fontSize: '1.5rem' }}>
                  {results.fastest_lap.max_speed?.toFixed(0) ?? '—'}
                </div>
                <div className="kpi-card__sub">{t.kmhInBestLap}</div>
              </div>
            )}
          </div>

          {results.track_map && results.track_map.length > 0 && (
            <div style={{ marginBottom: 'var(--s5)' }}>
              <TrackMap trackData={results.track_map} />
            </div>
          )}

          {/* Lap table */}
          {results.laps && results.laps.length > 0 && (
            <div className="card">
              <div className="card__title">
                <span className="card__title-icon">▤</span>
                {t.sessionListTitle}
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="session-lap-table">
                  <thead>
                    <tr>
                      <th>{t.lapCol}</th>
                      <th>{t.timeCol}</th>
                      <th>{t.maxSpeedCol}</th>
                      <th>{t.distanceCol}</th>
                      <th>{t.deltaCol}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.laps.map((lap) => {
                      const delta = results.fastest_lap
                        ? lap.lap_time - results.fastest_lap.lap_time
                        : null;

                      return (
                        <tr key={lap.lap_number} className={lap.is_fastest ? 'row-fastest' : ''}>
                          <td className="td-lap-num">
                            {lap.lap_number}
                            {lap.is_fastest && (
                              <span style={{ marginLeft: '6px', color: 'var(--cyan)', fontSize: '0.7rem' }}>
                                BEST
                              </span>
                            )}
                          </td>
                          <td className={`td-time ${lap.is_fastest ? '' : ''}`}>
                            {formatTime(lap.lap_time)}
                          </td>
                          <td>{lap.max_speed?.toFixed(1) ?? '—'} km/h</td>
                          <td>{lap.lap_distance?.toFixed(0) ?? '—'} m</td>
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
          )}
        </div>
      )}
    </div>
  );
};

export default SessionTab;
