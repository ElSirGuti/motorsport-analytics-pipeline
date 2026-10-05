// Folder settings (/api/settings): where the Assetto Corsa setups and the game install live.
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api');
const client = axios.create({ baseURL: `${API_URL}/settings`, timeout: 15000 });

function fail(error) {
  const detail = error.response?.data?.detail;
  const msg = typeof detail === 'string' ? detail : error.message || 'Request failed';
  return new Error(msg, { cause: error });
}

export async function getPaths() {
  try {
    return (await client.get('/paths')).data;
  } catch (e) {
    throw fail(e);
  }
}

/** Validates a folder without saving it; resolves with {ok, path, details}. */
export async function checkPath(key, path, lang = 'en') {
  try {
    return (await client.post('/paths/check', { key, path }, { params: { lang } })).data;
  } catch (e) {
    throw fail(e);
  }
}

export async function getCapabilities() {
  try {
    return (await client.get('/capabilities')).data;
  } catch {
    return { folder_picker: false };
  }
}

/** Opens the native folder dialog on the machine running the server; resolves {path|null, cancelled}. */
export async function pickFolder(key, path, lang = 'en') {
  try {
    return (await client.post('/pick-folder', { key, path }, { params: { lang }, timeout: 660000 })).data;
  } catch (e) {
    throw fail(e);
  }
}

/** Saves one folder; an empty value goes back to automatic detection. */
export async function savePath(key, path, lang = 'en') {
  try {
    return (await client.put('/paths', { [key]: path || null }, { params: { lang } })).data;
  } catch (e) {
    throw fail(e);
  }
}
