// Assetto Corsa setup integration — HTTP calls (see src/api/setups.py).
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api');
const client = axios.create({ baseURL: API_URL, timeout: 30000 });

function fail(error) {
  const detail = error.response?.data?.detail;
  const msg = typeof detail === 'string' ? detail : error.message || 'Request failed';
  return new Error(msg, { cause: error });
}

const HEADER_BYTES = 32 * 1024;
const metaCache = new Map();

/** Reads vehicle / venue from the first bytes of the CSV (never uploads the whole file). */
export async function detectSessionMeta(file) {
  const key = `${file.name}:${file.size}:${file.lastModified}`;
  if (metaCache.has(key)) return metaCache.get(key);
  const form = new FormData();
  form.append('header', file.slice(0, HEADER_BYTES), 'header.csv');
  try {
    const { data } = await client.post('/setups/detect', form);
    metaCache.set(key, data);
    return data;
  } catch (e) {
    throw fail(e);
  }
}

export async function fetchSetupCandidates(vehicle, venue, lang) {
  try {
    const { data } = await client.get('/setups/candidates', { params: { vehicle, venue, lang } });
    return data;
  } catch (e) {
    throw fail(e);
  }
}

export async function fetchSetupById(vehicle, venue, setupId, lang) {
  try {
    const { data } = await client.get('/setups/file', { params: { vehicle, venue, setup_id: setupId, lang } });
    return data;
  } catch (e) {
    throw fail(e);
  }
}

export async function uploadSetup(file, vehicle, lang) {
  const form = new FormData();
  form.append('file', file);
  try {
    const { data } = await client.post('/setups/parse', form, { params: { vehicle, lang } });
    return data;
  } catch (e) {
    throw fail(e);
  }
}

export async function annotateRecommendations(setup, recommendations, lang) {
  try {
    const { data } = await client.post('/setups/annotate', { setup, recommendations }, { params: { lang } });
    return data;
  } catch (e) {
    throw fail(e);
  }
}
