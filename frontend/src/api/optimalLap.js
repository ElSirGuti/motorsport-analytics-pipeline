import axios from 'axios';
import { API_URL, withFile, fileKey } from './files';

const client = axios.create({ baseURL: API_URL, timeout: 600000 });

// Requests are shared per (file, language, microsector size): the app starts the computation as soon
// as the file is uploaded (in parallel with the session / stint analysis) and the panel, which mounts
// later, simply joins the same promise instead of triggering a second computation.
const MAX_ENTRIES = 8;
const shared = new Map();

function rejectOnAbort(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new axios.CanceledError());
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(new axios.CanceledError());
    signal.addEventListener('abort', onAbort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort));
  });
}

function request(sessionFile, lang, microsectorM, signal, onProgress) {
  return withFile(sessionFile, { signal, onProgress }, async (id) => {
    const formData = new FormData();
    if (id) formData.append('file_id', id); else formData.append('session_file', sessionFile);
    formData.append('microsector_m', String(microsectorM));
    const response = await client.post('/optimal-lap', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { lang },
      signal,
    });
    return response.data;
  });
}

/**
 * Optimal lap by microsectors for a full session CSV.
 * The underlying request is shared by every caller of the same file/lang/size. `signal` only cancels the
 * caller's own wait (a React effect cleanup must not kill a request another consumer joined);
 * `requestSignal` aborts the request itself (used by the app when the file changes).
 * Pass `fresh: true` to force a new computation (retry button).
 */
export const analyzeOptimalLap = (sessionFile, lang = 'en',
  { microsectorM = 25, signal, requestSignal, fresh = false, onProgress } = {}) => {
  const key = `${fileKey(sessionFile)}|${lang}|${microsectorM}`;
  let entry = fresh ? null : shared.get(key);
  if (!entry) {
    const promise = request(sessionFile, lang, microsectorM, requestSignal, onProgress);
    entry = { promise };
    shared.set(key, entry);
    // keep only successful results; failures and cancellations must be retried
    promise.catch(() => { if (shared.get(key) === entry) shared.delete(key); });
    while (shared.size > MAX_ENTRIES) shared.delete(shared.keys().next().value);
  }
  return rejectOnAbort(entry.promise, signal).catch((error) => {
    if (axios.isCancel(error)) throw error;
    const detail = error.response?.data?.detail;
    throw new Error(
      typeof detail === 'string' ? detail : (error.message || 'Error'),
      { cause: error },
    );
  });
};

/**
 * Starts the computation without waiting for it (errors are surfaced later by the panel's retry).
 * Resolves to true / false when it finishes OK / fails (never rejects).
 */
export const prefetchOptimalLap = (sessionFile, lang, { signal, onProgress } = {}) => (
  analyzeOptimalLap(sessionFile, lang, { requestSignal: signal, onProgress }).then(() => true, () => false)
);

export const isCancelled = (error) => axios.isCancel(error);
