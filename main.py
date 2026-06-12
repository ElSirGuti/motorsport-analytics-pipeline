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

from typing import List
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
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

# Límite de tamaño por archivo: default 100 MB
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024

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
from src.analytics.dynamics import (calcular_limites_dinamicos, _build_gg_points,
                                     detectar_subviraje_sobreviraje, calcular_g_desde_cinematica)
from src.analytics.compression import comprimir_telemetria
from src.analytics.ml_anomaly import detectar_anomalias
from src.analytics.ml_clustering import clasificar_curvas
from src.analytics.ml_laptime import (calcular_tiempo_potencial,
                                       guardar_en_historial, predecir_tiempo_potencial_ml,
                                       n_observaciones_historial,
                                       enriquecer_corners_con_historial)
from src.analytics.stint import (extraer_metricas_por_vuelta, analizar_degradacion_stint,
                                  calcular_estrategia_combustible, simular_tiempos_stint,
                                  segmentar_vueltas_desde_csv)
from src.analytics.thermodynamics import analizar_neumaticos_comparativo
from src.analytics.brake_fade import analizar_eficiencia_frenado
from src.analytics.driver_inputs import analizar_inputs_piloto
from src.analytics.suspension import analizar_suspension
from src.analytics.slip_angle import analizar_slip_angle

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


import math

def _sanitize(obj):
    """Recursively replace NaN/Inf floats with None so the payload is JSON-safe."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


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
        return JSONResponse(content=_sanitize(result))

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

        return JSONResponse(content=_sanitize(result))

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


@app.post("/api/compare-session-laps")
async def compare_session_laps_endpoint(
    session_file: UploadFile = File(..., description="CSV con la sesión completa"),
    lap_a: int = Form(..., description="Número de vuelta A (1-based)"),
    lap_b: int = Form(..., description="Número de vuelta B (1-based)"),
):
    """
    Extrae dos vueltas de un CSV de sesión y las compara con el pipeline estándar.
    Permite comparar cualquier par de vueltas segmentadas automáticamente.
    """
    logger.info("=" * 60)
    logger.info(f"Solicitud: comparar vueltas {lap_a} vs {lap_b} de '{session_file.filename}'")
    logger.info("=" * 60)

    import pandas as pd

    tmp_dir = None
    try:
        content = await _read_upload(session_file)
        tmp_dir = tempfile.mkdtemp(prefix="motorsport_csl_")
        path = os.path.join(tmp_dir, "session.csv")
        Path(path).write_bytes(content)

        logger.info("Paso 1/3: Cargando sesión...")
        df = load_telemetry_data(path)
        df = apply_standard_filters(df)

        logger.info("Paso 2/3: Segmentando vueltas...")
        laps = segmentar_vueltas_desde_csv(df)
        n = len(laps)

        if lap_a < 1 or lap_a > n:
            raise HTTPException(422, f"Vuelta {lap_a} fuera de rango (1–{n})")
        if lap_b < 1 or lap_b > n:
            raise HTTPException(422, f"Vuelta {lap_b} fuera de rango (1–{n})")
        if lap_a == lap_b:
            raise HTTPException(422, "Las dos vueltas deben ser diferentes")

        df_a = laps[lap_a - 1]
        df_b = laps[lap_b - 1]

        if len(df_a) < 50 or len(df_b) < 50:
            raise HTTPException(422, "Alguna vuelta tiene muy pocas muestras para comparar")

        logger.info("Paso 3/3: Comparando V%d (%d pts) vs V%d (%d pts)...",
                    lap_a, len(df_a), lap_b, len(df_b))

        # Basic alignment + comparison
        df_a_aligned, df_b_aligned = align_pair(df_a, df_b, distance_step=1.0)
        result = compare_laps(df_a_aligned, df_b_aligned)
        result["text_report"] = export_report_text(result)

        # Track map from lap A (auto-select horizontal-plane axes)
        coord_ranges = {}
        for col in ["CarCoordX", "CarCoordY", "CarCoordZ"]:
            if col in df_a_aligned.columns:
                v = pd.to_numeric(df_a_aligned[col], errors="coerce").dropna()
                if len(v) > 10:
                    coord_ranges[col] = float(v.max() - v.min())
        if len(coord_ranges) >= 2:
            sorted_axes = sorted(coord_ranges, key=coord_ranges.get, reverse=True)
            x_col, y_col = sorted_axes[0], sorted_axes[1]
            step = max(1, len(df_a_aligned) // 500)
            xs = df_a_aligned[x_col].iloc[::step].fillna(0).tolist()
            ys = df_a_aligned[y_col].iloc[::step].fillna(0).tolist()
            dists = df_a_aligned["Distance"].iloc[::step].fillna(0).tolist()
            result["track_map"] = [
                {"x": float(x), "y": float(y), "distance": float(d)}
                for x, y, d in zip(xs, ys, dists)
            ]

        # Full advanced pipeline (geometry, GG, dynamics, anomaly detection)
        apexes = None
        basic_corners = result.get("corners", [])  # save before advanced pipeline may overwrite
        try:
            logger.info("Paso avanzado 1/5: Geometría y Apexes...")
            df_geo = procesar_geometria_pista_perfecta(df_a)
            apexes = detectar_apexes_perfectos(df_geo)

            logger.info("Paso avanzado 2/5: Alineación avanzada con Delta_Time...")
            canales_extra = [
                "LateralG", "LongitudinalG", "SteerAngle", "Brake", "Throttle",
                # tire thermals
                "TyreTempInnerFL", "TyreTempMiddleFL", "TyreTempOuterFL", "TyreTempCoreFL",
                "TyreTempInnerFR", "TyreTempMiddleFR", "TyreTempOuterFR", "TyreTempCoreFR",
                "TyreTempInnerRL", "TyreTempMiddleRL", "TyreTempOuterRL", "TyreTempCoreRL",
                "TyreTempInnerRR", "TyreTempMiddleRR", "TyreTempOuterRR", "TyreTempCoreRR",
                # suspension
                "SuspTravelFL", "SuspTravelFR", "SuspTravelRL", "SuspTravelRR",
                # brake thermals + yaw
                "BrakeTempFL", "BrakeTempFR", "BrakeTempRL", "BrakeTempRR",
                "YawRate",
            ]
            df_adv = alinear_vueltas_y_calcular_delta(
                df_a, df_b, paso_metros=1.0, canales_extra=canales_extra
            )

            logger.info("Paso avanzado 3/5: GG + Dinámicas...")
            df_adv, g_limit = calcular_limites_dinamicos(df_adv)  # returns (df, float)
            gg_points = _build_gg_points(df_adv)
            eventos = detectar_subviraje_sobreviraje(df_adv, apexes)

            logger.info("Paso avanzado 4/5: Sectores + Insights por curva...")
            df_sectores = resumir_delta_por_sector(df_adv, apexes)
            insights_curvas = analizar_errores_por_curva(df_adv, apexes)

            logger.info("Paso avanzado 5/5: Compresión + Anomalías + Módulos avanzados...")
            df_compressed = comprimir_telemetria(df_adv, asegurar_apexes=apexes)
            anomaly_data = detectar_anomalias(df_adv)

            # ── Nuevos módulos de análisis ────────────────────────────────────
            tyre_data    = analizar_neumaticos_comparativo(df_adv)
            brake_data   = analizar_eficiencia_frenado(df_adv)
            inputs_data  = analizar_inputs_piloto(df_adv)
            susp_data    = analizar_suspension(df_adv)
            slip_data    = analizar_slip_angle(df_adv)

            step_c = 1
            df_curv = df_geo.iloc[::step_c].copy()
            result["curvatura"]      = df_curv[["Distance", "Curvature"]].where(
                df_curv[["Distance", "Curvature"]].notna(), None
            ).to_dict(orient="records")
            result["apexes"]         = apexes.where(apexes.notna(), None).to_dict(orient="records")
            result["sectores"]       = df_sectores.to_dict(orient="records") if not df_sectores.empty else []
            result["corners"]        = insights_curvas   # richer corners override basic ones
            result["gg_diagram"]     = gg_points
            result["g_limit"]        = round(float(g_limit), 3)
            result["dynamic_events"] = eventos
            result["anomaly"]        = anomaly_data
            result["telemetria"]     = df_compressed.to_dict(orient="records")
            result["tyre_analysis"]  = tyre_data
            result["brake_analysis"] = brake_data
            result["driver_inputs"]  = inputs_data
            result["suspension"]     = susp_data
            result["slip_angle"]     = slip_data
            logger.info(
                "✓ Pipeline avanzado completado: %d apexes, %d eventos, "
                "neumáticos=%s, frenado=%s, inputs=%s, suspensión=%s",
                len(apexes), len(eventos),
                tyre_data.get("available"), brake_data.get("available"),
                inputs_data.get("available"), susp_data.get("available"),
            )

        except Exception as exc:
            logger.warning("Pipeline avanzado parcialmente disponible: %s", exc, exc_info=False)
            # Fallback: lightweight dynamic events using basic corners (pre-overwrite snapshot)
            if basic_corners and "LateralG" in df_a_aligned.columns and "SteerAngle" in df_a_aligned.columns:
                _apx = pd.DataFrame([
                    {"Distance": c["ref_apex_distance"], "Speed": c["ref_apex_speed"]}
                    for c in basic_corners
                    if "ref_apex_distance" in c
                ])
                _df = df_a_aligned.copy()
                _df["LateralG_Fast"] = df_a_aligned["LateralG"]
                _df["SteerAngle_Fast"] = df_a_aligned["SteerAngle"]
                try:
                    result["dynamic_events"] = detectar_subviraje_sobreviraje(_df, _apx)
                except Exception:
                    result["dynamic_events"] = []
            else:
                result["dynamic_events"] = []

        result["metadata"] = {
            "driver_a":       f"Vuelta {lap_a}",
            "vehicle_a":      session_file.filename,
            "driver_b":       f"Vuelta {lap_b}",
            "vehicle_b":      session_file.filename,
            "driver_fast":    f"V{lap_a}",
            "driver_slow":    f"V{lap_b}",
            "vehicle_fast":   session_file.filename,
            "vehicle_slow":   session_file.filename,
            "label_a":        f"V{lap_a}",
            "label_b":        f"V{lap_b}",
            "same_driver":    True,
            "same_vehicle":   True,
            "session_file":   session_file.filename,
            "delta_total_s":  result["summary"]["total_time_delta"],
            "apexes_detected": len(apexes) if apexes is not None else 0,
            "lap_a_samples":  len(df_a),
            "lap_b_samples":  len(df_b),
            "aligned_samples": len(df_a_aligned),
        }

        logger.info("✓ Comparación de vueltas de sesión completada")
        return JSONResponse(content=_sanitize(result))

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
        return JSONResponse(content=_sanitize(payload))

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
        if "LateralG_Fast" not in df_aligned.columns or "LongitudinalG_Fast" not in df_aligned.columns:
            logger.info("  Sin sensores de G en CSV — estimando desde cinemática (v²κ / dv·v)...")
            df_aligned = calcular_g_desde_cinematica(df_aligned, df_geo)
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
        curvatura_json  = df_curv[["Distance", "Curvature"]].where(
            df_curv[["Distance", "Curvature"]].notna(), None
        ).to_dict(orient="records")
        apexes_json  = apexes.where(apexes.notna(), None).to_dict(orient="records")
        sectores_json = df_sectores.to_dict(orient="records") if not df_sectores.empty else []

        meta_fast = read_motec_metadata(path_fast)
        meta_slow = read_motec_metadata(path_slow)
        delta_total = float(df_aligned["Delta_Time"].iloc[-1]) if not df_aligned.empty else 0.0
        n_total = len(df_aligned)
        n_comp  = len(df_compressed)

        # ── Fase IA ───────────────────────────────────────────────────────────
        logger.info("Paso 8/8: IA — Isolation Forest · K-Means · Tiempo Potencial...")
        anomaly_data    = detectar_anomalias(df_aligned)
        corner_clusters = clasificar_curvas(df_aligned, insights_curvas)

        meta_dict = {
            "driver_fast":  meta_fast.get("driver") or "Piloto A",
            "driver_slow":  meta_slow.get("driver") or "Piloto B",
            "vehicle_fast": meta_fast.get("vehicle") or "?",
            "vehicle_slow": meta_slow.get("vehicle") or "?",
            "venue":        meta_fast.get("venue") or meta_slow.get("venue"),
        }
        insights_curvas  = enriquecer_corners_con_historial(insights_curvas, meta_dict)
        tiempo_potencial = calcular_tiempo_potencial(sectores_json, insights_curvas, meta_dict)
        xgboost_pred     = predecir_tiempo_potencial_ml(insights_curvas, meta_dict)
        guardar_en_historial(meta_dict, insights_curvas, apexes, df_aligned)
        n_hist = n_observaciones_historial()

        payload = {
            "status": "success",
            "metadata": {
                "lap_fast_filename": lap_fast.filename,
                "lap_slow_filename": lap_slow.filename,
                **meta_dict,
                "samples_fast":       len(df_fast_raw),
                "samples_slow":       len(df_slow_raw),
                "delta_total_s":      round(delta_total, 3),
                "apexes_detected":    len(apexes),
                "resolution_m":       step,
                "compression_ratio":  f"{n_comp}/{n_total} ({(1 - n_comp/max(n_total,1))*100:.0f}%)",
                "history_samples":    n_hist,
            },
            "g_limit":       round(float(g_limit), 3),
            "telemetria":    telemetria_json,
            "curvatura":     curvatura_json,
            "apexes":        apexes_json,
            "sectores":      sectores_json,
            "corners":       insights_curvas,
            "gg_diagram":    gg_points,
            "dynamic_events": eventos_dinamica,
            # ── IA ──
            "anomaly":          anomaly_data,
            "corner_clusters":  corner_clusters,
            "tiempo_potencial": tiempo_potencial,
            "xgboost_pred":     xgboost_pred,
        }

        logger.info(f"✓ Pipeline completo: {len(apexes)} curvas, delta={delta_total:+.3f}s, "
                    f"G_max={g_limit:.2f}, {len(eventos_dinamica)} eventos, "
                    f"{len(anomaly_data.get('zones', []))} zonas anómalas, "
                    f"historial={n_hist} obs")
        return JSONResponse(content=_sanitize(payload))

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


@app.post("/api/stint/analyze")
async def analyze_stint_endpoint(
    laps: List[UploadFile] = File(..., description="CSVs de cada vuelta, o un único CSV de sesión completa"),
):
    """
    Analiza un stint completo de N vueltas.
    Acepta dos modos:
    - Múltiples archivos CSV (uno por vuelta, mínimo 3).
    - Un único CSV de sesión grande con canal 'Session Lap Count' o resets de distancia.
    Detecta degradación, ventana de pit stop y proyecta tiempos con Monte Carlo.
    """
    logger.info("=" * 60)
    logger.info(f"[stint/analyze] {len(laps)} archivo(s) recibido(s)")
    logger.info("=" * 60)

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="motorsport_stint_")
        dfs = []

        if len(laps) == 1:
            # Session CSV mode — auto-segment into individual laps
            content = await _read_upload(laps[0])
            path = os.path.join(tmp_dir, "session.csv")
            Path(path).write_bytes(content)
            df_session = load_telemetry_data(path)
            logger.info(f"Modo sesión única: segmentando '{laps[0].filename}' ({len(df_session)} filas)...")
            try:
                dfs = segmentar_vueltas_desde_csv(df_session)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
        else:
            if len(laps) < 3:
                raise HTTPException(
                    status_code=422,
                    detail="Se requieren mínimo 3 archivos CSV (uno por vuelta) o un único CSV de sesión.",
                )
            for i, lap_file in enumerate(laps):
                content = await _read_upload(lap_file)
                path = os.path.join(tmp_dir, f"lap_{i+1:02d}.csv")
                Path(path).write_bytes(content)
                dfs.append(load_telemetry_data(path))

        if len(dfs) < 3:
            raise HTTPException(
                status_code=422,
                detail=f"Solo se detectaron {len(dfs)} vuelta(s). Se requieren mínimo 3 para el análisis de stint.",
            )

        logger.info(f"Paso 1/4: {len(dfs)} vueltas cargadas. Extrayendo métricas...")
        df_laps = extraer_metricas_por_vuelta(dfs)

        logger.info("Paso 2/4: Analizando degradación...")
        degradacion = analizar_degradacion_stint(df_laps)

        logger.info("Paso 3/4: Calculando estrategia de combustible...")
        combustible = calcular_estrategia_combustible(df_laps)

        logger.info("Paso 4/4: Simulación Monte Carlo...")
        montecarlo = simular_tiempos_stint(df_laps, degradacion)

        laps_json = df_laps.where(df_laps.notna(), None).to_dict(orient="records")

        logger.info(
            f"✓ Stint completado: {len(dfs)} vueltas, "
            f"deg={degradacion.get('tasa_s_per_lap', 0):+.4f}s/lap, "
            f"combustible={'sí' if combustible.get('available') else 'no'}"
        )
        return JSONResponse(content=_sanitize({
            "status":      "success",
            "n_laps":      len(dfs),
            "laps":        laps_json,
            "degradacion": degradacion,
            "combustible": combustible,
            "montecarlo":  montecarlo,
        }))

    except HTTPException:
        raise
    except DataLoaderException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en stint: {e}", exc_info=True)
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
