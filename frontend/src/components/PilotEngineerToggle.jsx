import React, { useState, useCallback } from 'react';

const STORAGE_KEY = 'motorsport_view_mode';

export function usePilotMode() {
  const [mode, setMode] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) ?? 'engineer';
    } catch {
      return 'engineer';
    }
  });

  const toggleMode = useCallback(() => {
    setMode((prev) => {
      const next = prev === 'engineer' ? 'pilot' : 'engineer';
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // storage unavailable — still update state
      }
      return next;
    });
  }, []);

  return [mode === 'pilot', toggleMode];
}

export default function PilotEngineerToggle({ isPilotMode, onToggle }) {
  const containerStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    background: 'rgba(255,255,255,0.07)',
    borderRadius: '20px',
    padding: '3px',
    gap: '2px',
  };

  const btnBase = {
    padding: '5px 14px',
    borderRadius: '17px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 600,
    letterSpacing: '0.03em',
    transition: 'background 0.15s, color 0.15s',
    outline: 'none',
  };

  const activeStyle = {
    ...btnBase,
    background: '#00D4FF',
    color: '#000',
  };

  const inactiveStyle = {
    ...btnBase,
    background: 'transparent',
    color: '#9CA3AF',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '10px',
    color: '#506080',
    textAlign: 'center',
    marginTop: '4px',
    letterSpacing: '0.03em',
    fontFamily: "'JetBrains Mono', monospace",
  };

  return (
    <div>
      <div style={containerStyle}>
        <button
          style={!isPilotMode ? activeStyle : inactiveStyle}
          onClick={!isPilotMode ? undefined : onToggle}
          aria-pressed={!isPilotMode}
        >
          Engineer
        </button>
        <button
          style={isPilotMode ? activeStyle : inactiveStyle}
          onClick={isPilotMode ? undefined : onToggle}
          aria-pressed={isPilotMode}
        >
          Pilot
        </button>
      </div>
      <span style={labelStyle}>
        {isPilotMode ? 'Pilot mode — technical panels hidden' : 'Engineer mode — full telemetry'}
      </span>
    </div>
  );
}
