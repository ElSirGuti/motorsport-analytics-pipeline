// Human-readable names for simulator ids (e.g. "ks_porsche_cayman_gt4_clubsport" -> "Porsche Cayman GT4 Clubsport").
// Mirrors the backend helper used by the library (src/io/header_meta.py prettify_name) so both views agree.

const KEEP_UPPER = new Set(['gt', 'gt2', 'gt3', 'gt4', 'gte', 'gtd', 'lmp1', 'lmp2', 'tcr', 'bmw', 'amg', 'rs', 'rb', 'mc', 'drs', 'ks', 'f1', 'f3', 'f4', 'cup']);

export function prettyName(id) {
  if (!id || typeof id !== 'string') return id ?? '';
  // Already human-readable (has a space or an uppercase letter): leave untouched.
  if (/\s/.test(id) || /[A-Z]/.test(id)) return id;
  const parts = id.replace(/^ks_/, '').split(/[_-]+/).filter(Boolean);
  return parts
    .map((p) => (KEEP_UPPER.has(p) && p !== 'ks' ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(' ');
}
