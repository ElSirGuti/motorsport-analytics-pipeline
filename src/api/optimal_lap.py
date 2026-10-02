"""POST /api/optimal-lap — vuelta óptima por microsectores de una sesión completa."""

import logging
import math
import os
import shutil
import tempfile
from typing import Optional

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from src.i18n import DEFAULT_LANG, _l

logger = logging.getLogger("motorsport-api.optimal-lap")
router = APIRouter(prefix="/api", tags=["optimal-lap"])

_MAX_UPLOAD_MB = max(1, int(os.getenv("MAX_UPLOAD_MB", "2048") or 2048))


def _sanitize(obj):
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.generic):
        return _sanitize(obj.item())
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _pick_lang(request: Request, lang: Optional[str]) -> str:
    if lang in ("es", "en"):
        return lang
    for part in request.headers.get("accept-language", "").split(","):
        code = part.split(";")[0].strip().split("-")[0]
        if code in ("es", "en"):
            return code
    return DEFAULT_LANG


async def _save(upload: UploadFile, dest: str, lang: str) -> None:
    limit = _MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with open(dest, "wb") as fh:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise HTTPException(413, _l(lang, "api_err_upload_too_large", max_mb=_MAX_UPLOAD_MB))
                fh.write(chunk)
    except HTTPException:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise


@router.post("/optimal-lap")
async def optimal_lap_endpoint(
    request: Request,
    session_file: UploadFile = File(..., description="CSV con la sesión completa"),
    lang_form: Optional[str] = Form(None, alias="lang"),
    lang_query: Optional[str] = Query(None, alias="lang"),
    microsector_m: float = Form(25.0, description="Longitud del microsector (m)"),
    speed_tol_kmh: float = Form(3.0, description="Tolerancia de velocidad para cambiar de vuelta"),
):
    """Devuelve la vuelta óptima teórica (suma de mínimos) y realista (con continuidad)."""
    from src.io.loaders import load_telemetry_data, DataLoaderException
    from src.processing.filters import apply_standard_filters
    from src.analytics.optimal_lap import calcular_vuelta_optima_desde_df

    lang = _pick_lang(request, lang_form or lang_query)
    tmp_dir = tempfile.mkdtemp(prefix="motorsport_optlap_")
    try:
        path = os.path.join(tmp_dir, "session.csv")
        await _save(session_file, path, lang)
        df = load_telemetry_data(path)
        synthetic = bool(df.attrs.get("distance_synthetic", False))
        df = apply_standard_filters(df)
        result = calcular_vuelta_optima_desde_df(
            df, microsector_m=microsector_m, speed_tol_kmh=speed_tol_kmh,
            lang=lang, distance_synthetic=synthetic,
        )
        return JSONResponse(content=_sanitize(result))
    except HTTPException:
        raise
    except DataLoaderException as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("optimal-lap: %s", exc, exc_info=True)
        raise HTTPException(500, _l(lang, "optlap_reason_error", err=str(exc)))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
