import { useState } from 'react';
import FileUploader from './FileUploader';
import TrackMap from './TrackMap';
import { markerCorners } from '../utils/cornerKind';
import { analyzeSession } from '../api/telemetry';
import { useLanguage } from '../context/LanguageContext';
import { Icon, Panel, Stat, Badge } from './ui';
import css from './SessionTab.module.css';

const clean = (s) => String(s ?? '').replace(/^[^\p{L}\p{N}(]+/u, '');

const formatTime = (seconds) => {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(3);
  return m > 0 ? `${m}:${s.padStart(6, '0')}` : `${Number(s).toFixed(3)}s`;
};

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

  return (
    <div className={css.root}>
      <Panel icon="upload" title={clean(t.sessionLoadTitle)} id="session-upload">
        <FileUploader
          label={t.sessionCsvLabel}
          selectedFile={sessionFile}
          onFileSelect={setSessionFile}
        />

        {error && (
          <div className={css.error} role="alert">
            <Icon name="alert" size={16} />
            <div>
              <div className={css.errorTitle}>{clean(t.errorTitle)}</div>
              {error}
            </div>
          </div>
        )}

        <div className={css.actions}>
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={handleAnalyze}
            disabled={!sessionFile || loading}
            aria-label={loading ? t.sessionAnalyzingAria : t.sessionAnalyzeAria}
          >
            {loading
              ? <><span className={css.spin} /> {clean(t.sessionProcessing)}</>
              : <><Icon name="activity" size={16} /> {clean(t.analyzeSession)}</>
            }
          </button>
        </div>
      </Panel>

      {results && (
        <>
          <Panel flush>
            <div className={css.kpis}>
              <div className={css.kpi}><Stat label={t.validLaps} value={results.total_laps} /></div>
              {results.fastest_lap && (
                <div className={css.kpi}>
                  <Stat
                    label={t.bestLap}
                    value={formatTime(results.fastest_lap.lap_time)}
                    hint={`#${results.fastest_lap.lap_number}`}
                    tone="accent"
                  />
                </div>
              )}
              {results.fastest_lap && (
                <div className={css.kpi}>
                  <Stat
                    label={t.maxSpeed}
                    value={results.fastest_lap.max_speed?.toFixed(0) ?? '—'}
                    hint={clean(t.kmhInBestLap)}
                  />
                </div>
              )}
            </div>
          </Panel>

          {results.track_map && results.track_map.length > 0 && (
            <TrackMap trackData={results.track_map} corners={markerCorners({ cornerMap: results.corner_map }).items} cornerLengthM={markerCorners({ cornerMap: results.corner_map }).lengthM} />
          )}

          {results.laps && results.laps.length > 0 && (
            <Panel icon="flag" title={clean(t.sessionListTitle)} flush>
              <div className={css.scroll}>
                <table className="ui-table">
                  <thead>
                    <tr>
                      <th>{t.lapCol}</th>
                      <th className="is-num">{t.timeCol}</th>
                      <th className="is-num">{t.maxSpeedCol}</th>
                      <th className="is-num">{t.distanceCol}</th>
                      <th className="is-num">{t.deltaCol}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.laps.map((lap) => {
                      const delta = results.fastest_lap
                        ? lap.lap_time - results.fastest_lap.lap_time
                        : null;

                      return (
                        <tr key={lap.lap_number} className={lap.is_fastest ? css.best : undefined}>
                          <td>
                            <span className={css.lapCell}>
                              {lap.lap_number}
                              {lap.is_fastest && <Badge tone="accent">{t.lapBadgeBest}</Badge>}
                              {lap.is_pit_lap && <Badge tone="warn">{t.lapBadgePit}</Badge>}
                              {lap.is_outlier && <Badge tone="bad">{t.lapBadgeOutlier}</Badge>}
                            </span>
                          </td>
                          <td className="is-num">{formatTime(lap.lap_time)}</td>
                          <td className="is-num">{lap.max_speed?.toFixed(1) ?? '—'} km/h</td>
                          <td className="is-num">{lap.lap_distance?.toFixed(0) ?? '—'} m</td>
                          <td className={`is-num ${delta != null && delta > 0 ? css.loss : css.muted}`}>
                            {delta != null && delta > 0 ? `+${delta.toFixed(3)}s` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
};

export default SessionTab;
