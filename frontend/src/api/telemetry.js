// Dev: backend directo en :8000. Build de produccion (nginx/Ingress): mismo origen, ruta relativa '/api'.
const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api');

import axios from 'axios';
import { withFile, isCancelled } from './files';

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 600000, // 10 minutes to allow 1GB+ files
});

function extractErrorMessage(error) {
  if (error.response) {
    return error.response.data?.detail || `Error del servidor: ${error.response.status}`;
  }
  if (error.request) {
    return 'No se pudo conectar con el servidor. Verifica que la API esté corriendo.';
  }
  return error.message || 'Error desconocido';
}

export const compareLaps = async (lapA, lapB, lang = 'en') => {
  const formData = new FormData();
  formData.append('lap_a', lapA);
  formData.append('lap_b', lapB);

  try {
    const response = await apiClient.post('/compare-laps', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};

/**
 * Pipeline avanzado: geometría + Time Delta acumulado + sectorización.
 * Llama al endpoint POST /api/telemetry/compare
 */
export const compareAdvanced = async (lapFast, lapSlow, resolutionM = 5, lang = 'en') => {
  const formData = new FormData();
  formData.append('lap_fast', lapFast);
  formData.append('lap_slow', lapSlow);
  formData.append('resolution_m', String(resolutionM));

  try {
    const response = await apiClient.post('/telemetry/compare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};

export const analyzeTelemetry = async (lapFast, lapSlow, resolutionM = 5, lang = 'en') => {
  const formData = new FormData();
  formData.append('lap_fast', lapFast);
  formData.append('lap_slow', lapSlow);
  formData.append('resolution_m', String(resolutionM));

  try {
    const response = await apiClient.post('/telemetry/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error), { cause: error });
  }
};

// Session endpoints send the file once (POST /api/files) and then only its `file_id`; if the upload
// endpoint is unavailable they fall back to sending the file in the request, as before.
const asError = (error) => {
  if (isCancelled(error)) return error;
  return new Error(extractErrorMessage(error), { cause: error });
};

export const analyzeSession = async (sessionFile, lang = 'en', { signal, onProgress } = {}) => {
  try {
    return await withFile(sessionFile, { signal, onProgress }, async (id) => {
      const formData = new FormData();
      if (id) formData.append('file_id', id); else formData.append('session_file', sessionFile);
      const response = await apiClient.post('/analyze-session', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: { lang },
        signal,
      });
      return response.data;
    });
  } catch (error) {
    throw asError(error);
  }
};

export const compareSessionLaps = async (sessionFile, lapA, lapB, lang = 'en', { signal, onProgress } = {}) => {
  try {
    return await withFile(sessionFile, { signal, onProgress }, async (id) => {
      const formData = new FormData();
      if (id) formData.append('file_id', id); else formData.append('session_file', sessionFile);
      formData.append('lap_a', String(lapA));
      formData.append('lap_b', String(lapB));
      const response = await apiClient.post('/compare-session-laps', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: { lang },
        signal,
      });
      return response.data;
    });
  } catch (error) {
    throw asError(error);
  }
};

export const downloadPdfReport = async (compareResult, lang = 'en') => {
  const response = await apiClient.post('/report/pdf-from-json', compareResult, {
    responseType: 'blob',
    headers: { 'Content-Type': 'application/json' },
    timeout: 60000,
    params: { lang },
  });
  return response.data;
};

// Whole-session PDF from the JSON already held by the UI. Returns { blob, filename }
// (filename comes from the server: motorsport_<circuit>_<car>_<date>.pdf).
export const downloadSessionPdfReport = async ({ session, stint, comparison, metadata }, lang = 'en') => {
  const response = await apiClient.post(
    '/report/session-pdf-from-json',
    { session, stint: stint ?? null, comparison: comparison ?? null, metadata: metadata ?? null },
    { responseType: 'blob', headers: { 'Content-Type': 'application/json' }, timeout: 120000, params: { lang } },
  );
  const cd = response.headers?.['content-disposition'] || '';
  const match = /filename="?([^";]+)"?/i.exec(cd);
  return { blob: response.data, filename: match ? match[1] : 'motorsport_report.pdf' };
};

/** Pace + Setup Advisor of each range of laps between setup changes. `splits`: laps where a new setup starts. */
export const analyzeSetupSegments = async (file, splits, lang = 'en', { signal } = {}) => {
  const send = async (id) => {
    const formData = new FormData();
    if (id) formData.append('file_id', id);
    else formData.append('session_file', file);
    formData.append('splits', splits.join(','));
    const response = await apiClient.post('/stint/segments', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, params: { lang }, signal,
    });
    return response.data;
  };
  try {
    return await withFile(file, { signal }, send);
  } catch (error) {
    throw asError(error);
  }
};

export const analyzeStint = async (lapFiles, lang = 'en', { signal, onProgress } = {}) => {
  const send = async (id) => {
    const formData = new FormData();
    if (id) formData.append('file_id', id);
    else lapFiles.forEach(f => formData.append('laps', f));
    const response = await apiClient.post('/stint/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
      signal,
    });
    return response.data;
  };
  try {
    // One session CSV -> upload once and reference it; several per-lap CSVs -> classic multipart.
    if (lapFiles.length === 1) return await withFile(lapFiles[0], { signal, onProgress }, send);
    return await send(null);
  } catch (error) {
    throw asError(error);
  }
};
