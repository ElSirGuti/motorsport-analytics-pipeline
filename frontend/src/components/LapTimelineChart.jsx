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
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: '0.75rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 6, fontWeight: 600 }}>
        Vuelta {label}
      </div>
      {payload.map((p) => {
        if (!p.value || p.name === 'band_floor' || p.name === 'band_dim_low' ||
            p.name === 'band_bright' || p.name === 'band_dim_high') return null;
        return (
          <div key={p.name} style={{ color: p.color || 'var(--text-1)', marginBottom: 2 }}>
            {p.name}: {fmtLaptime(p.value)}
          </div>
        );
      })}
    </div>
  );
};

const LegendContent = () => (
  <div style={{ display: 'flex', gap: 20, justifyContent: 'center', fontSize: '0.72rem',
    fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-2)', marginTop: 8 }}>
    <span style={{ color: 'var(--cyan)' }}>● Actual</span>
    <span style={{ color: 'rgba(0,212,255,0.4)' }}>╌ Tendencia</span>
    <span style={{ color: 'var(--amber)' }}>╌ Proyección MC</span>
  </div>
);

export default function LapTimelineChart({ degradacion, montecarlo, laps }) {
  const { chartData, separatorLap, yDomain } = useMemo(() => {
    if (!degradacion?.available) return { chartData: [], separatorLap: null, yDomain: ['auto', 'auto'] };

    const actualMap = {};
    (laps || []).forEach(l => { actualMap[l.lap_number] = l.lap_time_s; });

    const trendMap = {};
    (degradacion.trend_laps || []).forEach((lap, i) => {
      trendMap[lap] = degradacion.trend_times[i];
    });

    const mcMap = {};
    const p10Map = {}, p25Map = {}, p75Map = {}, p90Map = {};
    if (montecarlo?.available) {
      (montecarlo.future_laps || []).forEach((lap, i) => {
        mcMap[lap]  = montecarlo.p50[i];
        p10Map[lap] = montecarlo.p10[i];
        p25Map[lap] = montecarlo.p25[i];
        p75Map[lap] = montecarlo.p75[i];
        p90Map[lap] = montecarlo.p90[i];
      });
    }

    const allLaps = new Set([
      ...(degradacion.actual_laps || []),
      ...(degradacion.projected_laps || []),
    ]);

    const sorted = [...allLaps].sort((a, b) => a - b);
    const lastActual = Math.max(...(degradacion.actual_laps || [0]));

    const data = sorted.map(lap => {
      const isProjected = lap > lastActual;
      const p10 = p10Map[lap];
      const p25 = p25Map[lap];
      const p75 = p75Map[lap];
      const p90 = p90Map[lap];

      return {
        lap,
        actual:        actualMap[lap] ?? null,
        trend:         trendMap[lap]  ?? null,
        mc_p50:        mcMap[lap]     ?? null,
        band_floor:    isProjected && p10 != null ? p10 : null,
        band_dim_low:  isProjected && p25 != null && p10 != null ? p25 - p10 : null,
        band_bright:   isProjected && p75 != null && p25 != null ? p75 - p25 : null,
        band_dim_high: isProjected && p90 != null && p75 != null ? p90 - p75 : null,
      };
    });

    const allTimes = [
      ...(degradacion.actual_times || []),
      ...(montecarlo?.p10 || []),
      ...(montecarlo?.p90 || []),
    ].filter(Boolean);

    const minT = Math.min(...allTimes) - 0.5;
    const maxT = Math.max(...allTimes) + 0.5;

    return { chartData: data, separatorLap: lastActual + 0.5, yDomain: [minT, maxT] };
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
          <Legend content={<LegendContent />} />

          {separatorLap && (
            <ReferenceLine
              x={separatorLap}
              stroke="rgba(255,255,255,0.15)"
              strokeDasharray="4 4"
              label={{ value: 'Proyección →', fill: 'var(--text-3)', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          {/* MC bands — stacked areas */}
          <Area dataKey="band_floor"    stackId="mc" fill="transparent"              stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_dim_low"  stackId="mc" fill="rgba(255,179,0,0.07)"     stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_bright"   stackId="mc" fill="rgba(255,179,0,0.18)"     stroke="none" isAnimationActive={false} legendType="none" />
          <Area dataKey="band_dim_high" stackId="mc" fill="rgba(255,179,0,0.07)"     stroke="none" isAnimationActive={false} legendType="none" />

          {/* P50 projection */}
          <Line
            dataKey="mc_p50"
            name="Proyección MC"
            stroke="var(--amber)"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />

          {/* Trend */}
          <Line
            dataKey="trend"
            name="Tendencia"
            stroke="rgba(0,212,255,0.4)"
            strokeWidth={1}
            strokeDasharray="4 4"
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />

          {/* Actual times */}
          <Line
            dataKey="actual"
            name="Actual"
            stroke="var(--cyan)"
            strokeWidth={2}
            dot={{ fill: 'var(--cyan)', r: 4, strokeWidth: 0 }}
            activeDot={{ r: 6 }}
            isAnimationActive={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
