import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';

const PHASE_COLOR = {
  frenada: '#FF6B6B',
  apex:    '#FFD93D',
  salida:  '#6BCB77',
};

function CustomTooltip({ active, payload }) {
  const { t } = useLanguage();
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'rgba(10,14,26,0.95)',
      border: '1px solid rgba(0,212,255,0.3)',
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: 11,
      minWidth: 200,
    }}>
      <div style={{ color: '#00D4FF', fontWeight: 700, marginBottom: 6 }}>
        {t.cornerLabel} {d.corner_number}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '3px 10px', color: '#9AAABB' }}>
        <span>{t.tooltipLoss}</span>
        <span style={{ color: d.time_loss_seconds > 0 ? '#FF4444' : '#00CC66', fontWeight: 700, fontFamily: 'monospace' }}>
          {d.time_loss_seconds > 0 ? '+' : ''}{d.time_loss_seconds.toFixed(3)}s
        </span>
        {d.std_loss_seconds != null && (
          <>
            <span>{t.tooltipStd}</span>
            <span style={{ fontFamily: 'monospace', color: d.std_loss_seconds > 0.08 ? '#FFB800' : '#00CC66' }}>
              ±{d.std_loss_seconds.toFixed(3)}s
            </span>
          </>
        )}
        {d.n_laps != null && (
          <>
            <span>{t.tooltipLaps}</span>
            <span style={{ fontFamily: 'monospace' }}>{d.n_laps}</span>
          </>
        )}
        <span>{t.tooltipBrake}</span>
        <span style={{ fontFamily: 'monospace' }}>{d.braking_delta_meters > 0 ? '+' : ''}{d.braking_delta_meters.toFixed(0)} m</span>
        <span>{t.tooltipApex}</span>
        <span style={{ fontFamily: 'monospace' }}>{d.apex_speed_delta_kmh > 0 ? '+' : ''}{d.apex_speed_delta_kmh.toFixed(1)} km/h</span>
        <span>{t.tooltipThrottle}</span>
        <span style={{ fontFamily: 'monospace' }}>{d.throttle_delta_meters > 0 ? '+' : ''}{d.throttle_delta_meters.toFixed(0)} m</span>
      </div>
      {d.focus && (
        <div style={{ marginTop: 8, padding: '5px 8px', background: 'rgba(0,212,255,0.08)', borderRadius: 4 }}>
          <span style={{ color: '#00D4FF', fontSize: 10 }}>→ {d.focus}</span>
        </div>
      )}
    </div>
  );
}

function PhaseBar({ label, delta, unit, color }) {
  if (Math.abs(delta) < 0.5) return null;
  const sign = delta > 0 ? '+' : '';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: 10, color: '#7080A0', minWidth: 50 }}>{label}</span>
      <div style={{
        flex: 1, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden',
      }}>
        <div style={{
          width: `${Math.min(100, Math.abs(delta) / 30 * 100)}%`,
          height: '100%',
          background: color,
          borderRadius: 2,
        }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: 'monospace', color, minWidth: 52, textAlign: 'right' }}>
        {sign}{delta.toFixed(delta < 10 ? 1 : 0)}{unit}
      </span>
    </div>
  );
}

function TopCornerCard({ c, rank }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel || { frenada: 'Frenada', apex: 'Apex', salida: 'Salida' };
  const dominant = c.dominant_phase;
  const phColor  = PHASE_COLOR[dominant] || '#00D4FF';
  const isLoss   = (c.time_loss_seconds || 0) > 0;
  const valColor = isLoss ? '#FF4444' : '#00CC66';
  const sign     = isLoss ? '+' : '';

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${phColor}44`,
      borderTop: `2px solid ${phColor}`,
      borderRadius: 8,
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{
          width: 24, height: 24, borderRadius: '50%',
          background: phColor + '22', border: `1px solid ${phColor}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: phColor, flexShrink: 0,
        }}>
          {rank}
        </div>
        <div>
          <div style={{ fontSize: 13, color: '#C0C8E0', fontWeight: 600 }}>
            {t.cornerLabel} {c.corner_number}
          </div>
          <div style={{ fontSize: 10, color: '#506080' }}>
            <span style={{ color: phColor }}>{PHASE_LABEL[dominant]}</span>
            {' '}{t.phaseDominant}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ fontSize: 16, fontFamily: 'monospace', fontWeight: 700, color: valColor }}>
            {sign}{c.time_loss_seconds.toFixed(3)}s
          </div>
          <div style={{ fontSize: 9, color: '#506080' }}>{isLoss ? t.cornerLoss : t.cornerGain}</div>
        </div>
      </div>

      <PhaseBar
        label={PHASE_LABEL.frenada}
        delta={c.braking_delta_meters}
        unit=" m"
        color={PHASE_COLOR.frenada}
      />
      <PhaseBar
        label={PHASE_LABEL.apex}
        delta={c.apex_speed_delta_kmh}
        unit=" km/h"
        color={PHASE_COLOR.apex}
      />
      <PhaseBar
        label={PHASE_LABEL.salida}
        delta={c.throttle_delta_meters}
        unit=" m"
        color={PHASE_COLOR.salida}
      />

      {c.focus && (
        <div style={{
          marginTop: 10, padding: '6px 10px',
          background: `${phColor}11`,
          borderLeft: `2px solid ${phColor}`,
          borderRadius: 4,
        }}>
          <span style={{ fontSize: 10, color: phColor, fontWeight: 600 }}>▶ {c.focus}</span>
        </div>
      )}
      {c.description && (
        <p style={{ margin: '6px 0 0', fontSize: 10, color: '#607080', lineHeight: 1.4 }}>
          {c.description}
        </p>
      )}
    </div>
  );
}

export default function CornerAnalysisPanel({ result, metadata, sessionMode, referenceLap, nLaps }) {
  const { t } = useLanguage();
  const PHASE_LABEL = t.phaseLabel || { frenada: 'Frenada', apex: 'Apex', salida: 'Salida' };
  const corners      = result?.corners || [];
  const cornerPrio   = result?.setup_advisor?.corner_priority || [];
  const la = metadata?.label_a || 'A';
  const lb = metadata?.label_b || 'B';

  if (!corners.length) return null;

  const barData = corners
    .filter(c => c.time_loss_seconds != null)
    .map(c => ({
      ...c,
      abs_loss: Math.abs(c.time_loss_seconds || 0),
      ...(cornerPrio.find(cp => cp.corner_number === c.corner_number) || {}),
    }))
    .sort((a, b) => a.corner_number - b.corner_number);

  const totalLoss = corners.reduce((s, c) => s + Math.max(0, c.time_loss_seconds || 0), 0);

  return (
    <section style={{
      background: 'rgba(10,14,26,0.6)',
      border: '1px solid rgba(0,212,255,0.2)',
      borderRadius: 12,
      padding: 20,
      marginTop: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, color: '#00D4FF', textTransform: 'uppercase', letterSpacing: 1 }}>
            {sessionMode ? t.cornerPanelTitleSession : t.cornerPanelTitle}
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#506080' }}>
            {sessionMode
              ? t.cornerDescSession(nLaps, referenceLap)
              : t.cornerDescCompare(lb, la)
            }
          </p>
        </div>
        <div style={{
          background: 'rgba(255,68,68,0.08)',
          border: '1px solid rgba(255,68,68,0.25)',
          borderRadius: 8, padding: '8px 14px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1 }}>{t.cornerTotalLoss}</div>
          <div style={{ fontSize: 20, color: '#FF4444', fontWeight: 700, fontFamily: 'monospace' }}>
            +{totalLoss.toFixed(3)}s
          </div>
        </div>
      </div>

      <div style={{ height: 180, marginBottom: 20 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="corner_number"
              tick={{ fill: '#506080', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              tickLine={false}
              label={{ value: t.cornerLabel, position: 'insideBottom', offset: -2, fill: '#506080', fontSize: 10 }}
            />
            <YAxis
              tick={{ fill: '#506080', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
            />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="time_loss_seconds" radius={[3, 3, 0, 0]} maxBarSize={32}>
              {barData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.time_loss_seconds > 0
                    ? (entry.time_loss_seconds > 0.1 ? '#FF4444' : '#FF8866')
                    : '#00CC66'}
                  opacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 16, fontSize: 10, color: '#506080' }}>
        <span><span style={{ color: '#FF4444' }}>■</span> {t.cornerLosses(lb)}</span>
        <span><span style={{ color: '#00CC66' }}>■</span> {t.cornerGains(lb)}</span>
        <span style={{ marginLeft: 'auto', color: '#304050' }}>
          {t.cornerHover}
        </span>
      </div>

      {cornerPrio.length > 0 && (
        <>
          <div style={{
            fontSize: 11, color: '#506080', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 10, paddingTop: 4,
            borderTop: '1px solid rgba(255,255,255,0.06)',
          }}>
            {t.cornerPriorityTitle}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 10,
          }}>
            {cornerPrio.slice(0, 6).map((c, i) => (
              <TopCornerCard key={i} c={c} rank={i + 1} />
            ))}
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: 16, marginTop: 14, fontSize: 10, flexWrap: 'wrap' }}>
        {Object.entries(PHASE_LABEL).map(([k, v]) => (
          <span key={k}><span style={{ color: PHASE_COLOR[k] }}>●</span> {v}</span>
        ))}
      </div>

    </section>
  );
}
