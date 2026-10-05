// Helpers for the unified corner map (docs/CORNER_DETECTION.md): corner kind, which phases
// were measured, confidence and the per-circuit `corner_map` object. Every helper degrades
// gracefully when the backend runs with CORNER_DETECTION=legacy (no new fields at all).

/** Kinds that have no braking / apex / throttle figures, only a time loss inside their window. */
export const NO_PHASE_KINDS = ['flat_out', 'kink'];
/** Kinds that get a badge ('braking' is the default and shows nothing). */
export const BADGE_KINDS = ['flat_out', 'lift', 'kink'];
export const LOW_CONFIDENCE = 0.6;
export const HIGH_CONFIDENCE = 0.8;

export const cornerNo = (c) => c?.corner_number ?? c?.number ?? null;

/** 'braking' | 'lift' | 'flat_out' | 'kink' | null (legacy payload without the field). */
export const kindOf = (c) => c?.kind ?? c?.corner_kind ?? null;

/** True for corners with no measurable braking / apex / throttle phases. */
export const isNoPhase = (c) => NO_PHASE_KINDS.includes(kindOf(c));

/**
 * Was this phase measured? phase: 'braking' | 'apex' | 'throttle'. A missing flag counts as
 * available (legacy payload). The comparison endpoints also use `<phase>_delta_available`.
 */
export function hasPhase(c, phase) {
  if (!c) return true;
  if (c[`${phase}_available`] === false || c[`${phase}_delta_available`] === false) return false;
  // Payloads that only carry the kind (e.g. racing-line corners): infer what cannot be measured.
  const k = kindOf(c);
  if (NO_PHASE_KINDS.includes(k)) return false;
  if (k === 'lift' && phase === 'braking') return false;
  return true;
}

/** {number: corner} from a `corner_map` object (or a plain list of corners). */
export function cornerMapIndex(cornerMap) {
  const list = Array.isArray(cornerMap) ? cornerMap : cornerMap?.corners;
  const idx = {};
  (list || []).forEach((c) => {
    const n = cornerNo(c);
    if (n != null) idx[n] = c;
  });
  return idx;
}

/** Corner merged with its `corner_map` entry (fields already on `c` win). */
export function withMapInfo(c, idx) {
  const m = idx?.[cornerNo(c)];
  if (!m) return c;
  const out = { ...m, ...c };
  // `name` / `corner_name` can be null on one side and filled on the other.
  out.corner_name = c.corner_name ?? m.name ?? null;
  out.sources = c.sources ?? m.sources;
  return out;
}

/** 'low' (< 0.6) | 'mid' (0.6 - 0.8) | 'high' (>= 0.8) | null (unknown / legacy). */
export function confidenceLevel(c) {
  const v = c?.confidence;
  if (typeof v !== 'number') return null;
  if (v < LOW_CONFIDENCE) return 'low';
  if (v < HIGH_CONFIDENCE) return 'mid';
  return 'high';
}

/** Names the user can read for the evidence behind a corner, from `sources`. */
export function sourceParts(sources) {
  const s = new Set(sources || []);
  const parts = [];
  if (s.has('brake')) parts.push('brake');
  else if (s.has('speed')) parts.push('speed');
  if (s.has('geometry') || s.has('track_geometry')) parts.push('geometry');
  if (s.has('table')) parts.push('table');
  return { parts, telemetry: s.has('brake') || s.has('speed') };
}

/**
 * Corners to draw on a track map: [{number, name, kind, distance}] plus the lap length their
 * distances refer to. Comparison corners (already scaled to lap A) win over the raw corner map.
 */
export function markerCorners({ corners, cornerMap } = {}) {
  const withApex = (corners || []).filter((c) => c && c.apex_distance != null && cornerNo(c) != null);
  if (withApex.length) {
    return {
      lengthM: null,
      items: withApex.map((c) => ({ number: cornerNo(c), name: c.corner_name ?? c.name ?? null, kind: kindOf(c), distance: c.apex_distance })),
    };
  }
  const list = (cornerMap?.corners || []).filter((c) => c && c.apex_distance_m != null);
  return {
    lengthM: cornerMap?.lap_length_m ?? null,
    items: list.map((c) => ({ number: cornerNo(c), name: c.name ?? c.corner_name ?? null, kind: kindOf(c), distance: c.apex_distance_m })),
  };
}
