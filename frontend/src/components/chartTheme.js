// Shared chart constants and helpers.
// Colours are CSS custom properties (var(--...)): SVG presentation attributes resolve them
// at paint time, so every Recharts chart follows the active theme without re-rendering.
// For canvas / JS colour maths use hooks/useThemeColors.js (literal computed values).
export const LAP_COLORS = ['var(--lap-a)', 'var(--lap-b)', 'var(--lap-c)', 'var(--lap-d)', 'var(--lap-e)', 'var(--lap-f)'];
export const COLOR = {
  ok: 'var(--ok)', warn: 'var(--warn)', bad: 'var(--bad)', accent: 'var(--accent)',
  ink1: 'var(--ink-1)', ink2: 'var(--ink-2)', ink3: 'var(--ink-3)', line: 'var(--line)', lineStrong: 'var(--line-strong)',
  halo: 'var(--map-halo)',
};

export const TICK = { fill: COLOR.ink3, fontSize: 11, fontFamily: 'var(--font-mono)' };
export const AXIS_LINE = { stroke: COLOR.lineStrong };
export const GRID_PROPS = { stroke: COLOR.line, strokeOpacity: 0.7, vertical: false };
export const CURSOR = { stroke: COLOR.ink3, strokeDasharray: '3 3', strokeOpacity: 0.7 };
export const ACTIVE_DOT = { r: 3.5, strokeWidth: 0 };

export const fmtDist = (v) => `${Number(v).toFixed(0)}`;

/** Removes leading emoji / decorative glyphs from i18n strings (keeps letters, digits, #). */
export const clean = (s) => (typeof s === 'string' ? s.replace(/^[^\p{L}\p{N}#(]+/u, '').trim() : s);
