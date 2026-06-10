"""
Detección automática de eventos clave de telemetría.

Este módulo contiene los algoritmos centrales que un ingeniero de pista usa
para analizar el pilotaje:

1. Puntos de frenado: ¿Dónde empezó a frenar el piloto?
2. Apex (vértice): ¿Cuál fue la velocidad mínima en la curva?
3. Aceleración a fondo: ¿Cuándo aplicó 100% de throttle?
4. Segmentación de curvas: ¿Dónde empieza y termina cada curva?

Todos los eventos se detectan en función de la distancia, no del tiempo.
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import logging

logger = logging.getLogger(__name__)

# ── Constantes de detección ───────────────────────────────────────────────────
BRAKE_THRESHOLD_PCT = 5.0       # % mínimo de freno para considerar frenada activa
BRAKE_RELEASE_FACTOR = 0.5      # Factor para determinar fin de frenada (threshold * factor)
APEX_WINDOW_SAMPLES = 25        # Muestras a cada lado para detectar mínimo local
APEX_SPEED_FACTOR = 0.85        # El apex debe estar por debajo de este factor de la velocidad media
APEX_MIN_DISTANCE_M = 100.0     # Distancia mínima (m) entre apex consecutivos
FULL_THROTTLE_THRESHOLD_PCT = 98.0  # % mínimo de gas para considerar "fondo"
FULL_THROTTLE_RESET_PCT = 50.0  # % debajo del cual se resetea el estado de full throttle


def detect_braking_points(df: pd.DataFrame, threshold: float = BRAKE_THRESHOLD_PCT) -> list[dict]:
    """
    Detecta los puntos donde el piloto inicia la frenada.
    
    Un punto de frenado se define como el momento donde la presión de freno
    pasa de 0 (o < threshold) a ≥ threshold. En la industria esto se llama
    "brake application point".
    
    Args:
        df: DataFrame alineado por distancia con columnas 'Distance' y 'Brake'.
        threshold: Porcentaje mínimo de freno para considerar frenada activa.
    
    Returns:
        Lista de diccionarios con información de cada punto de frenado:
        [{"distance": float, "index": int, "brake_pressure": float}, ...]
    """
    brake = df["Brake"].values
    distance = df["Distance"].values
    
    braking_points = []
    is_braking = False
    
    for i in range(1, len(brake)):
        # Transición de no-frenado a frenado
        if not is_braking and brake[i] >= threshold and brake[i - 1] < threshold:
            braking_points.append({
                "distance": float(distance[i]),
                "index": i,
                "brake_pressure": float(brake[i]),
            })
            is_braking = True
        # Transición de frenado a no-frenado
        elif is_braking and brake[i] < threshold * BRAKE_RELEASE_FACTOR:
            is_braking = False
    
    logger.info(f"  Detectados {len(braking_points)} puntos de frenado")
    return braking_points


def detect_apex_points(df: pd.DataFrame, min_distance_between: float = APEX_MIN_DISTANCE_M) -> list[dict]:
    """
    Detecta los vértices (apex) de cada curva como mínimos locales de velocidad.
    
    El apex es el punto de velocidad mínima dentro de una zona de frenado/curva.
    Se filtran mínimos espurios exigiendo una distancia mínima entre apex
    consecutivos y un descenso significativo de velocidad respecto a la recta.
    
    Args:
        df: DataFrame alineado con columnas 'Distance' y 'Speed'.
        min_distance_between: Distancia mínima (metros) entre apex consecutivos.
    
    Returns:
        Lista de diccionarios:
        [{"distance": float, "index": int, "speed": float}, ...]
    """
    speed = df["Speed"].values
    distance = df["Distance"].values
    
    local_min_indices = argrelextrema(speed, np.less, order=APEX_WINDOW_SAMPLES)[0]

    mean_speed = np.mean(speed)
    speed_threshold = mean_speed * APEX_SPEED_FACTOR
    
    apex_points = []
    last_apex_distance = -np.inf
    
    for idx in local_min_indices:
        d = distance[idx]
        s = speed[idx]
        
        # Filtro 1: velocidad suficientemente baja para ser una curva
        if s > speed_threshold:
            continue
        
        # Filtro 2: distancia mínima entre apex consecutivos
        if d - last_apex_distance < min_distance_between:
            # Si este apex es más lento que el anterior, reemplazar
            if apex_points and s < apex_points[-1]["speed"]:
                apex_points[-1] = {
                    "distance": float(d),
                    "index": int(idx),
                    "speed": float(s),
                }
                last_apex_distance = d
            continue
        
        apex_points.append({
            "distance": float(d),
            "index": int(idx),
            "speed": float(s),
        })
        last_apex_distance = d
    
    logger.info(f"  Detectados {len(apex_points)} apex points")
    return apex_points


def detect_full_throttle_points(df: pd.DataFrame, threshold: float = FULL_THROTTLE_THRESHOLD_PCT) -> list[dict]:
    """
    Detecta los puntos donde el piloto aplica acelerador a fondo (≥ threshold%).
    
    Se busca la transición de throttle parcial a throttle completo, que marca
    la salida de la curva y el inicio de la fase de aceleración en recta.
    
    Args:
        df: DataFrame alineado con columnas 'Distance' y 'Throttle'.
        threshold: Porcentaje mínimo para considerar "full throttle" (default 98%).
    
    Returns:
        Lista de diccionarios:
        [{"distance": float, "index": int, "throttle": float}, ...]
    """
    throttle = df["Throttle"].values
    distance = df["Distance"].values
    
    full_throttle_points = []
    was_partial = True
    
    for i in range(1, len(throttle)):
        # Transición de parcial a full throttle
        if was_partial and throttle[i] >= threshold and throttle[i - 1] < threshold:
            full_throttle_points.append({
                "distance": float(distance[i]),
                "index": i,
                "throttle": float(throttle[i]),
            })
            was_partial = False
        # Reset: throttle baja significativamente (nueva curva)
        elif not was_partial and throttle[i] < FULL_THROTTLE_RESET_PCT:
            was_partial = True
    
    logger.info(f"  Detectados {len(full_throttle_points)} puntos de aceleración a fondo")
    return full_throttle_points


def segment_corners(
    df: pd.DataFrame,
    brake_threshold: float = BRAKE_THRESHOLD_PCT,
    min_distance_between: float = APEX_MIN_DISTANCE_M,
) -> list[dict]:
    """
    Segmenta automáticamente el circuito en curvas.
    
    Cada curva se define como una zona que contiene:
    - Un punto de frenado (entrada)
    - Un apex (vértice, velocidad mínima)
    - Un punto de aceleración a fondo (salida)
    
    Args:
        df: DataFrame alineado por distancia.
        brake_threshold: Umbral de freno para detectar frenada.
        min_distance_between: Distancia mínima entre apex consecutivos.
    
    Returns:
        Lista de diccionarios, uno por curva:
        [{
            "corner_number": int,
            "braking_point": {"distance": float, ...},
            "apex": {"distance": float, "speed": float, ...},
            "full_throttle": {"distance": float, ...},
        }, ...]
    """
    logger.info("Segmentando curvas del circuito...")
    
    braking = detect_braking_points(df, threshold=brake_threshold)
    apexes = detect_apex_points(df, min_distance_between=min_distance_between)
    throttles = detect_full_throttle_points(df)
    
    corners = []
    
    for i, apex in enumerate(apexes):
        apex_d = apex["distance"]
        
        # Encontrar el punto de frenado más cercano ANTES del apex
        brake_candidates = [b for b in braking if b["distance"] < apex_d]
        if not brake_candidates:
            continue
        brake_point = brake_candidates[-1]  # El más cercano al apex
        
        # Encontrar el punto de aceleración más cercano DESPUÉS del apex
        throttle_candidates = [t for t in throttles if t["distance"] > apex_d]
        if not throttle_candidates:
            continue
        throttle_point = throttle_candidates[0]  # El más cercano al apex
        
        corners.append({
            "corner_number": i + 1,
            "braking_point": brake_point,
            "apex": apex,
            "full_throttle": throttle_point,
        })
    
    logger.info(f"  ✓ Segmentadas {len(corners)} curvas completas")
    return corners
