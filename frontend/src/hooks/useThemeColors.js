import { useMemo } from 'react';
import useTheme from './useTheme';

const TOKENS = {
  surface0: '--surface-0', surface1: '--surface-1', surface2: '--surface-2',
  line: '--line', lineStrong: '--line-strong',
  ink1: '--ink-1', ink2: '--ink-2', ink3: '--ink-3', ink4: '--ink-4',
  accent: '--accent', ok: '--ok', warn: '--warn', bad: '--bad',
  lapA: '--lap-a', lapB: '--lap-b', lapC: '--lap-c', lapD: '--lap-d', lapE: '--lap-e', lapF: '--lap-f',
  heatNeutral: '--heat-neutral', mapCasing: '--map-casing', mapLine: '--map-line', mapHalo: '--map-halo',
};

/** Parses '#rrggbb' / '#rgb' / 'rgb(...)' into [r, g, b]; null if unknown. */
export function parseRgb(v) {
  if (!v) return null;
  let m = /^#([0-9a-f]{6})$/i.exec(v);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  m = /^#([0-9a-f]{3})$/i.exec(v);
  if (m) return [0, 1, 2].map((i) => parseInt(m[1][i] + m[1][i], 16));
  m = /^rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)/i.exec(v);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function readThemeColors() {
  const cs = getComputedStyle(document.documentElement);
  const out = {};
  for (const [k, name] of Object.entries(TOKENS)) out[k] = cs.getPropertyValue(name).trim();
  out.lap = [out.lapA, out.lapB, out.lapC, out.lapD, out.lapE, out.lapF];
  out.rgb = (key) => parseRgb(out[key]);
  return out;
}

/**
 * Computed theme colours as literal strings, for canvas drawing and JS colour maths.
 * Re-evaluates when the theme changes (consumers re-render). SVG/Recharts props can
 * simply use var(--token) strings from chartTheme.js and need no hook.
 */
export default function useThemeColors() {
  const { theme } = useTheme();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `theme` is the invalidation key
  return useMemo(() => readThemeColors(), [theme]);
}
