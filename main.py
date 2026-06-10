"""
Backend API — Motorsport Analytics Pipeline.

Aplicación FastAPI que expone el pipeline de análisis de telemetría como una API REST.

Endpoints:
    POST /api/compare-laps    → Recibe dos CSVs, devuelve análisis completo en JSON
    POST /api/analyze-session → Analiza una sesión completa con múltiples vueltas
    GET  /api/health          → Health check
"""

import os
import tempfile
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Configuración desde entorno ──────────────────────────────────────────────
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
).split(",") if o.strip()]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Directorio temporal: preferir variable de entorno, luego carpeta /tmp del proyecto
_project_tmp = os.getenv("TEMP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp"))
os.makedirs(_project_tmp, exist_ok=True)
tempfile.tempdir = _project_tmp

# Límite de tamaño por archivo: default 50 MB
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
)
logger = logging.getLogger("motorsport-api")

# ── Módulos del pipeline ──────────────────────────────────────────────────────
from src.io.loaders import load_telemetry_data, read_motec_metadata, DataLoaderException
from src.io.exporters import export_report_text
from src.processing.alignment import align_pair
from src.processing.filters import apply_standard_filters
from src.telemetry.lap_comparator import compare_laps
from src.telemetry.session_analyzer import analyze_session

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Motorsport Analytics API",
    description="API para comparar vueltas de telemetría de Assetto Corsa (ACTI/MoTeC)",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _read_upload(upload: UploadFile) -> bytes:
    """Lee un UploadFile y valida el límite de tamaño."""
    content = await upload.read()
    if len(content) > MAX_UPLOAD_BYTES:
        max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"El archivo '{upload.filename}' supera el límite de {max_mb} MB.",
        )
    return content


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "motorsport-analytics-api", "version": "1.1.0"}


@app.post("/api/compare-laps")
async def compare_laps_endpoint(
    lap_a: UploadFile = File(..., description="CSV de la vuelta de referencia"),
    lap_b: UploadFile = File(..., description="CSV de la vuelta a comparar"),
):
    """
    Compara dos vueltas de telemetría y devuelve un análisis completo.

    Pipeline:
    1. Carga y valida ambos CSVs
    2. Aplica filtros de señal
    3. Alinea por distancia (interpolación cúbica)
    4. Detecta eventos clave (frenado, apex, aceleración)
    5. Compara curva por curva
    6. Genera reporte de texto formato ingeniero
    """
    logger.info("=" * 60)
    logger.info(f"Solicitud: comparar '{lap_a.filename}' vs '{lap_b.filename}'")
    logger.info("=" * 60)

    tmp_dir = None
    try:
        content_a = await _read_upload(lap_a)
        content_b = await _read_upload(lap_b)

        tmp_dir = tempfile.mkdtemp(prefix="motorsport_")
        path_a = os.path.join(tmp_dir, "lap_a.csv")
        path_b = os.path.join(tmp_dir, "lap_b.csv")

        Path(path_a).write_bytes(content_a)
        Path(path_b).write_bytes(content_b)

        logger.info("Paso 1/4: Cargando datos...")
        df_a = load_telemetry_data(path_a)
        df_b = load_telemetry_data(path_b)

        logger.info("Paso 2/4: Aplicando filtros...")
        df_a = apply_standard_filters(df_a)
        df_b = apply_standard_filters(df_b)

        logger.info("Paso 3/4: Alineando por distancia...")
        df_a_aligned, df_b_aligned = align_pair(df_a, df_b, distance_step=1.0)

        logger.info("Paso 4/4: Comparando vueltas...")
        result = compare_laps(df_a_aligned, df_b_aligned)
        result["text_report"] = export_report_text(result)

        # Metadata
        meta_a = read_motec_metadata(path_a)
        meta_b = read_motec_metadata(path_b)

        driver_a = meta_a.get("driver") or "Piloto A"
        driver_b = meta_b.get("driver") or "Piloto B"
        vehicle_a = meta_a.get("vehicle") or "?"
        vehicle_b = meta_b.get("vehicle") or "?"
        venue = meta_a.get("venue") or meta_b.get("venue")

        same_driver  = driver_a.strip().lower() == driver_b.strip().lower()
        same_vehicle = vehicle_a.strip().lower() == vehicle_b.strip().lower()

        if same_driver and not same_vehicle:
            label_a = f"{driver_a} ({vehicle_a})"
            label_b = f"{driver_b} ({vehicle_b})"
        elif not same_driver:
            label_a = driver_a
            label_b = driver_b
        else:
            label_a = "Vuelta A (Ref)"
            label_b = "Vuelta B"

        result["metadata"] = {
            "lap_a_filename": lap_a.filename,
            "lap_b_filename": lap_b.filename,
            "lap_a_samples": len(df_a),
            "lap_b_samples": len(df_b),
            "aligned_samples": len(df_a_aligned),
            "driver_a": driver_a,
            "driver_b": driver_b,
            "vehicle_a": vehicle_a,
            "vehicle_b": vehicle_b,
            "venue": venue,
            "label_a": label_a,
            "label_b": label_b,
            "same_driver": same_driver,
            "same_vehicle": same_vehicle,
        }

        if "AirTemp" in df_a.columns and not df_a["AirTemp"].isna().all():
            result["metadata"]["air_temp"] = float(df_a["AirTemp"].dropna().iloc[0])
        if "RoadTemp" in df_a.columns and not df_a["RoadTemp"].isna().all():
            result["metadata"]["road_temp"] = float(df_a["RoadTemp"].dropna().iloc[0])

        # Track map (máximo 500 puntos para optimizar transferencia JSON)
        coord_x_col = "CarCoordX" if "CarCoordX" in df_a_aligned.columns else None
        coord_y_col = (
            "CarCoordZ" if "CarCoordZ" in df_a_aligned.columns
            else "CarCoordY" if "CarCoordY" in df_a_aligned.columns
            else None
        )
        if coord_x_col and coord_y_col:
            step = max(1, len(df_a_aligned) // 500)
            x_coords = df_a_aligned[coord_x_col].iloc[::step].fillna(0).tolist()
            y_coords = df_a_aligned[coord_y_col].iloc[::step].fillna(0).tolist()
            result["track_map"] = [{"x": x, "y": y} for x, y in zip(x_coords, y_coords)]

        logger.info("✓ Comparación completada exitosamente")
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except DataLoaderException as e:
        logger.error(f"Error de datos: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error interno: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/analyze-session")
async def analyze_session_endpoint(
    session_file: UploadFile = File(..., description="CSV con la sesión completa"),
):
    """Analiza un CSV de telemetría de sesión completa y extrae las vueltas."""
    logger.info("=" * 60)
    logger.info(f"Solicitud: analizar sesión '{session_file.filename}'")
    logger.info("=" * 60)

    tmp_dir = None
    try:
        content = await _read_upload(session_file)

        tmp_dir = tempfile.mkdtemp(prefix="motorsport_session_")
        path = os.path.join(tmp_dir, "session.csv")
        Path(path).write_bytes(content)

        logger.info("Paso 1/2: Cargando sesión completa...")
        df = load_telemetry_data(path)

        logger.info("Paso 2/2: Analizando vueltas...")
        result = analyze_session(df)

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except DataLoaderException as e:
        logger.error(f"Error de datos: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error interno: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    logger.info(f"Iniciando servidor en {host}:{port} (reload={reload})")
    uvicorn.run("main:app", host=host, port=port, reload=reload, log_level=LOG_LEVEL.lower())
