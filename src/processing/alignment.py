"""
Módulo de alineación por distancia.

En telemetría de motorsport, las series temporales de dos vueltas no coinciden
si una vuelta es más rápida que otra. La solución estándar de la industria es
re-muestrear todos los canales usando la distancia recorrida en la pista como
eje X común, en lugar del tiempo.

Este módulo interpola los datos a intervalos uniformes de distancia (por defecto
cada 1 metro) usando interpolación cúbica de scipy.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import logging

logger = logging.getLogger(__name__)


def align_by_distance(df: pd.DataFrame, distance_step: float = 1.0) -> pd.DataFrame:
    """
    Re-muestrea un DataFrame de telemetría a intervalos uniformes de distancia.
    
    Esto es fundamental porque los datos crudos de ACTI pueden tener muestreo
    temporal irregular, y las comparaciones entre vueltas requieren que ambas
    estén indexadas al mismo vector de distancia.
    
    Args:
        df: DataFrame con al menos la columna 'Distance' y otros canales.
        distance_step: Intervalo de distancia en metros entre muestras (default: 1.0m).
    
    Returns:
        DataFrame con distancia uniforme como índice implícito.
    """
    logger.info(f"Alineando por distancia con paso de {distance_step}m")
    
    # Validar que Distance existe y es monótonamente creciente
    if "Distance" not in df.columns:
        raise ValueError("El DataFrame no contiene la columna 'Distance'")
    
    # Eliminar duplicados de distancia (mantener el primero)
    df = df.drop_duplicates(subset=["Distance"], keep="first").copy()
    
    # Asegurar orden creciente
    df = df.sort_values("Distance").reset_index(drop=True)
    
    # Definir el nuevo vector de distancia uniforme
    d_min = np.ceil(df["Distance"].min())
    d_max = np.floor(df["Distance"].max())
    new_distance = np.arange(d_min, d_max + distance_step, distance_step)
    
    logger.info(f"  Rango original: [{df['Distance'].min():.1f}, {df['Distance'].max():.1f}]m "
                f"({len(df)} muestras)")
    logger.info(f"  Rango alineado: [{d_min:.1f}, {d_max:.1f}]m "
                f"({len(new_distance)} muestras)")
    
    # Interpolar cada canal
    result = {"Distance": new_distance}
    
    # Columnas a interpolar (todas excepto Distance)
    channels_to_interpolate = [col for col in df.columns if col != "Distance"]
    
    for channel in channels_to_interpolate:
        if df[channel].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]:
            try:
                # Usar interpolación cúbica para canales continuos
                # Para 'Gear' usar interpolación nearest (es un valor discreto)
                method = "nearest" if channel == "Gear" else "cubic"
                
                interpolator = interp1d(
                    df["Distance"].values,
                    df[channel].values,
                    kind=method,
                    bounds_error=False,
                    fill_value="extrapolate"
                )
                result[channel] = interpolator(new_distance)
                
            except Exception as e:
                logger.warning(f"  No se pudo interpolar el canal '{channel}': {e}")
                # Fallback a interpolación lineal
                interpolator = interp1d(
                    df["Distance"].values,
                    df[channel].values,
                    kind="linear",
                    bounds_error=False,
                    fill_value="extrapolate"
                )
                result[channel] = interpolator(new_distance)
        else:
            logger.warning(f"  Canal '{channel}' no es numérico, se omite en la interpolación.")
    
    df_aligned = pd.DataFrame(result)
    
    # Post-procesamiento: clipear valores que no deben ser negativos
    for col in ["Speed", "Brake", "Throttle", "RPM"]:
        if col in df_aligned.columns:
            df_aligned[col] = df_aligned[col].clip(lower=0)
    
    # Clipear freno y acelerador a 100%
    for col in ["Brake", "Throttle"]:
        if col in df_aligned.columns:
            df_aligned[col] = df_aligned[col].clip(upper=100)
    
    logger.info(f"  ✓ Alineación completada: {df_aligned.shape}")
    
    return df_aligned


def align_pair(df_a: pd.DataFrame, df_b: pd.DataFrame, distance_step: float = 1.0):
    """
    Alinea dos vueltas a un vector de distancia común.
    
    Primero alinea cada vuelta individualmente, luego recorta ambas al rango
    de distancia compartido para que tengan exactamente la misma longitud.
    
    Args:
        df_a: DataFrame de la vuelta A (referencia).
        df_b: DataFrame de la vuelta B (a comparar).
        distance_step: Intervalo de distancia en metros.
    
    Returns:
        Tuple (df_a_aligned, df_b_aligned) con el mismo número de filas
        e idéntico vector de distancia.
    """
    logger.info("Alineando par de vueltas a vector de distancia común...")
    
    # Alinear cada una individualmente
    df_a_aligned = align_by_distance(df_a, distance_step)
    df_b_aligned = align_by_distance(df_b, distance_step)
    
    # Encontrar el rango de distancia compartido
    d_start = max(df_a_aligned["Distance"].min(), df_b_aligned["Distance"].min())
    d_end = min(df_a_aligned["Distance"].max(), df_b_aligned["Distance"].max())
    
    logger.info(f"  Rango compartido: [{d_start:.1f}, {d_end:.1f}]m")
    
    # Recortar al rango compartido
    mask_a = (df_a_aligned["Distance"] >= d_start) & (df_a_aligned["Distance"] <= d_end)
    mask_b = (df_b_aligned["Distance"] >= d_start) & (df_b_aligned["Distance"] <= d_end)
    
    df_a_aligned = df_a_aligned[mask_a].reset_index(drop=True)
    df_b_aligned = df_b_aligned[mask_b].reset_index(drop=True)
    
    # Verificar que tienen la misma longitud
    min_len = min(len(df_a_aligned), len(df_b_aligned))
    df_a_aligned = df_a_aligned.iloc[:min_len].reset_index(drop=True)
    df_b_aligned = df_b_aligned.iloc[:min_len].reset_index(drop=True)
    
    logger.info(f"  ✓ Par alineado: {min_len} muestras cada vuelta")
    
    return df_a_aligned, df_b_aligned
