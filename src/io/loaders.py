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
    "LateralG":       ["LateralG", "lateral_g", "LatG", "G_Lat", "AccG_Lateral"],
    "LongitudinalG":  ["LongitudinalG", "longitudinal_g", "LonG", "G_Lon", "AccG_Longitudinal"],
    "LapTime":        ["LapTime", "lap_time", "Time", "time", "CurrentLapTime"],
    # New aliases for weather and coordinates
    "AirTemp":        ["Air Temp", "AirTemp", "air_temp", "AmbientTemp"],
    "RoadTemp":       ["Road Temp", "RoadTemp", "road_temp", "TrackTemp"],
    "CarCoordX":      ["Car Coord X", "car_coord_x", "PosX"],
    "CarCoordY":      ["Car Coord Y", "car_coord_y", "PosY"],  # plano horizontal
    "CarCoordZ":      ["Car Coord Z", "car_coord_z", "PosZ"],  # elevación real
    "SessionLapCount": ["Session Lap Count", "session_lap_count", "Lap"],
}

# Canales que DEBEN existir para que el pipeline funcione
ESSENTIAL_CHANNELS = ["Speed", "Brake", "Throttle", "Distance"]


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
    separators = [",", ";"]
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            # Leer las primeras 50 líneas
            lines = [f.readline() for _ in range(50)]
    except Exception:
        return ",", 0, False
        
    for sep in separators:
        for i, line in enumerate(lines):
            clean = line.replace('"', '').strip()
            parts = [p.strip() for p in clean.split(sep)]
            if "Time" in parts and "Distance" in parts:
                has_units = False
                if i + 1 < len(lines):
                    next_clean = lines[i+1].replace('"', '').strip()
                    next_parts = [p.strip() for p in next_clean.split(sep)]
                    if any(u in next_parts for u in ["s", "m", "km/h", "rpm", "deg"]):
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

    # Asegurar que los canales esenciales sean numéricos (forzando coerción)
    for ch in ESSENTIAL_CHANNELS:
        df[ch] = pd.to_numeric(df[ch], errors="coerce")
    
    # 5. Interpolar NaN en canales esenciales
    if df[ESSENTIAL_CHANNELS].isnull().any().any():
        logger.warning("Valores NaN detectados en canales esenciales. Interpolando...")
        df[ESSENTIAL_CHANNELS] = df[ESSENTIAL_CHANNELS].interpolate(method="linear")
        df[ESSENTIAL_CHANNELS] = df[ESSENTIAL_CHANNELS].ffill().bfill()

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
