"""Assetto Corsa setup endpoints (see src/analytics/ac_setups.py)."""

from typing import Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile

from src.analytics import ac_setups as ac

router = APIRouter(prefix="/api/setups", tags=["setups"])

_HEADER_MAX = 64 * 1024


def _lang(lang: Optional[str]) -> str:
    return lang if lang in ("es", "en") else "en"


async def _read_upload(upload: UploadFile, limit: int) -> bytes:
    raw = await upload.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(status_code=413, detail="file too large")
    return raw


@router.post("/detect")
async def detect_session_metadata(header: Optional[UploadFile] = File(None),
                                  file_id: Optional[str] = Form(None)):
    """Vehicle / venue / driver (+ ``date``, ``session_type``, ``format``) from the first bytes of a
    telemetry file (CSV, .ibt or .ld) or of a stored file_id."""
    from src.io.header_meta import HEADER_SNIFF_BYTES, read_header_bytes
    if file_id:
        from src.api.files import resolve_input
        inp = resolve_input(None, file_id, "en")
        with open(inp.path, "rb") as fh:
            raw = fh.read(HEADER_SNIFF_BYTES)
    elif header is None:
        raise HTTPException(status_code=422, detail="header or file_id is required")
    else:
        raw = await _read_upload(header, HEADER_SNIFF_BYTES)
    meta = read_header_bytes(raw)
    out = {k: meta.get(k) for k in ("driver", "vehicle", "venue")}
    if meta.get("date_iso"):
        out["date"] = meta["date_iso"]
    if meta.get("session_type"):
        out["session_type"] = meta["session_type"]
    if meta.get("format") in ("ibt", "ld"):
        out["format"] = meta["format"]
    return out


@router.get("/candidates")
def candidates(vehicle: Optional[str] = None, venue: Optional[str] = None,
               lang: str = Query("en")):
    try:
        return ac.find_candidates(vehicle, venue, _lang(lang))
    except ac.SetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/file")
def get_setup(vehicle: str, setup_id: str, venue: Optional[str] = None,
              lang: str = Query("en")):
    try:
        return ac.read_setup_by_id(vehicle, venue, setup_id, _lang(lang))
    except ac.SetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/parse")
async def parse_setup_upload(file: UploadFile = File(...), vehicle: Optional[str] = None,
                             lang: str = Query("en")):
    raw = await _read_upload(file, ac.MAX_SETUP_BYTES)
    try:
        return ac.parse_upload(file.filename or "setup.ini", raw, vehicle, _lang(lang))
    except ac.SetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/annotate")
def annotate(payload: dict = Body(...), lang: str = Query("en")):
    setup = payload.get("setup")
    recs = payload.get("recommendations")
    if not isinstance(setup, dict) or not isinstance(recs, list):
        raise HTTPException(status_code=400, detail="setup and recommendations are required")
    if len(recs) > 500:
        raise HTTPException(status_code=413, detail="too many recommendations")
    try:
        return ac.annotate_recommendations(setup, recs, _lang(lang))
    except ac.SetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
