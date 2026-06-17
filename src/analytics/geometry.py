"""
Módulo de geometría de pista para análisis de telemetría de motorsport.

Pipeline de procesamiento:
  1. Elimina duplicados de distancia y ordena el DataFrame.
  2. Remuestrea las coordenadas al eje de distancia uniforme (1 m/muestra).
  3. Aplica filtro Savitzky-Golay macroscópico (ventana=75m, grado=2) sobre
     el plano horizontal real (CarCoordX, CarCoordY) de la telemetría ACTI.
  4. Construye Splines Cúbicos para obtener las derivadas espaciales.
  5. Calcula la curvatura geométrica κ = |x'y'' - y'x''| / (x'² + y'²)^1.5.
  6. Detecta los Apex del circuito usando find_peaks con prominencia dinámica
     y un filtro físico de acelerador (Throttle < 85 %).

Nota sobre coordenadas ACTI (Assetto Corsa):
  - Car Coord X → eje lateral  (→ CarCoordX en el pipeline)
  - Car Coord Y → eje de profundidad (→ CarCoordY en el pipeline)
  - Car Coord Z → elevación real   (→ CarCoordZ / Elevation)
  El plano horizontal de la pista está definido por X e Y.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks, savgol_filter

logger = logging.getLogger(__name__)

# ── Constantes de configuración ───────────────────────────────────────────────
SAVGOL_WINDOW  = 75   # metros — ventana macroscópica para Savitzky-Golay
SAVGOL_ORDER   = 2    # grado del polinomio de suavizado
RESAMPLE_STEP  = 1.0  # metros entre muestras del eje uniforme

APEX_HEIGHT_MIN    = 0.005   # κ mínima (rectas por debajo quedan excluidas); reducida para capturar curvas de baja curvatura
APEX_PROM_FACTOR   = 0.10    # prominencia = 10 % del pico máximo (era 15 %) — captura más curvas lentas
APEX_DISTANCE_MIN  = 80      # metros mínimos entre dos Apex consecutivos (era 100 m)
APEX_THROTTLE_MAX  = 95.0    # % — en el apex real no se va al 100 %, pero sí se puede abrir un poco (era 85 %)


_GPS_PAIRS = [
    ("Lat", "Lon"),
    ("GPSlat", "GPSlon"),
    ("GPS Lat", "GPS Lon"),
    ("gps_lat", "gps_lon"),
]
_METERS_PER_DEG = 111_319.9


def _synthesize_coordinates_dead_reckoning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Populate CarCoordX/CarCoordY from the best available source:
      1. Already present (ACTI/direct coordinates) → return unchanged.
      2. iRacing VelocityX/VelocityY (world-frame, 360 Hz) → integrate for exact position.
      3. GPS lat/lon → equirectangular projection to metres (1 Hz, lower resolution).
      4. Dead reckoning from YawRate + Speed → last resort.
    """
    if 'CarCoordX' in df.columns and 'CarCoordY' in df.columns:
        return df

    # ── iRacing: absolute yaw angle + Speed (no heading drift) ──────────────
    # YawNorth = yaw relative to North in radians (iRacing native channel).
    # Using the absolute heading avoids the integration-drift problem of YawRate.
    # Speed is in km/h (loader converts from m/s); divide by 3.6 to get m/s.
    yaw_col = next((c for c in ('YawNorth', 'Gyro Yaw Angle', 'Yaw') if c in df.columns), None)
    if yaw_col and 'Speed' in df.columns:
        yaw    = pd.to_numeric(df[yaw_col], errors='coerce').ffill().bfill().fillna(0)
        spd_ms = pd.to_numeric(df['Speed'],  errors='coerce').fillna(0) / 3.6
        if 'Distance' in df.columns:
            dist_v = pd.to_numeric(df['Distance'], errors='coerce').ffill().bfill()
            ds_v   = dist_v.diff().fillna(0).clip(lower=0, upper=20.0)
            dt_y   = (ds_v / spd_ms.clip(lower=0.5)).clip(lower=0, upper=0.5)
        else:
            dt_y = pd.Series(1.0 / 360.0, index=df.index)
        df_new = df.copy()
        df_new['CarCoordX'] = np.cumsum((spd_ms * np.cos(yaw) * dt_y).fillna(0).values)
        df_new['CarCoordY'] = np.cumsum((spd_ms * np.sin(yaw) * dt_y).fillna(0).values)
        logger.info("Coordenadas sintetizadas desde %s + Speed (yaw absoluto)", yaw_col)
        return df_new

    # ── iRacing GPS: convert lat/lon → local X/Y in metres ───────────────────
    for lat_col, lon_col in _GPS_PAIRS:
        if lat_col in df.columns and lon_col in df.columns:
            lat = pd.to_numeric(df[lat_col], errors='coerce')
            lon = pd.to_numeric(df[lon_col], errors='coerce')
            if lat.notna().sum() > 10 and lon.notna().sum() > 10:
                lat0 = float(lat.dropna().iloc[0])
                lon0 = float(lon.dropna().iloc[0])
                cos_lat = np.cos(np.deg2rad(lat0))
                df_new = df.copy()
                df_new['CarCoordX'] = (lon - lon0) * cos_lat * _METERS_PER_DEG
                df_new['CarCoordY'] = (lat - lat0) * _METERS_PER_DEG
                return df_new

    if 'Speed' not in df.columns:
        return df

    speed_ms = pd.to_numeric(df['Speed'], errors='coerce').fillna(0) / 3.6

    # Prefer computing dt from Distance/Speed so we don't depend on time channel
    # naming (the loader renames 'Time'→'LapTime', breaking time-based lookups).
    # ds/v gives the correct time step at any sample rate without configuration.
    if 'Distance' in df.columns:
        dist = pd.to_numeric(df['Distance'], errors='coerce').ffill().bfill()
        ds   = dist.diff().fillna(0).clip(lower=0, upper=20.0)    # max 20m/step
        safe_speed = speed_ms.clip(lower=0.5)
        dt = (ds / safe_speed).clip(lower=0, upper=0.5)
    else:
        time_col = next((c for c in [
            'LR Sample Clock', 'HR Sample Clock', 'MR Sample Clock',
            'SessionTime', 'Session Time', 'LapTime', 'Time', 'time',
        ] if c in df.columns), None)
        if time_col:
            t  = pd.to_numeric(df[time_col], errors='coerce').ffill().bfill()
            dt = t.diff().fillna(0).clip(lower=0, upper=0.5)
        else:
            dt = pd.Series(1.0 / 60.0, index=df.index)

    heading_rate = None
    if 'YawRate' in df.columns:
        yr = pd.to_numeric(df['YawRate'], errors='coerce').fillna(0)
        if yr.abs().max() > 5.0:
            yr = np.deg2rad(yr)
        heading_rate = yr
    elif 'SteerAngle' in df.columns or 'SteeringWheelAngle' in df.columns:
        col = 'SteerAngle' if 'SteerAngle' in df.columns else 'SteeringWheelAngle'
        steer_deg = pd.to_numeric(df[col], errors='coerce').fillna(0)
        heading_rate = steer_deg * 0.003

    if heading_rate is None:
        return df

    heading = np.cumsum((heading_rate * dt).fillna(0).values)
    dx = (speed_ms * np.cos(heading) * dt).fillna(0)
    dy = (speed_ms * np.sin(heading) * dt).fillna(0)
    
    df_new = df.copy()
    df_new['CarCoordX'] = np.cumsum(dx.values)
    df_new['CarCoordY'] = np.cumsum(dy.values)
    return df_new

def procesar_geometria_pista_perfecta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Procesa la geometría de la pista a partir de los datos de telemetría limpios.

    Aplica remuestreo uniforme, filtro Savitzky-Golay macroscópico y cálculo
    de curvatura geométrica sobre el plano horizontal real de la telemetría
    ACTI (CarCoordX, CarCoordY).

    Args:
        df: DataFrame con al menos las columnas 'Distance', 'CarCoordX',
            'CarCoordY' y 'CarCoordZ' (nombres canónicos del loader).
            Opcionalmente puede contener 'Speed', 'Throttle', 'Brake'.

    Returns:
        DataFrame con eje de distancia uniforme y columnas:
        'Distance', 'Curvature', 'Elevation', y los canales opcionales
        interpolados al mismo eje.
    """
    logger.info("🧼 Iniciando purga de ruido y alineación geométrica real...")

    df = _synthesize_coordinates_dead_reckoning(df)
    
    if "CarCoordX" not in df.columns or "CarCoordY" not in df.columns:
        logger.warning("No se pudo sintetizar coordenadas. Fallback a curvatura 0.")
        dist_max = df["Distance"].max() if not df.empty else 1000.0
        dist_uniforme = np.arange(0, dist_max, RESAMPLE_STEP)
        return pd.DataFrame({
            "Distance": dist_uniforme,
            "Curvature": np.zeros_like(dist_uniforme)
        })

    # 1. Eliminar duplicados y garantizar orden creciente de distancia
    df = (
        df.drop_duplicates(subset=["Distance"])
          .sort_values("Distance")
          .reset_index(drop=True)
    )

    dist_max = df["Distance"].max()
    dist_uniforme = np.arange(0, dist_max, RESAMPLE_STEP)

    # 2. Remuestreo lineal de las coordenadas horizontales al eje uniforme
    # GPS channels may be sparse (e.g. 1 Hz vs 360 Hz telemetry) — use only
    # non-NaN rows so np.interp doesn't produce NaN-contaminated output.
    coord_mask = df["CarCoordX"].notna() & df["CarCoordY"].notna()
    if coord_mask.sum() < 10:
        logger.warning("Coordenadas insuficientes (%d pts) — fallback curvatura 0.", coord_mask.sum())
        return pd.DataFrame({"Distance": dist_uniforme, "Curvature": np.zeros_like(dist_uniforme)})
    dist_c = df.loc[coord_mask, "Distance"].values
    x_c    = df.loc[coord_mask, "CarCoordX"].values
    y_c    = df.loc[coord_mask, "CarCoordY"].values
    x_interp = np.interp(dist_uniforme, dist_c, x_c)
    y_interp = np.interp(dist_uniforme, dist_c, y_c)

    # 3. Filtro Savitzky-Golay macroscópico
    #    Ventana de 75 m y grado 2: elimina el jitter del motor de física sin
    #    distorsionar la geometría macroscópica de las curvas.
    x_smooth = savgol_filter(x_interp, window_length=SAVGOL_WINDOW, polyorder=SAVGOL_ORDER)
    y_smooth = savgol_filter(y_interp, window_length=SAVGOL_WINDOW, polyorder=SAVGOL_ORDER)

    # 4. Splines Cúbicos para derivadas espaciales precisas
    spline_x = CubicSpline(dist_uniforme, x_smooth)
    spline_y = CubicSpline(dist_uniforme, y_smooth)

    dx  = spline_x(dist_uniforme, 1)   # x'
    ddx = spline_x(dist_uniforme, 2)   # x''
    dy  = spline_y(dist_uniforme, 1)   # y'
    ddy = spline_y(dist_uniforme, 2)   # y''

    # 5. Curvatura geométrica κ = |x'y'' - y'x''| / (x'² + y'²)^1.5
    numerador    = np.abs(dx * ddy - dy * ddx)
    denominador  = (dx**2 + dy**2) ** 1.5
    curvatura    = np.where(denominador > 1e-6, numerador / denominador, 0.0)
    
    # Clip extreme curvature spikes (noise) to a reasonable maximum (R_min = 2m -> k_max = 0.5)
    curvatura = np.clip(curvatura, 0, 0.5)

    df_geo = pd.DataFrame({
        "Distance":  dist_uniforme,
        "Curvature": curvatura,
    })

    # 6. Interpolar canales de telemetría al nuevo eje uniforme
    canales_opcionales = ["Speed", "Throttle", "Brake"]
    for col in canales_opcionales:
        if col in df.columns:
            df_geo[col] = np.interp(dist_uniforme, df["Distance"], df[col])

    # Elevación real (Car Coord Z)
    if "CarCoordZ" in df.columns:
        df_geo["Elevation"] = np.interp(dist_uniforme, df["Distance"], df["CarCoordZ"])

    n_muestras = len(df_geo)
    max_k = curvatura.max()
    logger.info(
        f"  ✓ Geometría procesada: {n_muestras} m de pista, κ_max={max_k:.4f} "
        f"(R_min≈{1/max_k:.1f}m)" if max_k > 0 else
        f"  ✓ Geometría procesada: {n_muestras} m de pista"
    )
    return df_geo


def detectar_apexes_perfectos(
    df_geo: pd.DataFrame,
    height_min: float = APEX_HEIGHT_MIN,
    prom_factor: float = APEX_PROM_FACTOR,
    distance_min: int = APEX_DISTANCE_MIN,
    throttle_max: float = APEX_THROTTLE_MAX,
) -> pd.DataFrame:
    """
    Detecta los Apex del circuito con calibración de grado industrial.

    Combina dos capas de filtrado:
      1. Geométrico: picos de curvatura con height y prominencia dinámica.
      2. Físico: en un Apex real de competición el piloto no pisa el acelerador
         a fondo (Throttle < throttle_max %).

    Args:
        df_geo:       DataFrame de salida de `procesar_geometria_pista_perfecta`.
        height_min:   Curvatura mínima para considerar un punto como curva.
        prom_factor:  Factor sobre κ_max para calcular la prominencia mínima.
        distance_min: Separación mínima en muestras entre Apex consecutivos.
        throttle_max: Porcentaje máximo de acelerador permitido en un Apex real.

    Returns:
        DataFrame filtrado con una fila por Apex detectado, incluyendo las
        columnas 'Distance', 'Curvature', 'Speed', 'Throttle' y 'Elevation'.
    """
    max_kappa  = df_geo["Curvature"].max()
    prominencia = max_kappa * prom_factor

    logger.info(
        f"🔍 Detectando Apexes: κ_max={max_kappa:.4f}, "
        f"prominencia={prominencia:.4f}, distance={distance_min}"
    )

    indices_apex, _ = find_peaks(
        df_geo["Curvature"],
        height=height_min,
        prominence=prominencia,
        distance=distance_min,
    )

    candidatos = df_geo.iloc[indices_apex].copy()

    # Filtro físico: en el Apex real el piloto no va a fondo
    if "Throttle" in candidatos.columns:
        apexes = candidatos[candidatos["Throttle"] < throttle_max].copy()
    else:
        apexes = candidatos.copy()

    logger.info(f"  ✓ {len(apexes)} curvas reales detectadas (de {len(candidatos)} candidatos)")
    return apexes


def reporte_apexes(apexes: pd.DataFrame) -> str:
    """
    Genera un reporte de consola legible con el mapa de curvas del circuito.

    Args:
        apexes: DataFrame devuelto por `detectar_apexes_perfectos`.

    Returns:
        Cadena de texto con el reporte formateado.
    """
    lineas = [
        "\n=======================================================",
        "      REPORTE GEOMÉTRICO CALIBRADO (PRODUCCIÓN)       ",
        "=======================================================",
    ]
    for i, (_, apex) in enumerate(apexes.iterrows(), 1):
        dist    = apex["Distance"]
        vel     = apex.get("Speed", float("nan"))
        kappa   = apex["Curvature"]
        alt     = apex.get("Elevation", float("nan"))
        throttle = apex.get("Throttle", float("nan"))

        radio = 1 / kappa if kappa > 0 else float("inf")
        tipo  = "Rápida" if radio > 90 else "Media" if radio > 40 else "Frenada Fuerte / Lenta"

        lineas.append(
            f"📍 Curva {i:02d} | {dist:6.1f}m | "
            f"V-Apex: {vel:5.1f} km/h | "
            f"Alt: {alt:5.1f}m | "
            f"Throttle: {throttle:4.1f}% | "
            f"Radio: {radio:.1f}m -> [{tipo}]"
        )
    lineas.append("=======================================================\n")
    return "\n".join(lineas)
