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

const LABEL_KEYS = {
  'section-overview': 'secOverview',
  'section-stint': 'secStint',
  'section-setup': 'secSetup',
  'section-core-lap': 'secCoreLap',
  'section-dynamics': 'secDynamics',
  'section-inputs': 'secInputs',
  'section-strategy': 'secStrategy',
};

// t: the active i18n dictionary (useLanguage().t)
export function sectionLabel(id, t) {
  const key = LABEL_KEYS[id];
  return key ? (t[key] ?? id) : id;
}
