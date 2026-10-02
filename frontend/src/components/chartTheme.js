// Shared chart constants and helpers.
// Hex values of --lap-a..f (Recharts needs literal colours for series).
export const LAP_COLORS = ['#4da3ff', '#f0616d', '#3dd68c', '#f5a524', '#c084fc', '#2dd4bf'];
export const COLOR = {
  ok: '#3dd68c', warn: '#f5a524', bad: '#f0616d', accent: '#4da3ff',
  ink2: '#a3adbb', ink3: '#6f7a8a', line: '#262d38', lineStrong: '#323b48',
};

export const TICK = { fill: COLOR.ink3, fontSize: 11, fontFamily: 'var(--font-mono)' };
export const AXIS_LINE = { stroke: COLOR.lineStrong };
export const GRID_PROPS = { stroke: COLOR.line, strokeOpacity: 0.7, vertical: false };
export const CURSOR = { stroke: COLOR.ink3, strokeDasharray: '3 3', strokeOpacity: 0.7 };
export const ACTIVE_DOT = { r: 3.5, strokeWidth: 0 };

export const fmtDist = (v) => `${Number(v).toFixed(0)}`;

/** Removes leading emoji / decorative glyphs from i18n strings (keeps letters, digits, #). */
export const clean = (s) => (typeof s === 'string' ? s.replace(/^[^\p{L}\p{N}#(]+/u, '').trim() : s);
