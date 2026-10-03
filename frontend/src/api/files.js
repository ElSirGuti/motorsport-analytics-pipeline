// Upload a telemetry file ONCE (POST /api/files) and reuse its `file_id` in every analysis call.
//
// Backend contract (src/api/files.py):
//   POST /api/files (multipart `file`)  -> { file_id, filename, size_bytes, format, venue, vehicle, driver }
//   analysis endpoints accept `file_id` instead of the file; 410 = the server no longer has it
//   (expired / another replica without a shared volume) -> upload again and retry once.
// If /api/files itself fails (old backend, proxy limit...) `ensureFileId` resolves to null and the
// callers fall back to the classic "send the file in every request" flow.
import axios from 'axios';

// Same resolution as telemetry.js: dev -> :8000, production build -> same origin '/api'.
export const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api');

const client = axios.create({ baseURL: API_URL, timeout: 600000 });

// File -> { promise, listeners }  (one in-flight/finished upload per File object)
const uploads = new WeakMap();

export const isCancelled = (error) => axios.isCancel(error);
export const isGone = (error) => error?.response?.status === 410;

/** Stable identity of a File across re-selections (same name, size and mtime). */
export const fileKey = (file) => `${file.name}:${file.size}:${file.lastModified}`;

function upload(file, signal) {
  const form = new FormData();
  form.append('file', file);
  const entry = { listeners: new Set(), last: 0 };
  entry.promise = client.post('/files', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal,
    maxBodyLength: Infinity,
    onUploadProgress: (e) => {
      const pct = e.total ? Math.min(1, e.loaded / e.total) : 0;
      entry.last = pct;
      entry.listeners.forEach((fn) => fn(pct));
    },
  }).then((r) => r.data);
  return entry;
}

/**
 * Resolves to the upload metadata ({ file_id, ... }) or null when the upload endpoint is not
 * usable (callers then use the classic flow). Rejects only on cancellation.
 * Concurrent callers share a single upload; `onProgress(0..1)` is reported to all of them.
 */
export async function ensureFileId(file, { signal, onProgress, force = false, retryFailed = false } = {}) {
  if (!file) return null;
  let entry = uploads.get(file);
  if (!entry || force || (retryFailed && entry.failed)) {
    entry = upload(file, signal);
    uploads.set(file, entry);
    entry.promise.catch((error) => {
      // A cancelled upload is simply forgotten; a failed one is remembered so that the parallel
      // callers do not each retry it (they all fall back to the classic flow).
      if (axios.isCancel(error)) { if (uploads.get(file) === entry) uploads.delete(file); } else entry.failed = true;
    });
  }
  if (onProgress) {
    entry.listeners.add(onProgress);
    onProgress(entry.last);
  }
  try {
    return await entry.promise;
  } catch (error) {
    if (axios.isCancel(error) || signal?.aborted) throw error;
    return null;
  } finally {
    if (onProgress) entry.listeners.delete(onProgress);
  }
}

/** Forget the stored id (after a 410) so the next call uploads again. */
export function forgetFile(file) {
  if (file) uploads.delete(file);
}

/**
 * Runs `send(idOrNull)` with the file's id. `send` must build the request with
 * `file_id` when given an id, or with the file itself when given null (classic flow).
 * A 410 re-uploads the file and retries once.
 */
export async function withFile(file, { signal, onProgress } = {}, send) {
  let meta = await ensureFileId(file, { signal, onProgress });
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await send(meta ? meta.file_id : null);
    } catch (error) {
      if (meta && attempt === 0 && isGone(error)) {
        forgetFile(file);
        meta = await ensureFileId(file, { signal, onProgress, force: true });
        continue;
      }
      throw error;
    }
  }
}
