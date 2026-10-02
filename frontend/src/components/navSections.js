// Shared section definitions for the side rail and the section headers.
export const SESSION_SECTIONS = [
  { id: 'section-overview', icon: 'grid' },
  { id: 'section-stint', icon: 'trend' },
  { id: 'section-setup', icon: 'wrench' },
];

export const COMPARE_SECTIONS = [
  { id: 'section-core-lap', icon: 'stopwatch' },
  { id: 'section-dynamics', icon: 'gauge' },
  { id: 'section-inputs', icon: 'steering' },
  { id: 'section-strategy', icon: 'flag' },
];

export const PILOT_HIDDEN = new Set(['section-dynamics', 'section-inputs']);

const LABELS = {
  'section-overview': { en: 'Session overview', es: 'Resumen de sesión' },
  'section-stint': { en: 'Stint analysis', es: 'Análisis de stint' },
  'section-setup': { en: 'Setup & strategy', es: 'Setup y estrategia' },
  'section-core-lap': { en: 'Core lap', es: 'Vuelta base' },
  'section-dynamics': { en: 'Vehicle dynamics', es: 'Dinámica del vehículo' },
  'section-inputs': { en: 'Driver & inputs', es: 'Piloto y entradas' },
  'section-strategy': { en: 'Strategy & setup', es: 'Estrategia y setup' },
};

export function sectionLabel(id, lang) {
  const l = LABELS[id];
  if (!l) return id;
  return lang === 'es' ? l.es : l.en;
}
