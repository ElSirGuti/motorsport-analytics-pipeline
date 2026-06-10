"""
Filtros de señal para limpieza de datos de telemetría.

Los datos crudos de sensores (especialmente canales de aceleración lateral/longitudinal)
contienen ruido de alta frecuencia que puede contaminar la detección de eventos.
Este módulo proporciona filtros estándar para suavizar y limpiar señales.
"""

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d
import logging

logger = logging.getLogger(__name__)


def smooth_signal(series: pd.Series, window: int = 5) -> pd.Series:
    """
    Aplica un filtro de media móvil para suavizar una señal.
    
    Útil para canales como LateralG, LongitudinalG, SteerAngle donde
    el ruido del sensor oscila rápidamente pero el valor real es suave.
    
    Args:
        series: Serie de datos a suavizar.
        window: Tamaño de la ventana de media móvil (en muestras).
                Valores más altos = más suavizado, pero más latencia.
    
    Returns:
        Serie suavizada del mismo tamaño.
    """
    if window < 1:
        logger.warning("Ventana de suavizado < 1, devolviendo datos originales.")
        return series
    
    smoothed = uniform_filter1d(series.values.astype(float), size=window)
    return pd.Series(smoothed, index=series.index, name=series.name)


def remove_outliers(series: pd.Series, z_threshold: float = 3.0) -> pd.Series:
    """
    Elimina outliers usando el método de Z-score.
    
    Los valores que exceden z_threshold desviaciones estándar de la media
    se reemplazan por interpolación lineal de sus vecinos.
    
    Args:
        series: Serie de datos a limpiar.
        z_threshold: Número de desviaciones estándar para considerar outlier.
    
    Returns:
        Serie limpia con outliers reemplazados.
    """
    mean = series.mean()
    std = series.std()
    
    if std == 0:
        return series
    
    z_scores = np.abs((series - mean) / std)
    outlier_mask = z_scores > z_threshold
    n_outliers = outlier_mask.sum()
    
    if n_outliers > 0:
        logger.info(f"  Se detectaron {n_outliers} outliers en '{series.name}' "
                     f"(z > {z_threshold})")
        cleaned = series.copy()
        cleaned[outlier_mask] = np.nan
        cleaned = cleaned.interpolate(method="linear")
        # Rellenar NaN en los extremos
        cleaned = cleaned.ffill().bfill()
        return cleaned
    
    return series


def apply_standard_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica filtros estándar recomendados a un DataFrame de telemetría.
    
    - Suaviza canales de fuerza G (window=7)
    - Suaviza ángulo de dirección (window=5)
    - Elimina outliers de todos los canales numéricos
    
    Args:
        df: DataFrame de telemetría.
    
    Returns:
        DataFrame con filtros aplicados.
    """
    df = df.copy()
    
    # Suavizar canales ruidosos
    g_channels = ["LateralG", "LongitudinalG"]
    for ch in g_channels:
        if ch in df.columns:
            df[ch] = smooth_signal(df[ch], window=7)
    
    if "SteerAngle" in df.columns:
        df["SteerAngle"] = smooth_signal(df["SteerAngle"], window=5)
    
    # Eliminar outliers de canales clave
    for ch in ["Speed", "Brake", "Throttle", "RPM"]:
        if ch in df.columns:
            df[ch] = remove_outliers(df[ch], z_threshold=4.0)
    
    return df
