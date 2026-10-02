"""Assetto Corsa setup endpoints (see src/analytics/ac_setups.py)."""

from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile

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
async def detect_session_metadata(header: UploadFile = File(...)):
    """Vehicle / venue / driver from the first bytes of the telemetry CSV."""
    raw = await _read_upload(header, _HEADER_MAX)
    return ac.parse_motec_header(raw)


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
