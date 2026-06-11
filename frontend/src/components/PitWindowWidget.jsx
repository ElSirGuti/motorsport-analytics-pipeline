import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const FuelTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: '0.72rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>Vuelta {label}</div>
      <div style={{ color: 'var(--amber)' }}>{payload[0]?.value?.toFixed(3)} L</div>
    </div>
  );
};

export default function PitWindowWidget({ combustible }) {
  if (!combustible) return null;

  if (!combustible.available) {
    return (
      <div className="chart-card" style={{ marginBottom: 'var(--s4)' }}>
        <div className="chart-header">
          <div className="chart-title">⛽ Estrategia de Combustible</div>
        </div>
        <div style={{
          background: 'rgba(255,255,255,0.025)',
          border: '1px solid var(--border-1)',
          borderRadius: 8,
          padding: '16px 20px',
          fontSize: '0.78rem',
          color: 'var(--text-3)',
          lineHeight: 1.6,
        }}>
          Canal de combustible no detectado en los CSV. Los canales soportados son:
          Fuel, FuelLevel, FuelMass o equivalentes MoTeC.
        </div>
      </div>
    );
  }

  const { pit_window, combustible_actual_l, consumo_medio_l, consumo_std_l,
          vueltas_restantes_min, vueltas_restantes_max, fuel_per_lap } = combustible;

  const [open, close] = pit_window || [0, 0];
  const lapsLeft = vueltas_restantes_min;

  let bannerMod = '';
  let bannerIcon = '⚠';
  if (lapsLeft >= 5) { bannerMod = 'pit-window-banner--safe'; bannerIcon = '✓'; }
  else if (lapsLeft <= 2) { bannerMod = 'pit-window-banner--urgent'; bannerIcon = '🔴'; }

  const barData = (fuel_per_lap || []).map(r => ({
    lap: r.lap_number,
    burned: parseFloat(r.fuel_burned?.toFixed(3) ?? 0),
  }));

  const needsMoreLaps = (fuel_per_lap?.length ?? 0) < 3;

  return (
    <div className="chart-card" style={{ marginBottom: 'var(--s4)' }}>
      <div className="chart-header">
        <div className="chart-title">⛽ Estrategia de Combustible</div>
        <span style={{
          fontSize: '0.7rem',
          fontFamily: "'JetBrains Mono', monospace",
          color: 'var(--text-3)',
        }}>
          {combustible_actual_l?.toFixed(1)} L restantes
        </span>
      </div>

      {needsMoreLaps ? (
        <div style={{
          background: 'rgba(255,179,0,0.06)',
          border: '1px solid rgba(255,179,0,0.2)',
          borderRadius: 8,
          padding: '12px 16px',
          fontSize: '0.78rem',
          color: 'var(--text-2)',
        }}>
          Necesita más vueltas para calcular la ventana de pit stop con precisión.
        </div>
      ) : (
        <div className={`pit-window-banner ${bannerMod}`}>
          <span className="pit-window-banner__icon">{bannerIcon}</span>
          <div className="pit-window-banner__text">
            <div className="pit-window-banner__title">Ventana de Pit Stop</div>
            <div className="pit-window-banner__laps">
              Vuelta {open} – {close}
            </div>
          </div>
          <div style={{
            textAlign: 'right',
            fontSize: '0.65rem',
            fontFamily: "'JetBrains Mono', monospace",
            color: 'var(--text-3)',
            lineHeight: 1.8,
          }}>
            <div>{vueltas_restantes_min}–{vueltas_restantes_max} vueltas</div>
            <div>{consumo_medio_l?.toFixed(3)} L/v ±{consumo_std_l?.toFixed(3)}</div>
          </div>
        </div>
      )}

      {barData.length > 0 && (
        <div style={{ marginTop: 'var(--s3)' }}>
          <div style={{
            fontSize: '0.62rem',
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-3)',
            marginBottom: 8,
          }}>
            Consumo por Vuelta
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={barData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="lap" tick={{ fill: 'var(--text-3)', fontSize: 10 }} />
              <YAxis
                tick={{ fill: 'var(--text-3)', fontSize: 10 }}
                tickFormatter={v => `${v}L`}
                width={36}
              />
              <Tooltip content={<FuelTooltip />} />
              <Bar
                dataKey="burned"
                fill="var(--amber)"
                fillOpacity={0.7}
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 8,
        marginTop: 'var(--s3)',
      }}>
        {[
          { label: 'Combustible', value: `${combustible_actual_l?.toFixed(1)} L` },
          { label: 'Consumo medio', value: `${consumo_medio_l?.toFixed(3)} L/v` },
          { label: 'Desv. std', value: `±${consumo_std_l?.toFixed(3)} L` },
        ].map(({ label, value }) => (
          <div key={label} style={{
            background: 'var(--bg-glass)',
            border: '1px solid var(--border-1)',
            borderRadius: 6,
            padding: '8px 10px',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-3)', fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
              {label}
            </div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--amber)',
              fontFamily: "'JetBrains Mono', monospace" }}>
              {value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
