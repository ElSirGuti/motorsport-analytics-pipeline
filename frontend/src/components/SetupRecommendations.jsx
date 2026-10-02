import { useState } from 'react';
import { useLanguage } from '../context/LanguageContext';

const CATEGORY_ICON = {
  'Neumáticos — Camber':     '⊙',
  'Neumáticos — Presión':    '○',
  'Neumáticos — Asimetría':  '↔',
  'Balance Térmico':         '⚖',
  'Frenos — Fade':           '🔥',
  'Frenos — Zonas Críticas': '⚠',
  'Suspensión — ARB Delantero': '▽',
  'Suspensión — ARB Trasero':   '△',
  'Suspensión — Ride Height':   '↕',
  'Suspensión — Pitch de Frenada': '↘',
  'Aerodinámica — Balance':  '✈',
  'Aerodinámica — Ajuste Fino': '✈',
  'Amortiguadores':          '⇅',
  'Suspensión — Muelles':    '⊓',
  'Mecánica / Aero':         '◈',
  'Técnica de Pilotaje':     '◎',
  'Frenada':                 '⬛',
  'Velocidad de Paso':       '◆',
  'Aplicación de Gas':       '▶',
};

function RecCard({ rec, index, isPilotMode }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const PRIORITY_META = {
    alta:    { label: t.priorityHigh, color: '#FF4444', bg: 'rgba(255,68,68,0.12)'    },
    media:   { label: t.priorityMed,  color: '#FFB800', bg: 'rgba(255,184,0,0.12)'    },
    baja:    { label: t.priorityLow,  color: '#00CC66', bg: 'rgba(0,204,102,0.10)'    },
    nominal: { label: 'NOMINAL',      color: '#3A5F8A', bg: 'rgba(58,95,138,0.12)'    },
  };
  const pm  = PRIORITY_META[rec.priority] || PRIORITY_META.baja;
  const icon = CATEGORY_ICON[rec.category] || '•';

  if (isPilotMode) {
    return (
      <div style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${pm.color}33`,
        borderLeft: `3px solid ${pm.color}`,
        borderRadius: 8,
        marginBottom: 8,
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <span style={{ fontSize: 22, minWidth: 28, textAlign: 'center' }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: pm.color, letterSpacing: 1, marginBottom: 4 }}>
            {pm.label}
          </div>
          <p style={{ margin: 0, fontSize: 13, color: '#E0E8F0', fontWeight: 500, lineHeight: 1.4 }}>
            {rec.pilot_note || rec.problem}
          </p>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 12, color: '#00D4FF', fontWeight: 700 }}>{rec.expected_gain}</div>
          <div style={{ fontSize: 9, color: '#506080' }}>potential</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${pm.color}33`,
        borderLeft: `3px solid ${pm.color}`,
        borderRadius: 8,
        marginBottom: 8,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onClick={() => setOpen(o => !o)}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px' }}>
        <span style={{ fontSize: 18, minWidth: 24, textAlign: 'center' }}>{icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: 1,
              color: pm.color, background: pm.bg,
              padding: '2px 6px', borderRadius: 3,
            }}>
              {pm.label}
            </span>
            <span style={{ fontSize: 10, color: '#7080A0', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {rec.category}
            </span>
          </div>
          <p style={{ margin: '3px 0 0', fontSize: 12, color: '#C0C8E0', fontWeight: 500 }}>
            {rec.problem}
          </p>
        </div>
        <div style={{ textAlign: 'right', minWidth: 80 }}>
          <div style={{ fontSize: 11, color: '#00D4FF', fontWeight: 700 }}>{rec.expected_gain}</div>
          <div style={{ fontSize: 9, color: '#506080' }}>{t.setupPotential}</div>
        </div>
        <span style={{ color: '#506080', fontSize: 12, marginLeft: 4 }}>{open ? '▲' : '▼'}</span>
      </div>

      {/* Expanded detail */}
      {open && (
        <div style={{
          padding: '0 14px 14px',
          borderTop: '1px solid rgba(255,255,255,0.05)',
          transition: 'max-height 0.2s ease, opacity 0.2s ease',
          maxHeight: open ? 600 : 0,
          opacity: open ? 1 : 0,
          overflow: 'hidden',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
            <div>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 4 }}>{t.setupRootCause}</div>
              <p style={{ fontSize: 11, color: '#9AAABB', margin: 0, lineHeight: 1.5 }}>
                {rec.root_cause}
              </p>
            </div>
            <div>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 4 }}>{t.setupRec}</div>
              <p style={{ fontSize: 11, color: '#C0D0E0', margin: 0, lineHeight: 1.5, fontWeight: 500 }}>
                {rec.recommendation}
              </p>
            </div>
          </div>
          {rec.detail && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 10, color: '#506080', marginBottom: 2 }}>{t.setupData}</div>
              <p style={{ fontSize: 10, color: '#7088A0', fontFamily: 'monospace', margin: 0 }}>
                {rec.detail}
              </p>
            </div>
          )}
          {rec.solves && (
            <div style={{
              marginTop: 8, padding: '6px 10px',
              background: 'rgba(0,212,255,0.06)',
              borderRadius: 4, borderLeft: '2px solid #00D4FF44',
            }}>
              <span style={{ fontSize: 10, color: '#00D4FF' }}>✓ </span>
              <span style={{ fontSize: 10, color: '#80A0C0' }}>{rec.solves}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SetupRecommendations({ setup_advisor, source, isPilotMode }) {
  const { t } = useLanguage();
  const [filter, setFilter] = useState('all');

  if (!setup_advisor?.available && !setup_advisor?.areas_status?.length) return null;
  const { recommendations = [], areas_status = [], total_gain_range, total_gain_lo, total_gain_hi } = setup_advisor;

  const counts = {
    all:   recommendations.length,
    alta:  recommendations.filter(r => r.priority === 'alta').length,
    media: recommendations.filter(r => r.priority === 'media').length,
    baja:  recommendations.filter(r => r.priority === 'baja').length,
  };
  const visible = filter === 'all'
    ? recommendations
    : recommendations.filter(r => r.priority === filter);

  return (
    <section style={{
      background: 'rgba(10,14,26,0.6)',
      border: '1px solid rgba(0,212,255,0.2)',
      borderRadius: 12,
      padding: 20,
      marginTop: 20,
    }}>
      {source === 'compare' && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)',
          borderRadius: 20, padding: '3px 10px', marginBottom: 12, fontSize: 10,
          color: '#00D4FF', letterSpacing: 0.5,
        }}>
          <span>⚡</span> Post-lap comparison analysis
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, color: '#00D4FF', textTransform: 'uppercase', letterSpacing: 1 }}>
            {t.setupTitle}
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#506080' }}>
            {t.setupSub(recommendations.length)}
          </p>
        </div>
        {/* Total gain badge */}
        {recommendations.length > 0 && total_gain_range && (
          <div style={{
            background: 'rgba(0,212,255,0.08)',
            border: '1px solid rgba(0,212,255,0.25)',
            borderRadius: 8,
            padding: '8px 16px',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1 }}>{t.setupGainLabel}</div>
            <div style={{ fontSize: 20, color: '#00D4FF', fontWeight: 700, fontFamily: 'monospace' }}>
              {total_gain_range}s
            </div>
            <div style={{ fontSize: 9, color: '#406070' }}>{t.setupGainSub}</div>
          </div>
        )}
      </div>

      {/* Area Health grid — engineer only */}
      {!isPilotMode && areas_status?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: '#506080', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8 }}>
            Area Health
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {areas_status.map(area => {
              const STATUS_COLOR = {
                alta:    { text: '#FF4444', bg: 'rgba(255,68,68,0.12)',   border: 'rgba(255,68,68,0.3)' },
                media:   { text: '#FFB800', bg: 'rgba(255,184,0,0.12)',   border: 'rgba(255,184,0,0.3)' },
                baja:    { text: '#00CC66', bg: 'rgba(0,204,102,0.10)',   border: 'rgba(0,204,102,0.25)' },
                nominal: { text: '#4A7AB5', bg: 'rgba(58,95,138,0.10)',   border: 'rgba(58,95,138,0.25)' },
              };
              const sc = STATUS_COLOR[area.status] || STATUS_COLOR.nominal;
              return (
                <div key={area.domain} style={{
                  background: sc.bg, border: `1px solid ${sc.border}`,
                  borderRadius: 6, padding: '5px 10px', minWidth: 90,
                }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: sc.text, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                    {area.status === 'nominal' ? 'OK' : area.status === 'alta' ? 'HIGH' : area.status === 'media' ? 'MED' : 'LOW'}
                  </div>
                  <div style={{ fontSize: 10, color: '#C0C8E0', marginTop: 2 }}>{area.label}</div>
                  {area.n_issues > 0 && (
                    <div style={{ fontSize: 9, color: '#7080A0', marginTop: 1 }}>{area.n_issues} issue{area.n_issues > 1 ? 's' : ''}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Priority filters */}
      {recommendations.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
          {[
            { key: 'all',   label: t.setupFilterAll(counts.all),    color: '#C0C8E0' },
            { key: 'alta',  label: t.setupFilterHigh(counts.alta),  color: '#FF4444' },
            { key: 'media', label: t.setupFilterMed(counts.media),  color: '#FFB800' },
            { key: 'baja',  label: t.setupFilterLow(counts.baja),   color: '#00CC66' },
          ].map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)} style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 11,
              border: `1px solid ${filter === f.key ? f.color : 'rgba(255,255,255,0.1)'}`,
              background: filter === f.key ? `${f.color}22` : 'transparent',
              color: filter === f.key ? f.color : '#506080',
              cursor: 'pointer', transition: 'all 0.15s',
            }}>
              {f.label}
            </button>
          ))}
        </div>
      )}

      {/* Recommendation cards */}
      <div>
        {visible.map((rec, i) => (
          <RecCard key={i} rec={rec} index={i} isPilotMode={isPilotMode} />
        ))}
        {visible.length === 0 && (
          <p style={{ color: '#506080', fontSize: 12, textAlign: 'center', padding: 20 }}>
            {t.setupEmpty}
          </p>
        )}
      </div>

      <p style={{ margin: '12px 0 0', fontSize: 10, color: '#344050', lineHeight: 1.5 }}>
        {t.setupDisclaimer}
      </p>
    </section>
  );
}
