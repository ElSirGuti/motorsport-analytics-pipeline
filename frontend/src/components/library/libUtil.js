// Pequeñas utilidades de formato compartidas por las vistas de la biblioteca.

export function fmtLap(s) {
  if (s == null || Number.isNaN(Number(s)) || Number(s) <= 0) return '—';
  const v = Number(s);
  const m = Math.floor(v / 60);
  return `${m}:${(v % 60).toFixed(3).padStart(6, '0')}`;
}

export function fmtSigned(v, digits = 3, unit = ' s') {
  if (v == null || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  const sign = n > 0 ? '+' : n < 0 ? '−' : '';
  return `${sign}${Math.abs(n).toFixed(digits)}${unit}`;
}

export function fmtDate(iso, lang) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(lang === 'es' ? 'es-ES' : 'en-GB', {
    year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

export const normKey = (s) => String(s ?? '').toLowerCase().trim().replace(/\s+/g, ' ');

/** Misma regla que el backend: solo hay desajuste si ambos datos existen y difieren. */
export function isCompatible(a, b) {
  const diff = (x, y) => normKey(x) && normKey(y) && normKey(x) !== normKey(y);
  return !diff(a.venue, b.venue) && !diff(a.vehicle, b.vehicle);
}
