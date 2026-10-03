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
from scipy.interpolate import interp1d, make_interp_spline
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

    d_min = np.ceil(df["Distance"].min())
    d_max = np.floor(df["Distance"].max())

    logger.info(f"  Rango original: [{df['Distance'].min():.1f}, {df['Distance'].max():.1f}]m "
                f"({len(df)} muestras)")

    # Si el segmento no tiene rango útil (ej. 1 sola fila o distancia = 0)
    if d_max <= d_min or len(df) < 2:
        logger.warning(f"  Segmento con rango de distancia insuficiente ({len(df)} fila(s)). "
                       f"Devolviendo copia sin reinterpolación.")
        return df.reset_index(drop=True)

    new_distance = np.arange(d_min, d_max + distance_step, distance_step)
    logger.info(f"  Rango alineado: [{d_min:.1f}, {d_max:.1f}]m "
                f"({len(new_distance)} muestras)")

    n_pts = len(df)

    def _pick_method(channel: str) -> str:
        if channel == "Gear":
            return "nearest"
        if n_pts >= 4:
            return "cubic"
        if n_pts >= 2:
            return "linear"
        return "nearest"

    # Interpolar cada canal
    numeric_channels = [
        col for col in df.columns
        if col != "Distance" and df[col].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]
    ]
    for col in df.columns:
        if col != "Distance" and col not in numeric_channels:
            logger.debug(f"  Canal '{col}' no es numérico, se omite en la interpolación.")

    x_old = df["Distance"].values
    cols_out = ["Distance"] + numeric_channels
    out = np.empty((len(cols_out), len(new_distance)), dtype=np.float64)
    out[0] = new_distance
    row_of = {c: i + 1 for i, c in enumerate(numeric_channels)}

    # Camino rapido: una sola spline cubica multi-columna (misma matematica que interp1d por
    # columna, pero la factorizacion banded se hace una vez en vez de ~170).
    batch = [c for c in numeric_channels if c != "Gear"] if n_pts >= 4 else []
    if batch:
        try:
            y = df[batch].to_numpy(dtype=np.float64)
            spline = make_interp_spline(x_old, y, k=3, axis=0, check_finite=False)
            res = spline(new_distance)
            for j, c in enumerate(batch):
                out[row_of[c]] = res[:, j]
        except Exception as e:
            logger.debug(f"  spline por lotes falló ({e}); interpolación columna a columna.")
            batch = []
    batched = set(batch)

    for channel in numeric_channels:
        if channel in batched:
            continue
        col_vals = df[channel].values

        # Try primary method, fall back progressively: cubic → linear → nearest
        for method in [_pick_method(channel), "linear", "nearest"]:
            try:
                interpolator = interp1d(
                    x_old,
                    col_vals,
                    kind=method,
                    bounds_error=False,
                    fill_value="extrapolate",
                )
                out[row_of[channel]] = interpolator(new_distance)
                break
            except Exception as e:
                if method == "nearest":
                    # Last resort: fill with the only available value
                    out[row_of[channel]] = np.full(len(new_distance), col_vals[0] if len(col_vals) else np.nan)
                    break
                logger.debug(f"  método '{method}' falló en '{channel}': {e}. Probando siguiente.")

    df_aligned = pd.DataFrame(out.T, columns=cols_out)

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


def align_pair(df_a: pd.DataFrame, df_b: pd.DataFrame, distance_step: float = 1.0,
               pre_a: pd.DataFrame = None):
    """
    Alinea dos vueltas a un vector de distancia común.
    
    Primero alinea cada vuelta individualmente, luego recorta ambas al rango
    de distancia compartido para que tengan exactamente la misma longitud.
    
    Args:
        df_a: DataFrame de la vuelta A (referencia).
        df_b: DataFrame de la vuelta B (a comparar).
        distance_step: Intervalo de distancia en metros.
        pre_a: align_by_distance(df_a, distance_step) ya calculado (solo lectura; se reutiliza).
    
    Returns:
        Tuple (df_a_aligned, df_b_aligned) con el mismo número de filas
        e idéntico vector de distancia.
    """
    logger.info("Alineando par de vueltas a vector de distancia común...")
    
    # Alinear cada una individualmente
    # pre_a: resultado ya calculado de align_by_distance(df_a) (misma referencia en N pares)
    df_a_aligned = pre_a if pre_a is not None else align_by_distance(df_a, distance_step)
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
