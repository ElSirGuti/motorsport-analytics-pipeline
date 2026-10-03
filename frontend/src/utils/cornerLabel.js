// Shared corner / circuit labels. Corner names come from the backend (`corner_name`,
// null when the circuit is unknown or the apex has no tabulated name), so every
// panel shows the same text: "Corner 4 · Tamburello" or just "Corner 4".

/** "Corner 4 · Tamburello" / "Curva 4 · Tamburello" (plain "Corner 4" without a name). */
export function cornerLabel(t, number, name) {
  const base = `${t.cornerLabel} ${number}`;
  return name ? `${base} · ${name}` : base;
}

/** Compact form for tight columns and axes: "4 · Tamburello" (just "4" without a name). */
export function cornerShort(number, name) {
  return name ? `${number} · ${name}` : String(number);
}

/** {corner_number: corner_name} for the corners that have a name. */
export function cornerNameMap(corners) {
  const map = {};
  (corners || []).forEach((c) => {
    if (c && c.corner_number != null && c.corner_name) map[c.corner_number] = c.corner_name;
  });
  return map;
}

/** Localised country name from an ISO 3166-1 alpha-2 code ("IT" -> "Italia" / "Italy"). */
export function countryName(code, lang) {
  if (!code) return '';
  try {
    return new Intl.DisplayNames([lang || 'en'], { type: 'region' }).of(code) || code;
  } catch {
    return code;
  }
}

/** First available `circuit` object among several API results. */
export function pickCircuit(...results) {
  for (const r of results) {
    if (r && r.circuit && typeof r.circuit === 'object') return r.circuit;
  }
  return null;
}

/**
 * Sector label. With corner names: "Tamburello → Villeneuve"; an unnamed end falls back
 * to "Corner N" and the lap start / finish to the localised words. Returns null when
 * neither end has a name, so the caller keeps the backend description.
 */
export function sectorLabel(t, s) {
  if (!s || (!s.from_corner_name && !s.to_corner_name)) return null;
  const end = (num, name, edge) => (name || (num != null ? cornerLabel(t, num) : edge));
  return `${end(s.from_corner_number, s.from_corner_name, t.sectorStartLine)} → ${end(s.to_corner_number, s.to_corner_name, t.sectorFinishLine)}`;
}
