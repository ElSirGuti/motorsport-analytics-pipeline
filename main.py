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

# ── Módulos de análisis avanzado (Geometría + Time Delta) ─────────────────────
from src.analytics.geometry import procesar_geometria_pista_perfecta, detectar_apexes_perfectos
from src.analytics.alignment import alinear_vueltas_y_calcular_delta, resumir_delta_por_sector
from src.analytics.insights import analizar_errores_por_curva
from src.analytics.dynamics import calcular_limites_dinamicos, _build_gg_points, detectar_subviraje_sobreviraje
from src.analytics.compression import comprimir_telemetria

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
            "CarCoordY" if "CarCoordY" in df_a_aligned.columns
            else "CarCoordZ" if "CarCoordZ" in df_a_aligned.columns
            else None
        )
        if coord_x_col and coord_y_col:
            step = max(1, len(df_a_aligned) // 500)
            x_coords = df_a_aligned[coord_x_col].iloc[::step].fillna(0).tolist()
            y_coords = df_a_aligned[coord_y_col].iloc[::step].fillna(0).tolist()
            distances = df_a_aligned["Distance"].iloc[::step].fillna(0).tolist()
            result["track_map"] = [
                {"x": x, "y": y, "distance": d}
                for x, y, d in zip(x_coords, y_coords, distances)
            ]

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



@app.post("/api/telemetry/compare")
async def compare_telemetry_endpoint(
    lap_fast: UploadFile = File(..., description="CSV de la vuelta rápida (base/referencia)"),
    lap_slow: UploadFile = File(..., description="CSV de la vuelta a comparar"),
    resolution_m: int = 5,
):
    """
    Pipeline de análisis avanzado de telemetría.

    1. Carga y limpieza automática de ambas vueltas.
    2. Geometría de la pista: curvatura Savitzky-Golay + detección de Apex.
    3. Alineación espacial metro a metro y cálculo del Time Delta acumulado.
    4. Sectorización del circuito entre Apexes.
    5. Serialización JSON con resolución reducida para el frontend.
    """
    logger.info("=" * 60)
    logger.info(f"[telemetry/compare] '{lap_fast.filename}' vs '{lap_slow.filename}'")
    logger.info("=" * 60)

    tmp_dir = None
    try:
        content_fast = await _read_upload(lap_fast)
        content_slow = await _read_upload(lap_slow)

        tmp_dir = tempfile.mkdtemp(prefix="motorsport_geo_")
        path_fast = os.path.join(tmp_dir, "lap_fast.csv")
        path_slow = os.path.join(tmp_dir, "lap_slow.csv")
        Path(path_fast).write_bytes(content_fast)
        Path(path_slow).write_bytes(content_slow)

        # 1. Carga y limpieza
        logger.info("Paso 1/4: Cargando datos...")
        df_fast_raw = load_telemetry_data(path_fast)
        df_slow_raw = load_telemetry_data(path_slow)

        # 2. Geometría de la pista (usando la vuelta rápida como referencia)
        logger.info("Paso 2/4: Procesando geometría de la pista...")
        df_geo = procesar_geometria_pista_perfecta(df_fast_raw)
        apexes = detectar_apexes_perfectos(df_geo)

        # 3. Alineación y Time Delta
        logger.info("Paso 3/4: Calculando Time Delta acumulado...")
        df_alineado = alinear_vueltas_y_calcular_delta(df_fast_raw, df_slow_raw)

        # 4. Sectorización
        logger.info("Paso 4/4: Sectorización del circuito y extracción de Insights...")
        df_sectores = resumir_delta_por_sector(df_alineado, apexes)
        insights_curvas = analizar_errores_por_curva(df_alineado, apexes)

        # 5. Reducir resolución para la respuesta JSON
        step = max(1, resolution_m)
        df_telem  = df_alineado.iloc[::step].copy()
        df_curv   = df_geo.iloc[::step].copy()

        # Serializar a listas de dicts
        telemetria_json = df_telem.where(df_telem.notna(), None).to_dict(orient="records")
        curvatura_json  = df_curv[["Distance", "Curvature"]].where(
            df_curv[["Distance", "Curvature"]].notna(), None
        ).to_dict(orient="records")
        apexes_json = apexes.where(apexes.notna(), None).to_dict(orient="records")
        sectores_json = df_sectores.to_dict(orient="records") if not df_sectores.empty else []

        # Metadatos de las vueltas
        meta_fast = read_motec_metadata(path_fast)
        meta_slow = read_motec_metadata(path_slow)

        delta_total = float(df_alineado["Delta_Time"].iloc[-1]) if not df_alineado.empty else 0.0

        payload = {
            "metadata": {
                "lap_fast_filename": lap_fast.filename,
                "lap_slow_filename": lap_slow.filename,
                "driver_fast":  meta_fast.get("driver") or "Piloto A",
                "driver_slow":  meta_slow.get("driver") or "Piloto B",
                "vehicle_fast": meta_fast.get("vehicle") or "?",
                "vehicle_slow": meta_slow.get("vehicle") or "?",
                "venue":        meta_fast.get("venue") or meta_slow.get("venue"),
                "samples_fast": len(df_fast_raw),
                "samples_slow": len(df_slow_raw),
                "delta_total_s": round(delta_total, 3),
                "apexes_detected": len(apexes),
                "resolution_m":   step,
            },
            "telemetria":  telemetria_json,
            "curvatura":   curvatura_json,
            "apexes":      apexes_json,
            "sectores":    sectores_json,
            "corners":     insights_curvas,
        }

        logger.info(
            f"✓ Análisis completado: {len(apexes)} curvas, "
            f"delta total = {delta_total:+.3f}s"
        )
        return JSONResponse(content=payload)

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


@app.post("/api/telemetry/analyze")
async def analyze_telemetry_endpoint(
    lap_fast: UploadFile = File(..., description="CSV de la vuelta rápida (referencia)"),
    lap_slow: UploadFile = File(..., description="CSV de la vuelta lenta (a comparar)"),
    resolution_m: int = 5,
):
    """
    Pipeline completo de análisis de telemetría con dinámica vehicular y compresión.

    1. Carga y limpieza de ambas vueltas.
    2. Geometría de pista + detección de Apex.
    3. Alineación espacial + Time Delta + canales G.
    4. Círculo de fricción (G-G) y eficiencia de agarre.
    5. Detección de subviraje y sobreviraje por curva.
    6. Insights técnicos curva por curva.
    7. Compresión inteligente RDP para el frontend.
    """
    logger.info("=" * 60)
    logger.info(f"[telemetry/analyze] '{lap_fast.filename}' vs '{lap_slow.filename}'")
    logger.info("=" * 60)

    tmp_dir = None
    try:
        content_fast = await _read_upload(lap_fast)
        content_slow = await _read_upload(lap_slow)

        tmp_dir = tempfile.mkdtemp(prefix="motorsport_dyn_")
        path_fast = os.path.join(tmp_dir, "lap_fast.csv")
        path_slow = os.path.join(tmp_dir, "lap_slow.csv")
        Path(path_fast).write_bytes(content_fast)
        Path(path_slow).write_bytes(content_slow)

        logger.info("Paso 1/7: Cargando datos...")
        df_fast_raw = load_telemetry_data(path_fast)
        df_slow_raw = load_telemetry_data(path_slow)

        logger.info("Paso 2/7: Procesando geometría de pista y Apexes...")
        df_geo = procesar_geometria_pista_perfecta(df_fast_raw)
        apexes = detectar_apexes_perfectos(df_geo)

        logger.info("Paso 3/7: Alineando vueltas y calculando Time Delta...")
        canales_extra = ["LateralG", "LongitudinalG", "SteerAngle"]
        canales_existentes = [
            c for c in canales_extra
            if c in df_fast_raw.columns and c in df_slow_raw.columns
        ]
        df_aligned = alinear_vueltas_y_calcular_delta(
            df_fast_raw, df_slow_raw,
            canales_extra=canales_existentes if canales_existentes else None,
        )

        logger.info("Paso 4/7: Analizando dinámica vehicular (círculo de fricción)...")
        df_aligned, g_limit = calcular_limites_dinamicos(df_aligned)
        gg_points = _build_gg_points(df_aligned)

        logger.info("Paso 5/7: Detectando eventos de subviraje y sobreviraje...")
        eventos_dinamica = detectar_subviraje_sobreviraje(df_aligned, apexes)

        logger.info("Paso 6/7: Extrayendo insights por curva...")
        df_sectores = resumir_delta_por_sector(df_aligned, apexes)
        insights_curvas = analizar_errores_por_curva(df_aligned, apexes)

        logger.info("Paso 7/7: Comprimiendo payload con RDP...")
        df_compressed = comprimir_telemetria(df_aligned, asegurar_apexes=apexes)
        step = max(1, resolution_m)
        df_curv = df_geo.iloc[::step].copy()

        telemetria_json = df_compressed.where(df_compressed.notna(), None).to_dict(orient="records")
        curvatura_json = df_curv[["Distance", "Curvature"]].where(
            df_curv[["Distance", "Curvature"]].notna(), None
        ).to_dict(orient="records")
        apexes_json = apexes.where(apexes.notna(), None).to_dict(orient="records")
        sectores_json = df_sectores.to_dict(orient="records") if not df_sectores.empty else []

        meta_fast = read_motec_metadata(path_fast)
        meta_slow = read_motec_metadata(path_slow)

        delta_total = float(df_aligned["Delta_Time"].iloc[-1]) if not df_aligned.empty else 0.0
        n_total = len(df_aligned)
        n_comp = len(df_compressed)

        payload = {
            "status": "success",
            "metadata": {
                "lap_fast_filename": lap_fast.filename,
                "lap_slow_filename": lap_slow.filename,
                "driver_fast": meta_fast.get("driver") or "Piloto A",
                "driver_slow": meta_slow.get("driver") or "Piloto B",
                "vehicle_fast": meta_fast.get("vehicle") or "?",
                "vehicle_slow": meta_slow.get("vehicle") or "?",
                "venue": meta_fast.get("venue") or meta_slow.get("venue"),
                "samples_fast": len(df_fast_raw),
                "samples_slow": len(df_slow_raw),
                "delta_total_s": round(delta_total, 3),
                "apexes_detected": len(apexes),
                "resolution_m": step,
                "compression_ratio": f"{n_comp}/{n_total} ({(1 - n_comp/max(n_total,1))*100:.0f}%)",
            },
            "g_limit": round(float(g_limit), 3),
            "telemetria": telemetria_json,
            "curvatura": curvatura_json,
            "apexes": apexes_json,
            "sectores": sectores_json,
            "corners": insights_curvas,
            "gg_diagram": gg_points,
            "dynamic_events": eventos_dinamica,
        }

        logger.info(f"✓ Análisis completo: {len(apexes)} curvas, "
                    f"delta={delta_total:+.3f}s, G_max={g_limit:.2f}, "
                    f"{len(eventos_dinamica)} eventos dinámicos, "
                    f"compresión {n_comp}/{n_total}")
        return JSONResponse(content=payload)

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
