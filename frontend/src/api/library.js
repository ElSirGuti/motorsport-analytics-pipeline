// Cliente HTTP de la biblioteca de sesiones (/api/library).
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api');
const client = axios.create({ baseURL: `${API_URL}/library`, timeout: 60000 });

/** Error con `code`: 'network' (sin respuesta) o 'http'; `message` ya viene traducido por el backend. */
export class LibraryError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = 'LibraryError';
    this.code = code;
    this.status = status;
  }
}

function toError(err) {
  if (err.response) {
    const d = err.response.data?.detail;
    const msg = Array.isArray(d) ? d.map((x) => x.msg).join('; ') : d;
    return new LibraryError(msg || `HTTP ${err.response.status}`, 'http', err.response.status);
  }
  return new LibraryError(err.message || 'Network error', err.request ? 'network' : 'unknown');
}

async function call(fn) {
  try {
    return (await fn()).data;
  } catch (err) {
    throw toError(err);
  }
}

export const saveToLibrary = (body, lang = 'en') =>
  call(() => client.post('', body, { params: { lang }, maxBodyLength: Infinity }));

export const listLibrary = (params = {}, lang = 'en') =>
  call(() => client.get('', { params: { ...params, lang } }));

export const getLibrarySession = (id, lang = 'en') =>
  call(() => client.get(`/${id}`, { params: { lang } }));

export const patchLibrarySession = (id, patch, lang = 'en') =>
  call(() => client.patch(`/${id}`, patch, { params: { lang } }));

export const deleteLibrarySession = (id, lang = 'en') =>
  call(() => client.delete(`/${id}`, { params: { lang } }));

export const libraryFacets = () => call(() => client.get('/facets'));

export const compareLibrarySessions = (a, b, force = false, lang = 'en') =>
  call(() => client.post('/compare', { a, b, force }, { params: { lang } }));

/** Lee circuito/coche/piloto de la cabecera del CSV enviando solo los primeros KB. */
export async function sniffMetadata(file) {
  const form = new FormData();
  form.append('head', file.slice(0, 64 * 1024), 'head.csv');
  return call(() => client.post('/sniff', form));
}

/**
 * Huella rapida del archivo: SHA-256 de (primeros 4 MB + ultimos 4 MB + tamano).
 * Evita cargar CSV de cientos de MB en memoria. Devuelve null si no hay WebCrypto.
 */
export async function fingerprintFile(file) {
  try {
    if (!globalThis.crypto?.subtle) return null;
    const CH = 4 * 1024 * 1024;
    const head = await file.slice(0, CH).arrayBuffer();
    const tail = file.size > CH ? await file.slice(Math.max(CH, file.size - CH)).arrayBuffer() : new ArrayBuffer(0);
    const size = new TextEncoder().encode(`|${file.size}`);
    const buf = new Uint8Array(head.byteLength + tail.byteLength + size.byteLength);
    buf.set(new Uint8Array(head), 0);
    buf.set(new Uint8Array(tail), head.byteLength);
    buf.set(size, head.byteLength + tail.byteLength);
    const digest = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return null;
  }
}

// Punto de extension: otras funciones (vuelta optima, setup, calidad de datos...) pueden
// registrar aqui sus resultados para que se guarden en payload.extras al guardar.
const extras = {};
export const setLibraryExtra = (key, value) => {
  if (value == null) delete extras[key];
  else extras[key] = value;
};
export const getLibraryExtras = () => ({ ...extras });

/** Reconstruye {sessionResult, stintResult} desde un detalle guardado. */
export function restoreResults(detail) {
  const p = detail?.payload || {};
  const stint = p.stint || null;
  const session = p.session || {
    laps: [], fastest_lap: null, track_map: [], total_laps: stint?.n_laps ?? 0,
  };
  const extras = p.extras && typeof p.extras === 'object' ? p.extras : {};
  return { sessionResult: session, stintResult: stint, extras };
}
