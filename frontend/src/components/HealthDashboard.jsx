import React from 'react';

const STATUS_COLOR = {
  ok: '#22C55E',
  warning: '#F59E0B',
  unavailable: '#6B7280',
};

const OVERALL_CONFIG = {
  ok:       { label: 'ALL SYSTEMS GO', bg: '#22C55E', color: '#000' },
  warning:  { label: 'CHECK MODULES',  bg: '#F59E0B', color: '#000' },
  critical: { label: 'DATA LIMITED',   bg: '#EF4444', color: '#fff' },
};

const MODULE_LABELS = {
  thermal:      'Thermal',
  setup:        'Setup',
  tyre_degradation: 'Tyre Deg',
  racing_line:  'Racing Line',
  slip:         'Slip',
  corners:      'Corners',
};

export default function HealthDashboard({ health_summary }) {
  if (!health_summary) return null;

  const overall = OVERALL_CONFIG[health_summary.overall] ?? OVERALL_CONFIG.critical;

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '44px',
    padding: '0 12px',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '8px',
    gap: '12px',
  };

  const overallBadgeStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    borderRadius: '20px',
    background: overall.bg,
    color: overall.color,
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.06em',
    whiteSpace: 'nowrap',
    flexShrink: 0,
  };

  const dotStyle = (color) => ({
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
  });

  const modulesRowStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexWrap: 'nowrap',
    overflow: 'hidden',
  };

  const chipStyle = (status) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '3px 8px',
    borderRadius: '12px',
    background: 'rgba(255,255,255,0.06)',
    border: `1px solid ${STATUS_COLOR[status] ?? STATUS_COLOR.unavailable}33`,
    fontSize: '11px',
    color: STATUS_COLOR[status] ?? STATUS_COLOR.unavailable,
    whiteSpace: 'nowrap',
    fontWeight: 500,
  });

  return (
    <div style={containerStyle}>
      <div style={overallBadgeStyle}>
        <span style={dotStyle(overall.color === '#000' ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.5)')} />
        {overall.label}
      </div>

      <div style={modulesRowStyle}>
        {Object.entries(MODULE_LABELS).map(([key, label]) => {
          const status = health_summary[key] ?? 'unavailable';
          return (
            <div key={key} style={chipStyle(status)}>
              <span style={dotStyle(STATUS_COLOR[status] ?? STATUS_COLOR.unavailable)} />
              {label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
