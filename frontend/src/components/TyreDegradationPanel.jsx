import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';

const WEAR_COLOR = (pct) => {
  if (pct < 40) return '#00CC66';
  if (pct < 70) return '#FFB800';
  return '#FF4444';
};

function WearGauge({ pct }) {
  const color  = WEAR_COLOR(pct);
  const radius = 52;
  const circ   = 2 * Math.PI * radius;
  const dashOffset = circ * (1 - pct / 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={130} height={75} viewBox="0 0 130 75">
        {/* Background arc (bottom half) */}
        <path
          d="M 13 65 A 52 52 0 0 1 117 65"
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={10}
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          d="M 13 65 A 52 52 0 0 1 117 65"
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 163} 163`}
          style={{ transition: 'stroke-dasharray 0.4s ease' }}
        />
        {/* Value */}
        <text x={65} y={62} textAnchor="middle" fill={color} fontSize={22} fontWeight={700} fontFamily="monospace">
          {Math.round(pct)}%
        </text>
      </svg>
      <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1, textTransform: 'uppercase' }}>
        Current wear
      </div>
    </div>
  );
}

function StatChip({ label, value, color }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8,
      padding: '10px 14px',
      textAlign: 'center',
      flex: 1,
      minWidth: 90,
    }}>
      <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: color || '#C0C8E0' }}>
        {value}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,14,26,0.95)',
      border: '1px solid rgba(0,212,255,0.2)',
      borderRadius: 8, padding: '8px 12px', fontSize: 11,
    }}>
      <div style={{ color: '#00D4FF', marginBottom: 4, fontWeight: 700 }}>Lap {label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: <strong>{p.value != null ? `${p.value > 0 ? '+' : ''}${p.value.toFixed(3)}s` : '—'}</strong>
        </div>
      ))}
    </div>
  );
}

export default function TyreDegradationPanel({ data }) {
  if (!data?.available) return null;

  const {
    wear_pct, remaining_laps, current_delta_s, cliff_threshold_s,
    degradation_rate_s_per_lap, n_laps_analyzed,
    top_wear_factors, lap_data, projection,
    front_temp_trend_c_per_lap, rear_temp_trend_c_per_lap,
    left_mean_temp, right_mean_temp, tyre_temps_available,
  } = data;

  const wearColor = WEAR_COLOR(wear_pct);

  // Merge lap_data + projection for continuous chart
  const chartData = [
    ...lap_data.map(d => ({ lap: d.lap, actual: d.delta, trend: d.trend })),
    ...projection.map(d => ({ lap: d.lap, projected: d.projected, cliff: d.cliff })),
  ];

  const rateSign = degradation_rate_s_per_lap > 0 ? '+' : '';
  const remainingLabel = typeof remaining_laps === 'number'
    ? `${remaining_laps} laps`
    : remaining_laps;

  return (
    <section style={{
      background: 'rgba(10,14,26,0.6)',
      border: '1px solid rgba(0,212,255,0.2)',
      borderRadius: 12,
      padding: 20,
      marginTop: 20,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, color: '#00D4FF', textTransform: 'uppercase', letterSpacing: 1 }}>
            Tyre Degradation Prediction
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#506080' }}>
            Ridge polynomial regression · {n_laps_analyzed} laps analyzed
          </p>
        </div>
        <div style={{ fontSize: 10, color: '#344050', fontFamily: 'monospace' }}>
          ML MODEL: Ridge + Poly(2)
        </div>
      </div>

      {/* Gauge + stats row */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
        <WearGauge pct={wear_pct} />
        <div style={{ display: 'flex', gap: 10, flex: 1, flexWrap: 'wrap' }}>
          <StatChip
            label="Δ Current vs best"
            value={`${current_delta_s > 0 ? '+' : ''}${current_delta_s.toFixed(3)}s`}
            color={current_delta_s > 0.5 ? '#FF4444' : current_delta_s > 0.15 ? '#FFB800' : '#00CC66'}
          />
          <StatChip
            label="Degradation rate"
            value={`${rateSign}${degradation_rate_s_per_lap.toFixed(4)}s/lap`}
            color={degradation_rate_s_per_lap > 0.04 ? '#FF4444' : degradation_rate_s_per_lap > 0.015 ? '#FFB800' : '#00CC66'}
          />
          <StatChip
            label="Remaining laps"
            value={remainingLabel}
            color={
              typeof remaining_laps === 'number'
                ? remaining_laps < 5 ? '#FF4444' : remaining_laps < 15 ? '#FFB800' : '#00CC66'
                : '#00CC66'
            }
          />
          <StatChip
            label="Cliff threshold"
            value={`+${cliff_threshold_s.toFixed(1)}s`}
            color="#506080"
          />
        </div>
      </div>

      {/* Projection chart */}
      <div style={{ height: 200, marginBottom: 20 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="lap"
              tick={{ fill: '#506080', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              tickLine={false}
              label={{ value: 'Lap', position: 'insideBottom', offset: -2, fill: '#506080', fontSize: 10 }}
            />
            <YAxis
              tick={{ fill: '#506080', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
            />
            <ReferenceLine y={cliff_threshold_s} stroke="#FF4444" strokeDasharray="4 2" strokeOpacity={0.5}
              label={{ value: 'Cliff', fill: '#FF4444', fontSize: 9, position: 'right' }} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" />
            <Tooltip content={<CustomTooltip />} />
            <Line
              dataKey="actual"
              name="Δ actual"
              stroke={wearColor}
              strokeWidth={2}
              dot={{ r: 3, fill: wearColor }}
              connectNulls={false}
            />
            <Line
              dataKey="trend"
              name="Trend"
              stroke="rgba(0,212,255,0.5)"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              connectNulls={false}
            />
            <Line
              dataKey="projected"
              name="Projection"
              stroke="rgba(255,184,0,0.6)"
              strokeWidth={1.5}
              strokeDasharray="2 3"
              dot={false}
              connectNulls={false}
            />
            <Legend
              iconType="line"
              wrapperStyle={{ fontSize: 10, color: '#506080', paddingTop: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Axle / side temp trends */}
      {tyre_temps_available && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8, marginBottom: 16 }}>
          {front_temp_trend_c_per_lap != null && (
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 8, padding: '8px 12px',
            }}>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 2 }}>FRONT AXLE</div>
              <div style={{
                fontSize: 14, fontWeight: 700, fontFamily: 'monospace',
                color: Math.abs(front_temp_trend_c_per_lap) > 1.5 ? '#FFB800' : '#C0C8E0',
              }}>
                {front_temp_trend_c_per_lap > 0 ? '+' : ''}{front_temp_trend_c_per_lap.toFixed(2)}°C/lap
              </div>
              <div style={{ fontSize: 9, color: '#344050' }}>thermal trend</div>
            </div>
          )}
          {rear_temp_trend_c_per_lap != null && (
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 8, padding: '8px 12px',
            }}>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 2 }}>REAR AXLE</div>
              <div style={{
                fontSize: 14, fontWeight: 700, fontFamily: 'monospace',
                color: Math.abs(rear_temp_trend_c_per_lap) > 1.5 ? '#FFB800' : '#C0C8E0',
              }}>
                {rear_temp_trend_c_per_lap > 0 ? '+' : ''}{rear_temp_trend_c_per_lap.toFixed(2)}°C/lap
              </div>
              <div style={{ fontSize: 9, color: '#344050' }}>thermal trend</div>
            </div>
          )}
          {left_mean_temp != null && right_mean_temp != null && (
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 8, padding: '8px 12px',
            }}>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 2 }}>L/R ASYMMETRY</div>
              <div style={{
                fontSize: 14, fontWeight: 700, fontFamily: 'monospace',
                color: Math.abs(left_mean_temp - right_mean_temp) > 8 ? '#FFB800' : '#C0C8E0',
              }}>
                {Math.abs(left_mean_temp - right_mean_temp).toFixed(1)}°C
              </div>
              <div style={{ fontSize: 9, color: '#344050' }}>
                L: {left_mean_temp.toFixed(0)}°C · R: {right_mean_temp.toFixed(0)}°C
              </div>
            </div>
          )}
        </div>
      )}

      {/* Top wear factors */}
      {top_wear_factors?.length > 0 && (
        <>
          <div style={{
            fontSize: 11, color: '#506080', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 8,
            borderTop: '1px solid rgba(255,255,255,0.06)',
            paddingTop: 12,
          }}>
            Wear factors (correlation with degradation)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {top_wear_factors.map((f, i) => {
              const FACTOR_LABELS = {
                lap_number:    'Lap number',
                mean_lat_g:    'Mean lateral G',
                mean_brake_g:  'Mean braking G',
                mean_speed:    'Mean speed',
                temp_fl: 'Temp. FL', temp_fr: 'Temp. FR',
                temp_rl: 'Temp. RL', temp_rr: 'Temp. RR',
                stress_fl: 'Thermal stress FL', stress_fr: 'Thermal stress FR',
                stress_rl: 'Thermal stress RL', stress_rr: 'Thermal stress RR',
              };
              const label = FACTOR_LABELS[f.factor] || f.factor;
              const barPct = Math.min(100, f.correlation * 100);
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 10, color: '#7080A0', minWidth: 160 }}>{label}</span>
                  <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                    <div style={{
                      width: `${barPct}%`, height: '100%',
                      background: i === 0 ? '#FF4444' : i === 1 ? '#FFB800' : '#00D4FF',
                      borderRadius: 2,
                    }} />
                  </div>
                  <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#7080A0', minWidth: 36, textAlign: 'right' }}>
                    {(f.correlation * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}

      <p style={{ margin: '12px 0 0', fontSize: 10, color: '#344050', lineHeight: 1.5 }}>
        * Prediction based on polynomial regression over current session data. Accuracy improves with more laps. The "cliff" threshold is a conservative estimate; actual results depend on external factors (track temperature, compound, pressures).
      </p>
    </section>
  );
}
