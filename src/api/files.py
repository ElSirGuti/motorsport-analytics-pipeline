"""POST /api/files: upload a telemetry file once, analyse it many times.

The UI used to send the same 60 MB CSV to ``analyze-session``, ``stint/analyze``,
``optimal-lap``... and each endpoint parsed it again. Now:

    POST /api/files  (multipart ``file``)  ->  {"file_id": "<sha256>", ...basic metadata}

and every analysis endpoint accepts ``file_id`` (form field) instead of the file. The id is the
SHA-256 of the content, so uploading the same file twice is idempotent. Parsed frames are cached
in memory (see ``src/io/session_cache.py``); if a replica does not have them it re-reads the
stored file, and if the file is gone (TTL / other replica without a shared volume) the endpoints
answer 410 and the client uploads again.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.i18n import DEFAULT_LANG, _l, set_language
from src.io import session_cache as sc

logger = logging.getLogger("motorsport-api.files")
router = APIRouter(prefix="/api", tags=["files"])


def _limits() -> tuple[int, int]:
    """(max_bytes, max_mb) read at call time (main.py owns the setting)."""
    try:
        import main  # type: ignore
        return int(main.MAX_UPLOAD_BYTES), int(main.MAX_UPLOAD_MB)
    except Exception:
        try:
            mb = max(1, int(os.getenv("MAX_UPLOAD_MB", "2048")))
        except ValueError:
            mb = 2048
        return mb * 1024 * 1024, mb


def _lang(request: Optional[Request]) -> str:
    if request is None:
        return DEFAULT_LANG
    q = request.query_params.get("lang", "")
    if q in ("es", "en"):
        return q
    for part in request.headers.get("accept-language", "").split(","):
        code = part.split(";")[0].strip().split("-")[0]
        if code in ("es", "en"):
            return code
    return DEFAULT_LANG


# ── Resolving an endpoint's input (file upload OR file_id) ───────────────────
@dataclass
class SessionInput:
    sha: str
    path: str
    filename: str
    tmp_dir: Optional[str] = None      # per-request temp dir to delete (classic upload mode)
    from_id: bool = False

    def close(self) -> None:
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # Cached accessors: private copies, shared parse (see session_cache). Lap segmentation is NOT cached:
    # it costs ~0.1 s on a 60 MB session but would keep another full copy of the data in memory.
    def raw(self):
        return sc.raw_frame(self.sha, self.path)

    def filtered(self):
        return sc.filtered_frame(self.sha, self.path)


def _save_hashed(fileobj, dest: str, max_bytes: int, max_mb: int, lang: str) -> str:
    h = hashlib.sha256()
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = fileobj.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(413, _l(lang, "api_err_upload_too_large", max_mb=max_mb))
                h.update(chunk)
                out.write(chunk)
    except HTTPException:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise
    return h.hexdigest()


def resolve_input(upload: Optional[UploadFile], file_id: Optional[str], lang: str,
                  prefix: str = "motorsport_", into_dir: Optional[str] = None,
                  name: str = "session.csv") -> SessionInput:
    """Return a ``SessionInput`` from either an uploaded file or a stored ``file_id``.

    * ``file_id`` given: 410 (translated) when it is unknown / expired, 422 when malformed.
    * file given: saved to a per-request temp dir like before (call ``close()`` when done);
      its SHA-256 still lets the parse be shared through the frame cache. With ``into_dir`` the
      file is saved there as ``name`` and the caller owns (and removes) the directory.
    """
    file_id = (file_id or "").strip() or None
    if file_id:
        if not sc.valid_file_id(file_id):
            raise HTTPException(422, _l(lang, "files_err_bad_id"))
        stored = sc.store.get(file_id)
        if stored is None:
            raise HTTPException(410, _l(lang, "files_err_gone"))
        return SessionInput(file_id, stored.path, stored.filename, None, True)
    if upload is None:
        raise HTTPException(422, _l(lang, "files_err_missing_input"))
    max_bytes, max_mb = _limits()
    tmp_dir = into_dir or tempfile.mkdtemp(prefix=prefix)
    path = os.path.join(tmp_dir, name)
    try:
        sha = _save_hashed(upload.file, path, max_bytes, max_mb, lang)
    except BaseException:
        if not into_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return SessionInput(sha, path, upload.filename or "session.csv", None if into_dir else tmp_dir, False)


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("/files")
def upload_file(request: Request, file: UploadFile = File(..., description="CSV / .ibt / .ld")):
    """Store the file once and return its ``file_id`` (SHA-256) plus basic metadata."""
    lang = _lang(request)
    set_language(lang)
    max_bytes, max_mb = _limits()
    try:
        stored = sc.store.save_stream(file.file, file.filename or "session.csv", max_bytes)
    except sc.UploadTooLarge:
        raise HTTPException(413, _l(lang, "api_err_upload_too_large", max_mb=max_mb))
    except OSError as exc:
        logger.error("files: cannot store upload: %s", exc, exc_info=True)
        raise HTTPException(500, _l(lang, "files_err_store", err=str(exc)))
    if stored.size == 0:
        os.remove(stored.path)
        raise HTTPException(400, _l(lang, "files_err_empty"))

    fmt, meta = "csv", {}
    try:
        from src.io.loaders import read_motec_metadata
        from src.io.native_common import detect_format
        fmt = detect_format(stored.path)
        meta = {k: v for k, v in read_motec_metadata(stored.path).items() if v}
    except Exception as exc:  # metadata is best-effort
        logger.debug("files: metadata: %s", exc)
    return {
        "file_id": stored.file_id,
        "filename": stored.filename,
        "size_bytes": stored.size,
        "format": fmt,
        "venue": meta.get("venue"),
        "vehicle": meta.get("vehicle"),
        "driver": meta.get("driver"),
        "ttl_hours": sc.store.ttl_s / 3600.0,
    }


@router.get("/files/{file_id}")
def file_status(file_id: str, request: Request):
    """Does the file still exist? 200 with metadata, 410 when the client must upload again."""
    lang = _lang(request)
    stored = sc.store.get(file_id) if sc.valid_file_id(file_id) else None
    if stored is None:
        raise HTTPException(410, _l(lang, "files_err_gone"))
    return {"file_id": stored.file_id, "filename": stored.filename, "size_bytes": stored.size}
