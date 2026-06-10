"""
Backend API — Motorsport Analytics Pipeline.

Aplicación FastAPI que expone el pipeline de análisis de telemetría como una API REST.

Endpoints:
    POST /api/compare-laps  → Recibe dos CSVs, devuelve análisis completo en JSON
    GET  /api/health         → Health check

Uso:
    uvicorn main:app --reload --port 8000
"""

import os
import sys
import json
import tempfile
import logging

# Configurar el directorio temporal en el disco E (el disco C del usuario tiene 0 bytes libres)
project_tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
os.makedirs(project_tmp, exist_ok=True)
tempfile.tempdir = project_tmp

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
)
logger = logging.getLogger("motorsport-api")

# Importar los módulos del pipeline
from src.io.loaders import load_telemetry_data, read_motec_metadata, DataLoaderException
from src.io.exporters import export_report_text
from src.processing.alignment import align_pair
from src.processing.filters import apply_standard_filters
from src.telemetry.lap_comparator import compare_laps
from src.telemetry.session_analyzer import analyze_session

# ─────────────────────────────────────────────────
# Inicializar la aplicación FastAPI
# ─────────────────────────────────────────────────

app = FastAPI(
    title="Motorsport Analytics API",
    description="API para comparar vueltas de telemetría de Assetto Corsa (ACTI)",
    version="1.0.0",
)

# Configurar CORS para permitir peticiones del frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # React dev server (alternativo)
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "motorsport-analytics-api"}


@app.post("/api/compare-laps")
async def compare_laps_endpoint(
    lap_a: UploadFile = File(..., description="CSV de la vuelta de referencia (Piloto A)"),
    lap_b: UploadFile = File(..., description="CSV de la vuelta a comparar (Piloto B)"),
):
    """
    Compara dos vueltas de telemetría y devuelve un análisis completo.
    
    Recibe dos archivos CSV exportados de ACTI. El pipeline:
    1. Carga y valida ambos CSVs
    2. Aplica filtros de señal
    3. Alinea ambas vueltas por distancia (interpolación cúbica)
    4. Detecta eventos clave (frenado, apex, aceleración)
    5. Compara las vueltas curva por curva
    6. Genera un reporte con el análisis
    
    Returns:
        JSON con el resultado completo de la comparación.
    """
    logger.info("=" * 60)
    logger.info(f"Solicitud recibida: comparar '{lap_a.filename}' vs '{lap_b.filename}'")
    logger.info("=" * 60)
    
    tmp_dir = None
    try:
        # 1. Guardar archivos temporalmente
        tmp_dir = tempfile.mkdtemp(prefix="motorsport_")
        
        path_a = os.path.join(tmp_dir, "lap_a.csv")
        path_b = os.path.join(tmp_dir, "lap_b.csv")
        
        content_a = await lap_a.read()
        content_b = await lap_b.read()
        
        with open(path_a, "wb") as f:
            f.write(content_a)
        with open(path_b, "wb") as f:
            f.write(content_b)
        
        # 2. Cargar los datos
        logger.info("Paso 1/4: Cargando datos...")
        df_a = load_telemetry_data(path_a)
        df_b = load_telemetry_data(path_b)
        
        # 3. Aplicar filtros
        logger.info("Paso 2/4: Aplicando filtros...")
        df_a = apply_standard_filters(df_a)
        df_b = apply_standard_filters(df_b)
        
        # 4. Alinear por distancia
        logger.info("Paso 3/4: Alineando por distancia...")
        df_a_aligned, df_b_aligned = align_pair(df_a, df_b, distance_step=1.0)
        
        # 5. Comparar vueltas
        logger.info("Paso 4/4: Comparando vueltas...")
        result = compare_laps(df_a_aligned, df_b_aligned)
        
        # 6. Agregar reporte en texto
        result["text_report"] = export_report_text(result)
        
        # 7. Metadata base
        meta_a = read_motec_metadata(path_a)
        meta_b = read_motec_metadata(path_b)

        # Determinar etiquetas inteligentes
        driver_a = meta_a.get("driver") or "Piloto A"
        driver_b = meta_b.get("driver") or "Piloto B"
        vehicle_a = meta_a.get("vehicle") or "?"
        vehicle_b = meta_b.get("vehicle") or "?"
        venue = meta_a.get("venue") or meta_b.get("venue")

        same_driver  = driver_a.strip().lower() == driver_b.strip().lower()
        same_vehicle = vehicle_a.strip().lower() == vehicle_b.strip().lower()

        # Si mismo piloto, distinguir por carro; si mismo carro, distinguir por piloto
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
            # Identity
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
        
        # Extraer clima de la primera fila válida
        if "AirTemp" in df_a.columns and not df_a["AirTemp"].isna().all():
            result["metadata"]["air_temp"] = float(df_a["AirTemp"].dropna().iloc[0])
        if "RoadTemp" in df_a.columns and not df_a["RoadTemp"].isna().all():
            result["metadata"]["road_temp"] = float(df_a["RoadTemp"].dropna().iloc[0])

        # Extraer Track Map de df_a_aligned (diezmado para optimizar transferencia JSON)
        # AC y ACC usan X, Z para el plano del suelo y Y para la altitud, pero buscamos Y o Z como el 2do eje
        coord_x_col = "CarCoordX" if "CarCoordX" in df_a_aligned.columns else None
        coord_y_col = "CarCoordZ" if "CarCoordZ" in df_a_aligned.columns else ("CarCoordY" if "CarCoordY" in df_a_aligned.columns else None)
        
        if coord_x_col and coord_y_col:
            # Tomar 1 punto por cada 10 metros aprox o por índice
            step = max(1, len(df_a_aligned) // 500) # Máximo 500 puntos para el render
            x_coords = df_a_aligned[coord_x_col].iloc[::step].fillna(0).tolist()
            y_coords = df_a_aligned[coord_y_col].iloc[::step].fillna(0).tolist()
            result["track_map"] = [{"x": x, "y": y} for x, y in zip(x_coords, y_coords)]
        
        logger.info("✓ Comparación completada exitosamente")
        
        return JSONResponse(content=result)
        
    except DataLoaderException as e:
        logger.error(f"Error de datos: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error interno: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        # Limpiar archivos temporales
        if tmp_dir and os.path.exists(tmp_dir):
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

@app.post("/api/analyze-session")
async def analyze_session_endpoint(
    session_file: UploadFile = File(..., description="CSV con la sesión completa"),
):
    """
    Analiza un CSV de telemetría de sesión completa y extrae las vueltas.
    """
    logger.info("=" * 60)
    logger.info(f"Solicitud recibida: analizar sesión '{session_file.filename}'")
    logger.info("=" * 60)
    
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="motorsport_session_")
        path = os.path.join(tmp_dir, "session.csv")
        
        content = await session_file.read()
        with open(path, "wb") as f:
            f.write(content)
        
        logger.info("Paso 1/2: Cargando sesión completa...")
        # A veces el primer registro no es la línea de cabecera correcta si hay muchos metadatos, 
        # load_telemetry_data ya lo maneja gracias a nuestro fix anterior
        df = load_telemetry_data(path)
        
        logger.info("Paso 2/2: Analizando vueltas...")
        result = analyze_session(df)
        
        return JSONResponse(content=result)
        
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

# ─────────────────────────────────────────────────
# Punto de entrada para ejecución directa
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("Iniciando servidor de Motorsport Analytics API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
