"""Upload store + in-memory cache of parsed telemetry sessions.

Why: the UI used to send the same CSV to several endpoints and every endpoint parsed it
again (Imola, 57 MB: ~5 s per parse). Now the file is stored once under its SHA-256
(``file_id``) and the parsed and filtered frames are cached in memory.

Design notes
------------
* Disk is the source of truth, memory is a cache. A pod/replica that does not hold a
  frame in memory simply re-reads the file from the upload directory (shared volume) and
  caches it locally. If the file is not on disk either, the API answers 410 and the client
  uploads again.
* The LRU is bounded by bytes (``SESSION_CACHE_MAX_MB``) and entries expire after
  ``SESSION_CACHE_TTL_MIN`` minutes without use.
* Callers receive private deep copies: analysis modules were written assuming they own
  their DataFrame (they assign columns, reset_index, ...). A deep copy costs ~30 ms for a
  60 MB session, versus seconds for a re-parse, and removes any risk of cross-request
  corruption.
* One lock per cache key: N simultaneous requests for the same file parse it once.
* Old uploads are removed after ``UPLOAD_TTL_HOURS`` by a throttled background thread.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("motorsport-api.cache")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _env_num(name: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(os.getenv(name, "") or default))
    except ValueError:
        return default


def upload_dir() -> Path:
    """UPLOAD_DIR > STORAGE_DIR/uploads (when STORAGE_DIR is set) > TEMP_DIR/uploads."""
    explicit = os.getenv("UPLOAD_DIR", "").strip()
    if explicit:
        base = Path(explicit)
    elif os.getenv("STORAGE_DIR", "").strip():
        base = Path(os.environ["STORAGE_DIR"].strip()) / "uploads"
    else:
        base = Path(os.getenv("TEMP_DIR", "") or tempfile.gettempdir()) / "uploads"
    base.mkdir(parents=True, exist_ok=True)
    return base


def valid_file_id(file_id: str) -> bool:
    return bool(file_id) and bool(_HEX64.match(file_id))


# ── Upload store ─────────────────────────────────────────────────────────────
@dataclass
class StoredFile:
    file_id: str
    path: str
    filename: str
    size: int
    created: float


class UploadTooLarge(Exception):
    pass


class UploadStore:
    """Content-addressed upload directory: ``<sha256>.csv`` + ``<sha256>.json`` (name, size).

    The payload is always stored with a ``.csv`` suffix: the loaders sniff the real format
    (CSV / .ibt / .ld) from the signature, exactly like the per-request temp files did.
    """

    CLEAN_EVERY_S = 600.0
    TOUCH_EVERY_S = 300.0

    def __init__(self, directory: Optional[Path] = None):
        self._dir = directory
        self._last_clean = 0.0
        self._clean_lock = threading.Lock()

    @property
    def dir(self) -> Path:
        if self._dir is None:
            self._dir = upload_dir()
        self._dir.mkdir(parents=True, exist_ok=True)       # also if a volume was wiped meanwhile
        return self._dir

    @property
    def ttl_s(self) -> float:
        return _env_num("UPLOAD_TTL_HOURS", 24.0, 0.01) * 3600.0

    def _paths(self, file_id: str) -> tuple[Path, Path]:
        return self.dir / f"{file_id}.csv", self.dir / f"{file_id}.json"

    def save_stream(self, fileobj, filename: str, max_bytes: int) -> StoredFile:
        """Stream ``fileobj`` to disk hashing on the fly. Raises UploadTooLarge."""
        d = self.dir
        h = hashlib.sha256()
        written = 0
        fd, tmp = tempfile.mkstemp(prefix="up_", suffix=".part", dir=str(d))
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = fileobj.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise UploadTooLarge()
                    h.update(chunk)
                    out.write(chunk)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        file_id = h.hexdigest()
        data_path, meta_path = self._paths(file_id)
        if data_path.exists():
            os.remove(tmp)                      # identical content already stored
            os.utime(data_path, None)
        else:
            os.replace(tmp, data_path)          # atomic: readers never see a partial file
        meta = {"filename": os.path.basename(filename or "session.csv"), "size": written, "created": time.time()}
        mtmp = f"{meta_path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(mtmp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        os.replace(mtmp, meta_path)
        self.maybe_clean()
        return StoredFile(file_id, str(data_path), meta["filename"], written, meta["created"])

    def get(self, file_id: str) -> Optional[StoredFile]:
        if not valid_file_id(file_id):
            return None
        data_path, meta_path = self._paths(file_id)
        try:
            st = data_path.stat()
        except OSError:
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            meta = {}
        if time.time() - st.st_mtime > self.TOUCH_EVERY_S:   # keep active sessions alive
            try:
                os.utime(data_path, None)
            except OSError:
                pass
        return StoredFile(file_id, str(data_path), meta.get("filename") or "session.csv",
                          st.st_size, meta.get("created", st.st_mtime))

    def maybe_clean(self, force: bool = False) -> None:
        """Delete uploads unused for longer than the TTL, in a daemon thread (never blocks)."""
        now = time.time()
        if not force and now - self._last_clean < self.CLEAN_EVERY_S:
            return
        if not self._clean_lock.acquire(blocking=False):
            return
        self._last_clean = now

        def _run():
            try:
                self.clean_now()
            finally:
                self._clean_lock.release()

        threading.Thread(target=_run, name="upload-cleaner", daemon=True).start()

    def clean_now(self) -> int:
        ttl = self.ttl_s
        cutoff = time.time() - ttl
        removed = 0
        try:
            entries = list(os.scandir(self.dir))
        except OSError:
            return 0
        for e in entries:
            try:
                if e.is_file() and e.stat().st_mtime < cutoff and e.name.endswith((".csv", ".json", ".part", ".tmp")):
                    os.remove(e.path)
                    removed += 1
            except OSError:
                continue
        if removed:
            logger.info("upload cleanup: %d old file(s) removed", removed)
        return removed


store = UploadStore()


# ── Frame cache ──────────────────────────────────────────────────────────────
def _nbytes(obj: Any) -> int:
    import pandas as pd
    if isinstance(obj, pd.DataFrame):
        return int(obj.memory_usage(deep=False).sum())
    if isinstance(obj, (list, tuple)):
        return sum(_nbytes(o) for o in obj)
    return 0


def _clone(obj: Any):
    import pandas as pd
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    if isinstance(obj, list):
        return [_clone(o) for o in obj]
    return obj


class FrameCache:
    """Byte-bounded LRU with TTL and per-key loading locks. Values: DataFrame or list of them."""

    def __init__(self):
        self._data: "OrderedDict[tuple, tuple[Any, int, float]]" = OrderedDict()
        self._bytes = 0
        self._mu = threading.Lock()
        self._key_locks: dict = {}
        self.hits = 0
        self.misses = 0

    @property
    def max_bytes(self) -> int:
        return int(_env_num("SESSION_CACHE_MAX_MB", 1024, 0) * 1024 * 1024)

    @property
    def ttl_s(self) -> float:
        return _env_num("SESSION_CACHE_TTL_MIN", 60, 0.01) * 60.0

    def _evict_locked(self) -> None:
        now = time.time()
        for k in [k for k, (_, _, t) in self._data.items() if now - t > self.ttl_s]:
            self._bytes -= self._data.pop(k)[1]
        limit = self.max_bytes
        while self._data and self._bytes > limit:
            _, (_, n, _) = self._data.popitem(last=False)
            self._bytes -= n

    def _peek(self, key: tuple):
        with self._mu:
            item = self._data.get(key)
            if item is None:
                return None
            if time.time() - item[2] > self.ttl_s:
                self._bytes -= self._data.pop(key)[1]
                return None
            self._data.move_to_end(key)
            self._data[key] = (item[0], item[1], time.time())
            return item[0]

    def _put(self, key: tuple, value: Any) -> None:
        n = _nbytes(value)
        with self._mu:
            if key in self._data:
                self._bytes -= self._data.pop(key)[1]
            if n > self.max_bytes:
                return                      # larger than the whole budget: do not cache
            self._data[key] = (value, n, time.time())
            self._bytes += n
            self._evict_locked()

    def get_or_load(self, key: tuple, loader: Callable[[], Any], copy: bool = True):
        """Return the cached value (a private copy unless ``copy=False``), loading it once."""
        val = self._peek(key)
        if val is not None:
            self.hits += 1
            return _clone(val) if copy else val
        with self._mu:
            lock = self._key_locks.setdefault(key, threading.Lock())
        try:
            with lock:
                val = self._peek(key)       # another thread may have loaded it meanwhile
                if val is None:
                    self.misses += 1
                    val = loader()
                    self._put(key, val)
                    if copy:
                        # the loader's own object is what we cached; hand out a copy
                        return _clone(val)
                else:
                    self.hits += 1
        finally:
            with self._mu:
                if self._key_locks.get(key) is lock and not lock.locked():
                    self._key_locks.pop(key, None)
        return _clone(val) if copy else val

    def clear(self) -> None:
        with self._mu:
            self._data.clear()
            self._bytes = 0

    def stats(self) -> dict:
        with self._mu:
            return {"entries": len(self._data), "bytes": self._bytes, "hits": self.hits, "misses": self.misses}


cache = FrameCache()


# ── Corner-map cache ─────────────────────────────────────────────────────────
class CornerMapCache:
    """Small LRU (entries + TTL) of unified corner maps (``src/analytics/corner_map.py``).

    Why: the map is built from ALL the flying laps of a session (about 0.4 s for a 21-lap Imola file)
    and ``analyze-session``, ``stint/analyze``, ``optimal-lap``, ``compare-session-laps`` and the
    two-file compare endpoints must show the very same corners. The key is built by
    ``src/analytics/corner_service.py`` from the file SHA-256 (``file_id``) + purpose + venue + lap
    length + options, so a second endpoint (or a second upload of the same file) reuses the first
    build. Maps are small plain dicts; callers get a deep copy. Not byte-bounded: ``CORNER_MAP_CACHE_MAX``
    entries (default 64) and the same TTL as the frame cache. One lock per key: N simultaneous
    requests build it once. ``builds`` counts real builds (tests assert one build per session).
    """

    def __init__(self):
        self._data: "OrderedDict[tuple, tuple[Any, float]]" = OrderedDict()
        self._mu = threading.Lock()
        self._key_locks: dict = {}
        self.hits = 0
        self.builds = 0

    @property
    def max_entries(self) -> int:
        return int(_env_num("CORNER_MAP_CACHE_MAX", 64, 1))

    @property
    def ttl_s(self) -> float:
        return _env_num("SESSION_CACHE_TTL_MIN", 60, 0.01) * 60.0

    def _peek(self, key: tuple):
        with self._mu:
            item = self._data.get(key)
            if item is None:
                return None
            if time.time() - item[1] > self.ttl_s:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            self._data[key] = (item[0], time.time())
            return item[0]

    def _put(self, key: tuple, value: Any) -> None:
        with self._mu:
            self._data[key] = (value, time.time())
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def get_or_build(self, key: tuple, builder: Callable[[], Any]):
        import copy
        val = self._peek(key)
        if val is not None:
            self.hits += 1
            return copy.deepcopy(val)
        with self._mu:
            lock = self._key_locks.setdefault(key, threading.Lock())
        try:
            with lock:
                val = self._peek(key)
                if val is None:
                    self.builds += 1
                    val = builder()
                    if val is not None:
                        self._put(key, val)
                else:
                    self.hits += 1
        finally:
            with self._mu:
                if self._key_locks.get(key) is lock and not lock.locked():
                    self._key_locks.pop(key, None)
        return copy.deepcopy(val)

    def clear(self) -> None:
        with self._mu:
            self._data.clear()

    def stats(self) -> dict:
        with self._mu:
            return {"entries": len(self._data), "hits": self.hits, "builds": self.builds}


corner_map_cache = CornerMapCache()


# ── High level accessors (what the endpoints call) ───────────────────────────
def raw_frame(sha: str, path: str):
    """Parsed telemetry (``load_telemetry_data``)."""
    from src.io.loaders import load_telemetry_data
    return cache.get_or_load((sha, "raw"), lambda: load_telemetry_data(path))


def filtered_frame(sha: str, path: str):
    """Parsed + ``apply_standard_filters``."""
    return cache.get_or_load((sha, "filtered"), lambda: _filtered_uncached(sha, path))


def _load_raw(path: str):
    from src.io.loaders import load_telemetry_data
    return load_telemetry_data(path)


def _filtered_uncached(sha: str, path: str):
    from src.processing.filters import apply_standard_filters
    return apply_standard_filters(cache.get_or_load((sha, "raw"), lambda: _load_raw(path), copy=False), deep=False)


def cleanup_temp_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
