import { useState, useCallback } from 'react';

const STORAGE_KEY = 'motorsport_view_mode';

/** Persisted Pilot/Engineer view mode. Returns [isPilotMode, toggle]. */
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
        // storage unavailable - still update state
      }
      return next;
    });
  }, []);

  return [mode === 'pilot', toggleMode];
}
