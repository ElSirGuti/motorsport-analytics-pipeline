import React, { useState } from 'react';
import FileUploader from './FileUploader';
import TrackMap from './TrackMap';
import { analyzeSession } from '../api/telemetry';

const SessionTab = () => {
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
      setError(err.message || 'Error desconocido al analizar la sesión.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="session-tab">
      <section className="uploader card">
        <h2 className="card__title">
          <span className="card__title-icon">🏁</span>
          Analizar Sesión Completa
        </h2>
        
        <div className="uploader__grid" style={{ gridTemplateColumns: '1fr' }}>
          <FileUploader 
            label="Archivo CSV de Sesión (Múltiples Vueltas)" 
            selectedFile={sessionFile} 
            onFileSelect={setSessionFile} 
          />
        </div>

        {error && (
          <div className="error-message" style={{ marginTop: '1rem' }}>
            ⚠️ {error}
          </div>
        )}

        <button 
          className="btn-analyze" 
          onClick={handleAnalyze} 
          disabled={!sessionFile || loading}
          style={{ marginTop: '1.5rem' }}
        >
          {loading ? (
            <div className="spinner"></div>
          ) : (
            '⚡ Analizar Sesión'
          )}
        </button>
      </section>

      {results && (
        <section className="results animate-in">
          <div className="kpi-grid" style={{ marginBottom: '20px' }}>
            <div className="kpi-card">
              <span className="kpi-card__label">Total Vueltas Válidas</span>
              <span className="kpi-card__value">{results.total_laps}</span>
            </div>
            {results.fastest_lap && (
              <div className="kpi-card">
                <span className="kpi-card__label">Mejor Vuelta (Lap {results.fastest_lap.lap_number})</span>
                <span className="kpi-card__value highlight">
                  {results.fastest_lap.lap_time.toFixed(3)}s
                </span>
              </div>
            )}
          </div>

          {results.track_map && results.track_map.length > 0 && (
            <TrackMap trackData={results.track_map} />
          )}

          <div className="card">
            <h3 className="card__title">Lista de Vueltas</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #333', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Lap</th>
                    <th style={{ padding: '10px' }}>Tiempo</th>
                    <th style={{ padding: '10px' }}>Max Vel.</th>
                    <th style={{ padding: '10px' }}>Distancia</th>
                  </tr>
                </thead>
                <tbody>
                  {results.laps.map(lap => (
                    <tr key={lap.lap_number} style={{ 
                      borderBottom: '1px solid #222',
                      backgroundColor: lap.is_fastest ? 'rgba(0, 212, 255, 0.1)' : 'transparent'
                    }}>
                      <td style={{ padding: '10px' }}>{lap.lap_number} {lap.is_fastest && '⭐'}</td>
                      <td style={{ padding: '10px', color: lap.is_fastest ? '#00D4FF' : '#fff' }}>
                        {lap.lap_time.toFixed(3)}s
                      </td>
                      <td style={{ padding: '10px' }}>{lap.max_speed.toFixed(1)} km/h</td>
                      <td style={{ padding: '10px' }}>{lap.lap_distance.toFixed(0)} m</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default SessionTab;
