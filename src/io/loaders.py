"""
Módulo de ingesta de datos de telemetría.

Lee archivos CSV exportados por ACTI (Assetto Corsa Telemetry Interface),
limpia los nombres de columnas, valida la presencia de canales esenciales
y prepara los datos para el pipeline de procesamiento.

Soporta alias flexibles para nombres de columnas, ya que diferentes versiones
de ACTI o diferentes configuraciones de exportación pueden usar variantes.
"""

import pandas as pd
import numpy as np
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DataLoaderException(Exception):
    """Excepción personalizada para errores en la carga de datos de telemetría."""
    pass


# Mapeo de alias conocidos para los canales esenciales.
# La clave es el nombre canónico que usamos internamente.
# Los valores son posibles nombres que puede tener el canal en el CSV.
COLUMN_ALIASES = {
    "Speed":    ["Speed", "speed", "SPEED", "SpeedKmh", "speed_kmh", "Velocity", "Ground Speed", "Chassis Velocity X"],
    "Brake":    ["Brake", "brake", "BRAKE", "BrakePressure", "brake_pressure", "BrakeInput", "Brake Pos"],
    "Throttle": ["Throttle", "throttle", "THROTTLE", "Gas", "gas", "ThrottleInput", "Accel", "Throttle Pos"],
    "Distance": ["Distance", "distance", "DISTANCE", "Dist", "dist", "LapDistance", "lap_distance"],
    "Gear":     ["Gear", "gear", "GEAR", "GearNumber"],
    "RPM":      ["RPM", "rpm", "Rpm", "EngineRPM", "engine_rpm"],
    "SteerAngle":     ["SteerAngle", "steer_angle", "Steer", "SteeringAngle", "Steering Angle"],
    "LateralG":       ["LateralG", "lateral_g", "LatG", "G_Lat", "AccG_Lateral",
                       "Lateral G", "Lat G", "G Lat", "G Force Lat", "Lateral Acc",
                       "Lat Acc", "AccLateral", "Lateral Accel",
                       "CG Accel Lateral"],
    "LongitudinalG":  ["LongitudinalG", "longitudinal_g", "LonG", "G_Lon", "AccG_Longitudinal",
                       "Longitudinal G", "Lon G", "G Lon", "G Force Lon", "Longitudinal Acc",
                       "Lon Acc", "AccLongitudinal", "Longitudinal Accel", "Long G",
                       "CG Accel Longitudinal"],
    "LapTime":        ["LapTime", "lap_time", "Time", "time", "CurrentLapTime", "Lap Time"],
    # New aliases for weather and coordinates
    "AirTemp":        ["Air Temp", "AirTemp", "air_temp", "AmbientTemp"],
    "RoadTemp":       ["Road Temp", "RoadTemp", "road_temp", "TrackTemp"],
    "CarCoordX":      ["Car Coord X", "car_coord_x", "PosX"],
    "CarCoordY":      ["Car Coord Y", "car_coord_y", "PosY"],  # plano horizontal
    "CarCoordZ":      ["Car Coord Z", "car_coord_z", "PosZ"],  # elevación real
    "SessionLapCount": ["Session Lap Count", "session_lap_count", "Lap"],
    # ── Yaw rate ─────────────────────────────────────────────────
    "YawRate":         ["Chassis Yaw Rate", "Yaw Rate", "YawRate", "yaw_rate",
                        "Yaw Velocity", "YawVelocity"],
    # ── Tire temps — 4 zones × 4 corners ─────────────────────────
    "TyreTempCoreFL":   ["Tire Temp Core FL", "Tyre Temp Core FL", "Tyre Core Temp FL",
                         "Tire Core Temp FL", "TyreCoreFL", "TyreTempCoreFL"],
    "TyreTempCoreFR":   ["Tire Temp Core FR", "Tyre Temp Core FR", "Tyre Core Temp FR",
                         "Tire Core Temp FR", "TyreCoreFR", "TyreTempCoreFR"],
    "TyreTempCoreRL":   ["Tire Temp Core RL", "Tyre Temp Core RL", "Tyre Core Temp RL",
                         "Tire Core Temp RL", "TyreCoreRL", "TyreTempCoreRL"],
    "TyreTempCoreRR":   ["Tire Temp Core RR", "Tyre Temp Core RR", "Tyre Core Temp RR",
                         "Tire Core Temp RR", "TyreCoreRR", "TyreTempCoreRR"],
    "TyreTempInnerFL":  ["Tire Temp Inner FL", "Tyre Temp (I) FL", "Tyre Temp I FL",
                         "TyreTempInnerFL", "Tire Temp I FL"],
    "TyreTempInnerFR":  ["Tire Temp Inner FR", "Tyre Temp (I) FR", "Tyre Temp I FR",
                         "TyreTempInnerFR", "Tire Temp I FR"],
    "TyreTempInnerRL":  ["Tire Temp Inner RL", "Tyre Temp (I) RL", "Tyre Temp I RL",
                         "TyreTempInnerRL", "Tire Temp I RL"],
    "TyreTempInnerRR":  ["Tire Temp Inner RR", "Tyre Temp (I) RR", "Tyre Temp I RR",
                         "TyreTempInnerRR", "Tire Temp I RR"],
    "TyreTempMiddleFL": ["Tire Temp Middle FL", "Tyre Temp (M) FL", "Tyre Temp M FL",
                         "TyreTempMiddleFL", "Tire Temp M FL"],
    "TyreTempMiddleFR": ["Tire Temp Middle FR", "Tyre Temp (M) FR", "Tyre Temp M FR",
                         "TyreTempMiddleFR", "Tire Temp M FR"],
    "TyreTempMiddleRL": ["Tire Temp Middle RL", "Tyre Temp (M) RL", "Tyre Temp M RL",
                         "TyreTempMiddleRL", "Tire Temp M RL"],
    "TyreTempMiddleRR": ["Tire Temp Middle RR", "Tyre Temp (M) RR", "Tyre Temp M RR",
                         "TyreTempMiddleRR", "Tire Temp M RR"],
    "TyreTempOuterFL":  ["Tire Temp Outer FL", "Tyre Temp (O) FL", "Tyre Temp O FL",
                         "TyreTempOuterFL", "Tire Temp O FL"],
    "TyreTempOuterFR":  ["Tire Temp Outer FR", "Tyre Temp (O) FR", "Tyre Temp O FR",
                         "TyreTempOuterFR", "Tire Temp O FR"],
    "TyreTempOuterRL":  ["Tire Temp Outer RL", "Tyre Temp (O) RL", "Tyre Temp O RL",
                         "TyreTempOuterRL", "Tire Temp O RL"],
    "TyreTempOuterRR":  ["Tire Temp Outer RR", "Tyre Temp (O) RR", "Tyre Temp O RR",
                         "TyreTempOuterRR", "Tire Temp O RR"],
    # ── Suspension travel (mm compression) ───────────────────────
    "SuspTravelFL":     ["Suspension Travel FL", "Susp Travel FL", "SuspTravel_FL",
                         "SuspTravelFL", "Front Left Susp Travel"],
    "SuspTravelFR":     ["Suspension Travel FR", "Susp Travel FR", "SuspTravel_FR",
                         "SuspTravelFR", "Front Right Susp Travel"],
    "SuspTravelRL":     ["Suspension Travel RL", "Susp Travel RL", "SuspTravel_RL",
                         "SuspTravelRL", "Rear Left Susp Travel"],
    "SuspTravelRR":     ["Suspension Travel RR", "Susp Travel RR", "SuspTravel_RR",
                         "SuspTravelRR", "Rear Right Susp Travel"],
    # ── Brake temperatures ────────────────────────────────────────
    "BrakeTempFL":      ["Brake Temp FL", "Brake Temperature FL", "BrakeTempFL",
                         "Brake Disc Temp FL"],
    "BrakeTempFR":      ["Brake Temp FR", "Brake Temperature FR", "BrakeTempFR",
                         "Brake Disc Temp FR"],
    "BrakeTempRL":      ["Brake Temp RL", "Brake Temperature RL", "BrakeTempRL",
                         "Brake Disc Temp RL"],
    "BrakeTempRR":      ["Brake Temp RR", "Brake Temperature RR", "BrakeTempRR",
                         "Brake Disc Temp RR"],
}

# Canales que DEBEN existir para que el pipeline funcione
ESSENTIAL_CHANNELS = ["Speed", "Brake", "Throttle"]

# Canales de tiempo a intentar en orden para sintetizar Distance
_TIME_CANDIDATES = [
    "LR Sample Clock", "HR Sample Clock", "MR Sample Clock",
    "Time", "time", "Lap Time",
]


def read_motec_metadata(filepath: str) -> dict:
    """
    Lee los metadatos de cabecera de un archivo CSV de MoTeC (Driver, Vehicle, Venue).
    Estos aparecen en las primeras filas antes del bloque de datos.
    """
    meta = {"driver": None, "vehicle": None, "venue": None}
    keys = {
        "Driver":  "driver",
        "Vehicle": "vehicle",
        "Venue":   "venue",
    }
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(20):          # solo las primeras 20 líneas
                line = f.readline()
                if not line:
                    break
                clean = line.replace('"', '').strip()
                # Las líneas de cabecera tienen la forma:  Key,Value,...
                for raw_key, field in keys.items():
                    if clean.startswith(raw_key + ","):
                        parts = [p.strip() for p in clean.split(",")]
                        if len(parts) >= 2 and parts[1]:
                            meta[field] = parts[1]
    except Exception:
        pass
    return meta


def _synthesize_distance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes a Distance column (metres, cumulative) from Speed × dt when the
    channel is absent in the source CSV.

    Uses the best monotonic time clock available (LR/HR Sample Clock, then Time,
    then Lap Time). Falls back to a fixed 100 Hz interval when no clock is found.
    The synthesized distances are session-continuous (not reset per lap) — for
    per-lap analysis the caller must slice and re-cumsum after lap segmentation.
    """
    time_col = next((c for c in _TIME_CANDIDATES if c in df.columns), None)

    speed_ms = pd.to_numeric(df["Speed"], errors="coerce").fillna(0) / 3.6  # km/h → m/s

    if time_col:
        t = pd.to_numeric(df[time_col], errors="coerce").ffill().bfill()
        dt = t.diff().fillna(0).clip(lower=0, upper=2.0)
        logger.warning(
            "Canal 'Distance' ausente — sintetizado integrando Speed con '%s'. "
            "Precisión suficiente para análisis de stint; no apta para comparación de vueltas.",
            time_col,
        )
    else:
        dt = pd.Series(0.01, index=df.index)  # 100 Hz fallback
        logger.warning(
            "Canal 'Distance' ausente y sin canal de tiempo — asumiendo 100 Hz. "
            "Úsese solo para análisis de stint.",
        )

    df["Distance"] = (speed_ms * dt).cumsum()
    return df


def _resolve_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Intenta mapear columnas del DataFrame a nombres canónicos usando alias.
    
    Si una columna del CSV coincide con un alias conocido, se renombra
    al nombre canónico correspondiente.
    
    Args:
        df: DataFrame con nombres de columnas originales del CSV.
    
    Returns:
        DataFrame con columnas renombradas a nombres canónicos donde sea posible.
    """
    rename_map = {}
    
    for canonical_name, aliases in COLUMN_ALIASES.items():
        # Si el nombre canónico ya existe, no renombrar
        if canonical_name in df.columns:
            continue
        
        # Buscar un alias que coincida
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical_name
                logger.info(f"  Columna '{alias}' → '{canonical_name}' (alias detectado)")
                break
    
    if rename_map:
        df = df.rename(columns=rename_map)
    
    return df


def _detect_separator_and_header(filepath: str) -> tuple[str, int, bool]:
    """
    Detecta el separador (coma o punto y coma), la fila del encabezado y la fila de unidades.
    """
    # Nombres que confirman que una línea es el header de datos
    HEADER_ANCHORS = {"Time", "Distance", "Speed", "Brake", "Throttle",
                      "Ground Speed", "Brake Pos", "Throttle Pos"}
    UNIT_TOKENS = {"s", "m", "km/h", "rpm", "deg", "%", "bar", "km", "C"}
    separators = [",", ";"]

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [f.readline() for _ in range(50)]
    except Exception:
        return ",", 0, False

    for sep in separators:
        for i, line in enumerate(lines):
            clean = line.replace('"', '').strip()
            parts = [p.strip() for p in clean.split(sep)]
            # El header tiene al menos 3 columnas y al menos uno es un nombre conocido
            if len(parts) >= 3 and any(p in HEADER_ANCHORS for p in parts):
                has_units = False
                if i + 1 < len(lines):
                    next_clean = lines[i + 1].replace('"', '').strip()
                    next_parts = [p.strip() for p in next_clean.split(sep)]
                    if any(u in next_parts for u in UNIT_TOKENS):
                        has_units = True
                return sep, i, has_units

    return ",", 0, False


def load_telemetry_data(filepath: str, 
                         separator: Optional[str] = None,
                         skip_rows: Optional[int] = None) -> pd.DataFrame:
    """
    Lee un archivo CSV crudo exportado por ACTI (Assetto Corsa), limpia los
    nombres de las columnas y verifica que existan los canales esenciales.
    Soporta la detección automática del formato de MoTeC (saltando metadatos y unidades).

    Args:
        filepath: Ruta al archivo CSV.
        separator: Separador de columnas. Si es None, se auto-detecta.
        skip_rows: Número de filas a saltar al inicio. Si es None, se auto-detecta.

    Returns:
        DataFrame con los datos de telemetría limpios y listos para procesar.
    
    Raises:
        DataLoaderException: Si el archivo no existe, no es válido o faltan columnas requeridas.
    """
    logger.info(f"Cargando telemetría desde: {filepath}")
    
    if not os.path.exists(filepath):
        raise DataLoaderException(f"No se encontró el archivo: {filepath}")
    
    # Auto-detectar separador y cabecera
    detected_sep, header_idx, has_units = _detect_separator_and_header(filepath)
    
    sep_to_use = separator if separator is not None else detected_sep
    
    try:
        read_kwargs = {"sep": sep_to_use}
        if skip_rows is not None:
            read_kwargs["skiprows"] = skip_rows
        elif header_idx > 0:
            read_kwargs["skiprows"] = header_idx
            
        df = pd.read_csv(filepath, **read_kwargs)
        
        # Si se detectó una fila de unidades, la eliminamos (es el primer registro tras saltar la cabecera)
        if skip_rows is None and header_idx > 0 and has_units and not df.empty:
            df = df.iloc[1:].reset_index(drop=True)
            logger.info("  Se detectaron y eliminaron filas de metadatos/unidades de MoTeC")
            
    except Exception as e:
        raise DataLoaderException(f"Error al leer CSV: {str(e)}")

    if df.empty:
        raise DataLoaderException("El archivo CSV está vacío")

    # 1. Limpieza de nombres de columnas
    df.columns = df.columns.str.strip()
    
    # 2. Resolver alias de columnas
    df = _resolve_column_names(df)

    # 2b. Sintetizar Distance desde Speed+tiempo si no está disponible o si el
    # canal presente tiene todos los valores en cero (frecuente en CSVs de MoTeC
    # donde la columna "Distance" existe pero no se registra en sesión completa).
    dist_max = pd.to_numeric(df["Distance"], errors="coerce").abs().max() if "Distance" in df.columns else 0.0
    if "Distance" not in df.columns or not (dist_max > 10.0):
        df = _synthesize_distance(df)

    # 3. Verificación de canales esenciales
    missing = [ch for ch in ESSENTIAL_CHANNELS if ch not in df.columns]
    if missing:
        available = list(df.columns)
        raise DataLoaderException(
            f"Faltan canales esenciales: {missing}. "
            f"Columnas disponibles: {available}"
        )

    # 4. Reemplazar comas por puntos en columnas de texto/objeto e intentar convertirlas a float
    for col in df.columns:
        if df[col].dtype == object:
            try:
                cleaned = df[col].astype(str).str.replace(',', '.', regex=False).str.strip()
                converted = pd.to_numeric(cleaned, errors="coerce")
                # Si logramos convertir valores a número, guardamos la conversión
                if not converted.isnull().all():
                    df[col] = converted
                else:
                    df[col] = cleaned
            except Exception:
                pass

    # Asegurar que los canales base sean numéricos (forzando coerción)
    base_channels = ESSENTIAL_CHANNELS + ["Distance"]
    for ch in base_channels:
        if ch in df.columns:
            df[ch] = pd.to_numeric(df[ch], errors="coerce")

    # 5. Interpolar NaN en canales base
    present_base = [ch for ch in base_channels if ch in df.columns]
    if df[present_base].isnull().any().any():
        logger.warning("Valores NaN detectados en canales base. Interpolando...")
        df[present_base] = df[present_base].interpolate(method="linear")
        df[present_base] = df[present_base].ffill().bfill()

    logger.info(f"  ✓ Cargados {len(df)} registros, {len(df.columns)} canales")
    
    return df


def load_multiple_laps(directory: str, pattern: str = "*.csv") -> dict[str, pd.DataFrame]:
    """
    Carga múltiples archivos de telemetría de un directorio.
    
    Args:
        directory: Ruta al directorio con archivos CSV.
        pattern: Patrón glob para filtrar archivos (default: *.csv).
    
    Returns:
        Diccionario {nombre_archivo: DataFrame}.
    
    Raises:
        DataLoaderException: Si el directorio no existe o no contiene CSVs válidos.
    """
    import glob
    
    if not os.path.isdir(directory):
        raise DataLoaderException(f"Directorio no encontrado: {directory}")
    
    files = glob.glob(os.path.join(directory, pattern))
    
    if not files:
        raise DataLoaderException(f"No se encontraron archivos '{pattern}' en: {directory}")
    
    laps = {}
    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        try:
            laps[filename] = load_telemetry_data(filepath)
            logger.info(f"  ✓ {filename}")
        except DataLoaderException as e:
            logger.warning(f"  ✗ {filename}: {e}")
    
    if not laps:
        raise DataLoaderException("No se pudo cargar ningún archivo de telemetría")
    
    logger.info(f"  Total: {len(laps)} vueltas cargadas")
    return laps
