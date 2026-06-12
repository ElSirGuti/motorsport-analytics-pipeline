import React, { useMemo } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts';

function fmtLaptime(seconds) {
  if (seconds == null || isNaN(seconds) || seconds <= 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m}:${s.padStart(4, '0')}`;
}

function fmtAxis(seconds) {
  if (seconds == null || isNaN(seconds) || seconds <= 0) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  const isPit = point?.pit_actual_time != null;

  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)',
      border: `1px solid ${isPit ? 'rgba(255,61,61,0.3)' : 'rgba(255,255,255,0.07)'}`,
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: '0.75rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: isPit ? '#FF3D3D' : 'var(--text-2)', marginBottom: 6, fontWeight: 600 }}>
        {isPit ? '🔧 Pit Stop · ' : ''}Vuelta {label}
      </div>
      {isPit ? (
        <div style={{ color: '#FF3D3D' }}>
          Tiempo en boxes: {fmtLaptime(point.pit_actual_time)}
        </div>
      ) : (
        payload.map((p) => {
          if (!p.value || ['band_floor','band_dim_low','band_bright','band_dim_high','pit_marker'].includes(p.name)) return null;
          return (
            <div key={p.name} style={{ color: p.color || 'var(--text-1)', marginBottom: 2 }}>
              {p.name}: {fmtLaptime(p.value)}
            </div>
          );
        })
      )}
    </div>
  );
};

const LegendContent = ({ hasPitLaps }) => (
  <div style={{ display: 'flex', gap: 20, justifyContent: 'center', fontSize: '0.72rem',
    fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-2)', marginTop: 8 }}>
    <span style={{ color: 'var(--cyan)' }}>● Actual</span>
    <span style={{ color: 'rgba(0,212,255,0.4)' }}>╌ Tendencia</span>
    <span style={{ color: 'var(--amber)' }}>╌ Proyección MC</span>
    {hasPitLaps && <span style={{ color: '#FF3D3D' }}>● Pit Stop</span>}
  </div>
);

export default function LapTimelineChart({ degradacion, montecarlo, laps }) {
  const { chartData, separatorLap, yDomain, pitLapNums } = useMemo(() => {
    if (!degradacion?.available) return { chartData: [], separatorLap: null, yDomain: ['auto', 'auto'], pitLapNums: new Set() };

    const pitSet = new Set((laps || []).filter(l => l.is_pit_lap).map(l => l.lap_number));
    const pitTimeMap = {};
    const racingMap = {};
    (laps || []).forEach(l => {
      if (l.is_pit_lap) pitTimeMap[l.lap_number] = l.lap_time_s;
      else racingMap[l.lap_number] = l.lap_time_s;
    });

    const trendMap = {};
    (degradacion.trend_laps || []).forEach((lap, i) => { trendMap[lap] = degradacion.trend_times[i]; });

    const mcMap = {}, p10Map = {}, p25Map = {}, p75Map = {}, p90Map = {};
    if (montecarlo?.available) {
      (montecarlo.future_laps || []).forEach((lap, i) => {
        mcMap[lap]  = montecarlo.p50[i];
        p10Map[lap] = montecarlo.p10[i];
        p25Map[lap] = montecarlo.p25[i];
        p75Map[lap] = montecarlo.p75[i];
        p90Map[lap] = montecarlo.p90[i];
      });
    }

    // Y domain from racing laps only — pit laps are not included
    const racingTimes = [
      ...(degradacion.actual_times || []),
      ...(montecarlo?.p10 || []),
      ...(montecarlo?.p90 || []),
    ].filter(t => t != null && !isNaN(t) && t > 0);

    const minT = racingTimes.length ? Math.min(...racingTimes) - 1.0 : 0;
    const maxT = racingTimes.length ? Math.max(...racingTimes) + 1.0 : 300;

    // All laps including pit laps for proper X axis span
    const allLaps = new Set([
      ...(degradacion.actual_laps || []),
      ...(degradacion.projected_laps || []),
      ...Object.keys(pitTimeMap).map(Number),
    ]);
    const lastActual = Math.max(...(degradacion.actual_laps || [0]), ...pitSet);

    const data = [...allLaps].sort((a, b) => a - b).map(lap => {
      const isProjected = lap > lastActual;
      const p10 = p10Map[lap], p25 = p25Map[lap], p75 = p75Map[lap], p90 = p90Map[lap];
      return {
        lap,
        actual:          pitSet.has(lap) ? null : (racingMap[lap] ?? null),
        pit_marker:      pitSet.has(lap) ? minT + (maxT - minT) * 0.025 : null,
        pit_actual_time: pitTimeMap[lap] ?? null,
        trend:           trendMap[lap]  ?? null,
        mc_p50:          mcMap[lap]     ?? null,
        band_floor:    isProjected && p10 != null ? p10 : null,
        band_dim_low:  isProjected && p25 != null && p10 != null ? p25 - p10 : null,
        band_bright:   isProjected && p75 != null && p25 != null ? p75 - p25 : null,
        band_dim_high: isProjected && p90 != null && p75 != null ? p90 - p75 : null,
      };
    });

    return {
      chartData: data,
      separatorLap: lastActual + 0.5,
      yDomain: [minT, maxT],
      pitLapNums: pitSet,
    };
  }, [degradacion, montecarlo, laps]);

  if (!degradacion?.available || chartData.length === 0) {
    return (
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title">◎ Evolución de Tiempos por Vuelta</div>
        </div>
        <div className="chart-empty">
          <span className="chart-empty__icon">◎</span>
          Sin datos de degradación disponibles
        </div>
      </div>
    );
  }

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title">◎ Evolución de Tiempos · Proyección Monte Carlo</div>
        {montecarlo?.available && (
          <span className="chart-zoom-badge">σ = {montecarlo.sigma_real_s}s</span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 24, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="lap"
            tick={{ fill: 'var(--text-3)', fontSize: 11 }}
            label={{ value: 'Vuelta', position: 'insideBottom', offset: -2, fill: 'var(--text-3)', fontSize: 10 }}
          />
          <YAxis
            domain={yDomain}
            tickFormatter={fmtAxis}
            tick={{ fill: 'var(--text-3)', fontSize: 11 }}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend content={<LegendContent hasPitLaps={pitLapNums.size > 0} />} />

          {/* Pit stop vertical markers */}
          {[...pitLapNums].map(lapNum => (
            <ReferenceLine
              key={`pit-${lapNum}`}
              x={lapNum}
              stroke="rgba(255,61,61,0.25)"
              strokeDasharray="3 3"
              label={{ value: '🔧', fill: '#FF3D3D', fontSize: 11, position: 'insideTop' }}
            />
          ))}

          {/* Historical / projected separator */}
          {separatorLap && (
            <ReferenceLine
              x={separatorLap}
              stroke="rgba(255,255,255,0.15)"
              strokeDasharray="4 4"
              label={{ value: 'Proyección →', fill: 'var(--text-3)', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          {/* MC bands — stacked areas */}
          <Area dataKey="band_floor"    stackId="mc" fill="transparent"          stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_dim_low"  stackId="mc" fill="rgba(255,179,0,0.07)" stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_bright"   stackId="mc" fill="rgba(255,179,0,0.18)" stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_dim_high" stackId="mc" fill="rgba(255,179,0,0.07)" stroke="none" isAnimationActive={false} legendType="none" />

          {/* P50 projection */}
          <Line dataKey="mc_p50" name="Proyección MC" stroke="var(--amber)" strokeWidth={1.5}
            strokeDasharray="5 3" dot={false} isAnimationActive={false} connectNulls={false} />

          {/* Trend */}
          <Line dataKey="trend" name="Tendencia" stroke="rgba(0,212,255,0.4)" strokeWidth={1}
            strokeDasharray="4 4" dot={false} isAnimationActive={false} connectNulls={false} />

          {/* Actual racing laps */}
          <Line dataKey="actual" name="Actual" stroke="var(--cyan)" strokeWidth={2}
            dot={{ fill: 'var(--cyan)', r: 4, strokeWidth: 0 }}
            activeDot={{ r: 6 }} isAnimationActive={false} connectNulls={false} />

          {/* Pit stop markers — rendered at the bottom of the Y range */}
          <Line dataKey="pit_marker" name="pit_marker" stroke="none" strokeWidth={0}
            dot={{ fill: '#FF3D3D', r: 5, strokeWidth: 2, stroke: 'rgba(255,61,61,0.4)' }}
            activeDot={{ r: 7 }} isAnimationActive={false} connectNulls={false} legendType="none" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
