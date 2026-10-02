// Supported telemetry file formats. Native binary formats are EXPERIMENTAL:
// they have been validated with a small set of real files only.
export const TELEMETRY_EXTENSIONS = ['.csv', '.ibt', '.ld'];
export const ACCEPT_ATTR = TELEMETRY_EXTENSIONS.join(',');
export const MAX_FILE_MB = 500;

const FORMATS = {
  csv: { id: 'csv', label: 'CSV', experimental: false },
  ibt: { id: 'ibt', label: 'iRacing .ibt', experimental: true },
  ld: { id: 'ld', label: 'MoTeC .ld', experimental: true },
};

export function detectFormat(name) {
  const lower = String(name || '').toLowerCase();
  const ext = TELEMETRY_EXTENSIONS.find((e) => lower.endsWith(e));
  return ext ? FORMATS[ext.slice(1)] : null;
}

export const isSupportedFile = (file) => detectFormat(file?.name) !== null;
