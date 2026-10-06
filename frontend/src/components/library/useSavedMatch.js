import { useEffect, useState } from 'react';
import { ensureFileId } from '../../api/files';
import { fingerprintFile, lookupLibrary } from '../../api/library';

/**
 * Library sessions that come from the very same file (same SHA-256). It uploads the file once, which the
 * analysis then reuses, and asks the library; null while there is nothing to report.
 */
export function useSavedMatch(file, enabled = true) {
  const [match, setMatch] = useState({ file: null, items: [] });
  useEffect(() => {
    if (!file || !enabled) return undefined;
    let alive = true;
    (async () => {
      try {
        const meta = await ensureFileId(file, { retryFailed: true });
        if (!meta?.file_id) return;
        // saved sessions carry the quick fingerprint of the file (older ones) or its full SHA-256 (the file_id)
        const data = await lookupLibrary(meta.file_id, await fingerprintFile(file));
        if (alive) setMatch({ file, items: data.items || [] });
      } catch {
        // no upload endpoint or library: simply nothing to tell
      }
    })();
    return () => { alive = false; };
  }, [file, enabled]);
  return file && match.file === file ? match.items : [];
}
