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
def optimal_lap_endpoint(
    request: Request,
    session_file: Optional[UploadFile] = File(None, description="CSV con la sesión completa (o usa file_id)"),
    file_id: Optional[str] = Form(None, description="id devuelto por POST /api/files"),
    lang_form: Optional[str] = Form(None, alias="lang"),
    lang_query: Optional[str] = Query(None, alias="lang"),
    microsector_m: float = Form(25.0, description="Longitud del microsector (m)"),
    speed_tol_kmh: float = Form(3.0, description="Tolerancia de velocidad para cambiar de vuelta"),
):
    """Devuelve la vuelta óptima teórica (suma de mínimos) y realista (con continuidad)."""
    from src.io.loaders import DataLoaderException
    from src.analytics.optimal_lap import calcular_vuelta_optima_desde_df
    from src.api.files import resolve_input

    lang = _pick_lang(request, lang_form or lang_query)
    tmp_dir = tempfile.mkdtemp(prefix="motorsport_optlap_")
    try:
        inp = resolve_input(session_file, file_id, lang, into_dir=tmp_dir)
        path = inp.path
        df = inp.filtered()  # parsed + filtered once per file (cache); private copy
        synthetic = bool(df.attrs.get("distance_synthetic", False))
        from src.analytics import corner_service
        from src.io.loaders import read_motec_metadata
        try:
            venue = read_motec_metadata(path).get("venue")
        except Exception as exc:  # metadata is best-effort
            logger.warning("optimal-lap: metadata: %s", exc)
            venue = None

        def _corner_map(dfs, df_laps):  # unified corner map of the session (cached; None in legacy mode)
            try:
                return corner_service.session_corner_map(dfs, venue, inp.sha, df_laps)
            except Exception as exc:  # el mapa nunca debe romper la vuelta óptima
                logger.warning("optimal-lap: corner map: %s", exc)
                return None

        result = calcular_vuelta_optima_desde_df(
            df, microsector_m=microsector_m, speed_tol_kmh=speed_tol_kmh,
            lang=lang, distance_synthetic=synthetic, corner_map=_corner_map,
        )
        try:  # circuito conocido + nombres de curva (aditivo; nunca rompe el análisis)
            from src.analytics.circuits import enrich_optimal_lap
            enrich_optimal_lap(result, venue)
        except Exception as exc:
            logger.warning("optimal-lap: circuits: %s", exc)
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
