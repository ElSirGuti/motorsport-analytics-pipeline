import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';

const CORNERS = ['FL', 'FR', 'RL', 'RR'];

const STATUS_COLOR = {
  fria:          '#4FC3F7',
  suboptima:     '#29B6F6',
  optima:        '#00E676',
  caliente:      '#FFB300',
  sobrecalentada:'#FF3D3D',
  desconocida:   'var(--text-3)',
};

const CORNER_COLORS = { FL: '#00D4FF', FR: '#FF6B6B', RL: '#FFD93D', RR: '#6BCB77' };

const statusToKey = (s) => ({
  fria: 'tyreCold',
  suboptima: 'tyreSuboptimal',
  optima: 'tyreOptimal',
  caliente: 'tyreHot',
  sobrecalentada: 'tyreOverheated',
  desconocida: 'tyreUnknown',
}[s] || 'tyreUnknown');

const cornerLabelKey = (corner) => ({
  FL: 'tyreFL',
  FR: 'tyreFR',
  RL: 'tyreRL',
  RR: 'tyreRR',
}[corner] || 'tyreUnknown');

const renderTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,15,30,0.97)', border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.72rem',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ color: 'var(--text-3)', marginBottom: 4 }}>{Number(label).toFixed(0)}m</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value != null ? `${p.value.toFixed(1)}°C` : '—'}
        </div>
      ))}
    </div>
  );
};

const CornerCard = ({ corner, data, t }) => {
  if (!data) return null;
  const status  = data.window_status || 'desconocida';
  const color   = STATUS_COLOR[status];
  const label   = t[statusToKey(status)];
  const surface = data.surface_mean;
  const core    = data.core_mean;
  const delta   = data.delta_t_mean;
  const dev     = data.window_deviation;
  const stress  = data.high_stress_pct;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: `1px solid ${color}33`,
      borderRadius: 8, padding: '12px 14px', flex: '1 1 120px', minWidth: 120,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-2)', fontWeight: 600 }}>
          {t[cornerLabelKey(corner)]}
        </span>
        <span style={{
          fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.06em',
          color, background: `${color}22`, borderRadius: 4, padding: '2px 6px',
        }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: '1.1rem', fontWeight: 700, color, marginBottom: 4 }}>
        {surface != null ? `${surface.toFixed(0)}°C` : '—'}
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', lineHeight: 1.7 }}>
        {core  != null && <div>{t.tyreCore} {core.toFixed(0)}°C</div>}
        {delta != null && <div>ΔT: {delta > 0 ? '+' : ''}{delta.toFixed(1)}°C</div>}
        {dev   != null && dev !== 0 && (
          <div style={{ color: dev > 0 ? '#FFB300' : '#4FC3F7' }}>
            {dev > 0 ? t.tyreAbove(dev) : t.tyreBelow(Math.abs(dev))}
          </div>
        )}
        {stress > 0 && (
          <div style={{ color: '#FF3D3D' }}>{t.tyreStress} {stress.toFixed(0)}%</div>
        )}
      </div>
    </div>
  );
};

const TyreHeatmap = ({ tyre_analysis, metadata }) => {
  const { t } = useLanguage();
  const lap = tyre_analysis;
  if (!lap?.available) return null;

  const lapA = lap.lap_a;
  const lapB = lap.lap_b;
  const active = lapA?.available ? lapA : lapB;

  const distSeries = useMemo(() => {
    const src = active?.per_distance;
    if (!src?.distance) return [];
    return src.distance.map((d, i) => {
      const row = { distance: d };
      CORNERS.forEach((c) => {
        if (src[`${c}_surface`]) row[`${c}_s`] = src[`${c}_surface`][i];
        if (src[`${c}_core`])    row[`${c}_c`] = src[`${c}_core`][i];
      });
      return row;
    });
  }, [active]);

  const labelA = metadata?.label_a || 'A';
  const labelB = metadata?.label_b || 'B';
  const t_min  = lap.t_min ?? 80;
  const t_max  = lap.t_max ?? 100;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><span>◈</span> {t.tyreTitle}</div>
        <span className="chart-zoom-badge">{t.tyreWindow(t_min, t_max)}</span>
      </div>

      {lapA?.available && (
        <>
          <div style={{ fontSize: '0.72rem', color: '#00D4FF', marginBottom: 8, fontWeight: 600 }}>
            {labelA}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {lapA.corners?.map((c) => (
              <CornerCard key={c.corner} corner={c.corner} data={c} t={t} />
            ))}
          </div>
        </>
      )}

      {lapB?.available && (
        <>
          <div style={{ fontSize: '0.72rem', color: '#FF6B6B', marginBottom: 8, fontWeight: 600 }}>
            {labelB}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {lapB.corners?.map((c) => (
              <CornerCard key={c.corner} corner={c.corner} data={c} t={t} />
            ))}
          </div>
        </>
      )}

      {distSeries.length > 0 && (
        <>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: 8 }}>
            {t.tyreSurface}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={distSeries} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
              <XAxis dataKey="distance" tick={{ fontSize: 10 }} tickFormatter={(v) => `${Number(v).toFixed(0)}m`} />
              <YAxis tick={{ fontSize: 10 }} unit="°C" width={40} domain={['auto', 'auto']} />
              <Tooltip content={renderTooltip} />
              <ReferenceLine y={t_min} stroke="rgba(79,195,247,0.4)" strokeDasharray="4 3" label={{ value: `${t_min}°`, position: 'insideLeft', fontSize: 9, fill: '#4FC3F7' }} />
              <ReferenceLine y={t_max} stroke="rgba(255,179,0,0.4)"  strokeDasharray="4 3" label={{ value: `${t_max}°`, position: 'insideLeft', fontSize: 9, fill: '#FFB300' }} />
              {CORNERS.map((c) => (
                <Line
                  key={c} type="monotone" dataKey={`${c}_s`} name={t[cornerLabelKey(c)]}
                  stroke={CORNER_COLORS[c]} strokeWidth={1.5} dot={false}
                  isAnimationActive={false} connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
};

export default TyreHeatmap;
