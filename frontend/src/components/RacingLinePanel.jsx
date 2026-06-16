const BIN_COLOR = {
  early:   '#00CC66',
  similar: '#00D4FF',
  late:    '#FF4444',
  slow:    '#FF4444',
  fast:    '#00CC66',
};

const BIN_ICON = {
  brake: { early: '◀◀', similar: '▬', late: '▶▶' },
  apex:  { slow: '▼', similar: '◆', fast: '▲' },
  exit:  { late: '◀◀', similar: '▬', early: '▶▶' },
};

const BIN_LABEL = {
  brake: { early: 'Frenada temprana', similar: 'Frenada OK', late: 'Frenada tardía' },
  apex:  { slow: 'Apex lento', similar: 'Apex OK', fast: 'Apex rápido' },
  exit:  { late: 'Gas tardío', similar: 'Gas OK', early: 'Gas temprano' },
};

function PhaseTag({ phase, value, optimal }) {
  const isOpt   = value === optimal;
  const color   = isOpt ? '#00CC66' : BIN_COLOR[value] || '#7080A0';
  const optColor = BIN_COLOR[optimal] || '#00D4FF';
  const label   = BIN_LABEL[phase]?.[value] || value;
  const optLabel = BIN_LABEL[phase]?.[optimal] || optimal;
  const icon    = BIN_ICON[phase]?.[value] || '●';

  return (
    <div style={{
      background: isOpt ? 'rgba(0,204,102,0.06)' : 'rgba(255,255,255,0.03)',
      border: `1px solid ${color}44`,
      borderLeft: `2px solid ${color}`,
      borderRadius: 6,
      padding: '6px 10px',
      fontSize: 11,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: isOpt ? 0 : 4 }}>
        <span style={{ color, fontFamily: 'monospace', fontSize: 12 }}>{icon}</span>
        <span style={{ color: '#9AAABB' }}>{label}</span>
        {isOpt && <span style={{ marginLeft: 'auto', fontSize: 9, color: '#00CC66' }}>✓ ÓPT.</span>}
      </div>
      {!isOpt && (
        <div style={{ fontSize: 10, color: '#506080' }}>
          → objetivo: <span style={{ color: optColor, fontWeight: 600 }}>{optLabel}</span>
        </div>
      )}
    </div>
  );
}

function CornerCard({ corner }) {
  const { corner_number, n_laps, mean_time_loss_s, potential_gain_s,
          current_execution, optimal_execution, already_optimal, recommendations } = corner;

  const gainColor = already_optimal ? '#00CC66'
    : potential_gain_s > 0.15 ? '#FF4444'
    : potential_gain_s > 0.05 ? '#FFB800'
    : '#00CC66';

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${gainColor}33`,
      borderTop: `2px solid ${gainColor}`,
      borderRadius: 8,
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 13, color: '#C0C8E0', fontWeight: 600 }}>Curva {corner_number}</div>
          <div style={{ fontSize: 10, color: '#506080' }}>{n_laps} vueltas · pérdida media {mean_time_loss_s > 0 ? '+' : ''}{mean_time_loss_s.toFixed(3)}s</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 15, fontFamily: 'monospace', fontWeight: 700, color: gainColor }}>
            {already_optimal ? '✓' : `+${potential_gain_s.toFixed(3)}s`}
          </div>
          <div style={{ fontSize: 9, color: '#506080' }}>
            {already_optimal ? 'ya óptimo' : 'ganancia potencial'}
          </div>
        </div>
      </div>

      {/* Phase tags */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 10 }}>
        <PhaseTag phase="brake" value={current_execution.brake} optimal={optimal_execution.brake} />
        <PhaseTag phase="apex"  value={current_execution.apex}  optimal={optimal_execution.apex}  />
        <PhaseTag phase="exit"  value={current_execution.exit}  optimal={optimal_execution.exit}  />
      </div>

      {/* Q-heatmap: 3×3 grid (brake × apex) */}
      <QHeatmap heatmap={corner.q_heatmap} current={current_execution} optimal={optimal_execution} />

      {/* Recommendations */}
      {!already_optimal && recommendations?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {recommendations.map((r, i) => (
            <div key={i} style={{
              fontSize: 10, color: gainColor, padding: '3px 0',
              borderTop: i === 0 ? '1px solid rgba(255,255,255,0.05)' : 'none',
              paddingTop: i === 0 ? 6 : 2,
            }}>
              ▶ {r}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QHeatmap({ heatmap, current, optimal }) {
  if (!heatmap?.length) return null;

  const brakeLabels = ['early', 'similar', 'late'];
  const apexLabels  = ['slow',  'similar', 'fast'];

  const qByKey = {};
  heatmap.forEach(h => { qByKey[`${h.brake}_${h.apex}`] = h; });

  const allQ = heatmap.map(h => h.q).filter(q => q != null);
  const minQ = Math.min(...allQ);
  const maxQ = Math.max(...allQ);
  const range = maxQ - minQ || 1;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 9, color: '#344050', marginBottom: 4, letterSpacing: 0.5 }}>
        Q-TABLE · FRENADA × APEX
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 1fr 1fr', gap: 2, fontSize: 9 }}>
        {/* Header row */}
        <div />
        {apexLabels.map(al => (
          <div key={al} style={{ textAlign: 'center', color: '#344050', padding: '2px 0' }}>
            {al.slice(0, 3).toUpperCase()}
          </div>
        ))}
        {/* Data rows */}
        {brakeLabels.map(bl => (
          <>
            <div key={`lbl_${bl}`} style={{ color: '#344050', display: 'flex', alignItems: 'center' }}>
              {bl.slice(0, 3).toUpperCase()}
            </div>
            {apexLabels.map(al => {
              const cell = qByKey[`${bl}_${al}`];
              const q    = cell?.q;
              const isCurrent = bl === current.brake && al === current.apex;
              const isOptimal = bl === optimal.brake && al === optimal.apex;
              const intensity = q != null ? (q - minQ) / range : 0;

              let bgColor = `rgba(0,212,255,${intensity * 0.35})`;
              if (isOptimal)  bgColor = 'rgba(0,204,102,0.25)';
              if (isCurrent && !isOptimal) bgColor = 'rgba(255,184,0,0.2)';

              return (
                <div
                  key={`${bl}_${al}`}
                  style={{
                    background: bgColor,
                    border: isOptimal
                      ? '1px solid #00CC6699'
                      : isCurrent
                      ? '1px solid #FFB80099'
                      : '1px solid rgba(255,255,255,0.05)',
                    borderRadius: 3,
                    padding: '3px 2px',
                    textAlign: 'center',
                    fontFamily: 'monospace',
                    color: q != null ? '#9AAABB' : '#344050',
                    fontSize: 9,
                    position: 'relative',
                  }}
                  title={cell ? `Q: ${q?.toFixed(4)} | obs: ${cell.count}` : 'no data'}
                >
                  {q != null ? (q > 0 ? '+' : '') + q.toFixed(3) : '—'}
                  {isOptimal && (
                    <span style={{ position: 'absolute', top: 1, right: 2, fontSize: 7, color: '#00CC66' }}>★</span>
                  )}
                </div>
              );
            })}
          </>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 9, color: '#344050' }}>
        <span><span style={{ color: '#00CC66' }}>★</span> Óptimo</span>
        <span><span style={{ color: '#FFB800' }}>■</span> Actual</span>
      </div>
    </div>
  );
}

export default function RacingLinePanel({ data }) {
  if (!data?.available) return null;

  const { corners, total_potential_gain_s, n_corners } = data;

  const byGain  = [...corners].sort((a, b) => b.potential_gain_s - a.potential_gain_s);
  const optimal = corners.filter(c => c.already_optimal).length;

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
            Optimización de Trazada — Aprendizaje por Refuerzo
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#506080' }}>
            Q-learning tabular · {n_corners} curvas · {optimal} ya óptimas
          </p>
        </div>
        <div style={{
          background: 'rgba(0,204,102,0.08)',
          border: '1px solid rgba(0,204,102,0.25)',
          borderRadius: 8, padding: '8px 16px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1 }}>GANANCIA POTENCIAL TOTAL</div>
          <div style={{ fontSize: 20, color: '#00CC66', fontWeight: 700, fontFamily: 'monospace' }}>
            +{total_potential_gain_s.toFixed(3)}s
          </div>
          <div style={{ fontSize: 9, color: '#406070' }}>si se aplica la trazada óptima</div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 14, fontSize: 10, color: '#506080', flexWrap: 'wrap' }}>
        <span><span style={{ color: '#00CC66' }}>■</span> Ya óptimo</span>
        <span><span style={{ color: '#00CC66' }}>▲</span> Apex rápido &nbsp;<span style={{ color: '#FF4444' }}>▼</span> Apex lento</span>
        <span><span style={{ color: '#FF4444' }}>▶▶</span> Frenada tardía &nbsp;<span style={{ color: '#00CC66' }}>◀◀</span> Frenada temprana</span>
      </div>

      {/* Corner cards sorted by potential gain */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {byGain.map((c, i) => (
          <CornerCard key={i} corner={c} />
        ))}
      </div>

      <p style={{ margin: '12px 0 0', fontSize: 10, color: '#344050', lineHeight: 1.5 }}>
        * Q-learning offline entrenado sobre datos de telemetría histórica de la sesión. El agente aprende qué combinación de frenada/apex/gas produjo menor pérdida de tiempo en vueltas pasadas. Las recomendaciones reflejan patrones estadísticos — validar en pista antes de aplicar cambios drásticos.
      </p>
    </section>
  );
}
