import { useMemo } from 'react';

const CARD = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: 12,
  padding: '16px 20px',
  marginTop: 12,
};

const SECTION_HEADER = {
  fontSize: '0.72rem',
  fontWeight: 700,
  letterSpacing: '0.08em',
  color: 'var(--accent)',
  textTransform: 'uppercase',
  marginBottom: 10,
};

const PRIORITY_COLOR = {
  alta:    '#EF4444',
  media:   '#F59E0B',
  baja:    '#22C55E',
  nominal: '#3A5F8A',
};

const STATUS_COLOR = {
  critical:   '#EF4444',
  warning:    '#F59E0B',
  normal:     '#22C55E',
  ok:         '#22C55E',
  low_delta:  '#F59E0B',
  high_delta: '#F59E0B',
  too_cold:   '#60A5FA',
  suboptimal: '#F59E0B',
  optimal:    '#22C55E',
  hot:        '#F97316',
  critical_brake: '#EF4444',
};

const CORNER_LABELS = { FL: 'Front Left', FR: 'Front Right', RL: 'Rear Left', RR: 'Rear Right' };

function StatusBadge({ status, label }) {
  const color = STATUS_COLOR[status] ?? '#6B7280';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontSize: '0.67rem', fontWeight: 700, letterSpacing: '0.06em',
      background: `${color}15`, border: `1px solid ${color}44`,
      borderRadius: 20, padding: '2px 8px', color,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, display: 'inline-block' }} />
      {label ?? status.toUpperCase().replace('_', ' ')}
    </span>
  );
}

function RecCard({ rec, showCorner = false }) {
  const color = PRIORITY_COLOR[rec.priority] ?? '#6B7280';
  return (
    <div style={{
      background: `${color}08`, border: `1px solid ${color}30`,
      borderRadius: 8, padding: '10px 14px', marginBottom: 8,
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        {showCorner && rec.corner && (
          <span style={{
            fontSize: '0.66rem', fontWeight: 700, letterSpacing: '0.05em',
            background: 'rgba(255,255,255,0.06)', borderRadius: 4,
            padding: '2px 6px', color: 'var(--text-2)',
          }}>
            {CORNER_LABELS[rec.corner] ?? rec.corner}
          </span>
        )}
        <span style={{ fontSize: '0.67rem', color, fontWeight: 700, letterSpacing: '0.05em' }}>
          {rec.priority?.toUpperCase()}
        </span>
      </div>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-1)', lineHeight: 1.5 }}>
        {rec.reason || rec.action}
      </div>
      {rec.target_cold && (
        <div style={{ marginTop: 6, fontSize: '0.68rem', color: 'var(--text-3)' }}>
          Target cold pressure: <strong style={{ color: '#00D4FF' }}>
            {rec.target_cold.bar} bar / {rec.target_cold.psi} PSI
          </strong>
          <span style={{ marginLeft: 8, color: 'var(--text-3)' }}>
            ({rec.direction === 'lower' ? '−' : '+'}{rec.delta_bar} bar / {rec.delta_psi} PSI)
          </span>
        </div>
      )}
    </div>
  );
}

function FluidSection({ data, label }) {
  if (!data?.available) return null;
  const trendSign = data.trend_c_per_lap > 0 ? '+' : '';
  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-1)' }}>{label}</span>
        <StatusBadge status={data.status} label={data.status.toUpperCase()} />
        {data.trend_c_per_lap != null && (
          <span style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginLeft: 'auto' }}>
            {trendSign}{data.trend_c_per_lap}°C / lap
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 20 }}>
        <div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Mean</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-1)', fontFamily: 'monospace' }}>{data.mean_c}°C</div>
        </div>
        <div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Peak</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: STATUS_COLOR[data.status] ?? 'var(--text-1)', fontFamily: 'monospace' }}>{data.max_c}°C</div>
        </div>
        <div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Warn</div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>{data.warn_threshold_c}°C</div>
        </div>
      </div>
      {data.alert && (
        <div style={{
          marginTop: 10, fontSize: '0.71rem', color: STATUS_COLOR[data.status],
          background: `${STATUS_COLOR[data.status]}12`, border: `1px solid ${STATUS_COLOR[data.status]}30`,
          borderRadius: 6, padding: '6px 10px',
        }}>
          {data.alert}
        </div>
      )}
    </div>
  );
}

function BrakeTempSection({ data }) {
  if (!data?.available) return null;
  return (
    <div style={CARD}>
      <div style={SECTION_HEADER}>Brake Temperatures</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
        {Object.entries(data.corners).map(([corner, s]) => {
          const color = STATUS_COLOR[s.status] ?? '#6B7280';
          return (
            <div key={corner} style={{
              background: `${color}08`, border: `1px solid ${color}28`,
              borderRadius: 8, padding: '10px 14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-2)' }}>{CORNER_LABELS[corner]}</span>
                <StatusBadge status={s.status} label={s.status.replace('_', ' ').toUpperCase()} />
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em' }}>MEAN</div>
                  <div style={{ fontSize: '1rem', fontWeight: 700, color, fontFamily: 'monospace' }}>{s.mean_c}°C</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em' }}>PEAK</div>
                  <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-2)', fontFamily: 'monospace' }}>{s.max_c}°C</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {data.balance && (
        <div style={{ fontSize: '0.71rem', color: 'var(--text-3)', marginBottom: 12 }}>
          F/R thermal balance: <strong style={{ color: 'var(--text-1)' }}>
            {data.balance.front_mean_c}°C front</strong> vs <strong style={{ color: 'var(--text-1)' }}>
            {data.balance.rear_mean_c}°C rear</strong>
          {data.balance.ratio_f_r && (
            <span> (ratio {data.balance.ratio_f_r})</span>
          )}
        </div>
      )}

      {data.duct_recs?.length > 0 && (
        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Duct Recommendations
          </div>
          {data.duct_recs.map((rec, i) => (
            <RecCard key={i} rec={{ ...rec, reason: rec.reason }} showCorner />
          ))}
        </div>
      )}

      <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', marginTop: 8, fontStyle: 'italic' }}>
        Optimal window: {data.optimal_range_c?.[0]}–{data.optimal_range_c?.[1]}°C
      </div>
    </div>
  );
}

function TyrePressureSection({ data }) {
  if (!data?.available) return null;
  const hasRecs = data.recommendations?.length > 0;
  return (
    <div style={CARD}>
      <div style={SECTION_HEADER}>Tyre Pressures</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: hasRecs ? 16 : 0 }}>
        {Object.entries(data.corners).map(([corner, s]) => {
          const color = STATUS_COLOR[s.status] ?? '#22C55E';
          return (
            <div key={corner} style={{
              background: `${color}08`, border: `1px solid ${color}28`,
              borderRadius: 8, padding: '10px 14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-2)' }}>{CORNER_LABELS[corner]}</span>
                {s.status !== 'ok' && <StatusBadge status={s.status} label={s.status.replace('_', ' ').toUpperCase()} />}
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em' }}>HOT</div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F97316', fontFamily: 'monospace' }}>
                    {s.hot?.bar} bar
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>
                    {s.hot?.psi} PSI
                  </div>
                </div>
                {s.cold && (
                  <div>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em' }}>COLD</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#60A5FA', fontFamily: 'monospace' }}>
                      {s.cold?.bar} bar
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>
                      {s.cold?.psi} PSI
                    </div>
                  </div>
                )}
                {s.delta && (
                  <div>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em' }}>Δ HOT-COLD</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: color, fontFamily: 'monospace' }}>
                      {s.delta?.bar} bar
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>
                      {s.delta?.psi} PSI
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {hasRecs && (
        <div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Pressure Recommendations
          </div>
          {data.recommendations.map((rec, i) => (
            <RecCard key={i} rec={rec} showCorner />
          ))}
        </div>
      )}

      <div style={{ fontSize: '0.65rem', color: 'var(--text-3)', marginTop: 8, fontStyle: 'italic' }}>
        Target hot-cold delta: {data.delta_target?.bar} bar ({data.delta_target?.psi} PSI) ·
        Window: {data.delta_window?.low?.bar}–{data.delta_window?.high?.bar} bar
      </div>
    </div>
  );
}

function BrakeBiasSection({ data }) {
  if (!data?.available) return null;
  const color = data.recommendation
    ? PRIORITY_COLOR[data.recommendation.priority]
    : '#22C55E';
  return (
    <div style={CARD}>
      <div style={SECTION_HEADER}>Brake Bias</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: data.recommendation || data.out_of_range ? 12 : 0 }}>
        <div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Current (front)</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'monospace', color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
            {data.current_pct}%
          </div>
        </div>
        <div style={{ flex: 1, paddingLeft: 16, borderLeft: '1px solid rgba(255,255,255,0.07)' }}>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Typical Range</div>
          <div style={{ position: 'relative', height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4 }}>
            <div style={{
              position: 'absolute',
              left: `${((data.typical_range?.[0] ?? 50) - 45) / 25 * 100}%`,
              width: `${((data.typical_range?.[1] ?? 65) - (data.typical_range?.[0] ?? 50)) / 25 * 100}%`,
              height: '100%', background: '#22C55E33', borderRadius: 4,
              border: '1px solid #22C55E44',
            }} />
            <div style={{
              position: 'absolute',
              left: `${(data.current_pct - 45) / 25 * 100}%`,
              transform: 'translateX(-50%)',
              width: 3, height: '100%', background: color, borderRadius: 2,
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem', color: 'var(--text-3)', marginTop: 2 }}>
            <span>45%</span><span>70%</span>
          </div>
        </div>
      </div>

      {data.out_of_range && (
        <div style={{
          fontSize: '0.71rem', color: '#F59E0B',
          background: '#F59E0B12', border: '1px solid #F59E0B30',
          borderRadius: 6, padding: '6px 10px', marginBottom: 8,
        }}>
          {data.out_of_range}
        </div>
      )}

      {data.recommendation && (
        <RecCard rec={{
          ...data.recommendation,
          reason: data.recommendation.reason,
        }} />
      )}
    </div>
  );
}

export default function ThermalManagementPanel({ thermal_analysis }) {
  const data = thermal_analysis;
  if (!data?.available) return null;

  const totalRecs = data.n_recommendations ?? 0;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 16,
      padding: '20px 24px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-1)' }}>
          Thermal Management
        </h3>
        {totalRecs > 0 && (
          <span style={{
            fontSize: '0.68rem', fontWeight: 700,
            background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 20, padding: '2px 8px', color: '#EF4444',
          }}>
            {totalRecs} recommendation{totalRecs !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginBottom: 16 }}>
        Engine fluids · brake temperatures · tyre pressures · brake bias
      </div>

      <FluidSection data={data.water_temp} label="Water Temperature" />
      <FluidSection data={data.oil_temp}   label="Oil Temperature" />
      <BrakeTempSection  data={data.brake_temps} />
      <TyrePressureSection data={data.tyre_pressure} />
      <BrakeBiasSection  data={data.brake_bias} />
    </div>
  );
}
