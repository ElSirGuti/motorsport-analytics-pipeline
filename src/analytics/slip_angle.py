"""
Estimación de Ángulo de Deslizamiento del Chasis (Body Sideslip β).

Método cinemático integrado (bicycle model):

    dt     = 1 m / Vx   (tiempo para recorrer 1 m a velocidad Vx)
    Vy_dot = LateralG · g  −  YawRate_rad · Vx
    Vy     = ∫ Vy_dot dt   (con corrección de deriva lineal)
    β      = arctan2(Vy, Vx)   → grados

Ángulos de deslizamiento de ruedas (bicycle model, geometría estimada):
    αF = δ_wheel − β − L_f · r / Vx      (eje delantero)
    αR =         − β + L_r · r / Vx      (eje trasero)
    Balance = αF − αR
        > 0  →  subviraje (frontal trabaja más)
        < 0  →  sobreviraje (trasero trabaja más)

Corrección de deriva: eliminación de componente lineal (válida en
circuito cerrado donde el ángulo promedio debe ser ≈ 0).
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

G_MS2          = 9.80665
DOWNSAMPLE     = 5
WHEELBASE_M    = 2.48    # m — estimado para coches sport (Cayman GT4 ≈ 2.476 m)
L_F_RATIO      = 0.44    # CoG-to-front / wheelbase (44 % delante)
STEER_RATIO    = 14.0    # relación cremallera estimada (giro volante → rueda)
MIN_SPEED_MS   = 3.0     # m/s — ignorar muestras casi parado (div/0)
OS_THRESHOLD   = 2.0     # deg: αR − αF > OS_THRESHOLD → sobreviraje
US_THRESHOLD   = 2.0     # deg: αF − αR > US_THRESHOLD → subviraje


def _yaw_to_rad(yaw: pd.Series) -> pd.Series:
    """
    MoTeC exporta el Chassis Yaw Rate en °/s.
    Detectamos la unidad por el rango observado: si el máximo absoluto
    supera 6.3 rad/s (≈ una vuelta completa/s) asumimos ya está en rad/s;
    de lo contrario convertimos de °/s.
    """
    abs_max = float(yaw.abs().max())
    if abs_max > 6.3:
        return yaw  # ya en rad/s
    return np.deg2rad(yaw)


def _integrate_slip(speed_kmh: pd.Series,
                    lat_g: pd.Series,
                    yaw_rad_s: pd.Series) -> pd.Series:
    """
    Integra Vy_dot para obtener Vy y devuelve β en grados.
    Aplica corrección de deriva lineal (válida en circuito cerrado).
    """
    vx = (speed_kmh / 3.6).clip(lower=MIN_SPEED_MS)  # m/s

    # dt estimado a partir del paso de distancia (1 m/sample en df alineado)
    dt = (1.0 / vx).clip(lower=0, upper=2.0)  # segundos por metro

    ay = lat_g * G_MS2  # m/s²
    vy_dot = ay - yaw_rad_s * vx

    # Integración + corrección de deriva lineal
    vy_raw = (vy_dot * dt).cumsum()
    n = len(vy_raw)
    if n < 2:
        return pd.Series(0.0, index=speed_kmh.index)
    drift = np.linspace(float(vy_raw.iloc[0]), float(vy_raw.iloc[-1]), n)
    vy = vy_raw.values - drift

    beta = np.degrees(np.arctan2(vy, vx.values))
    return pd.Series(beta, index=speed_kmh.index)


def _wheel_slip_angles(speed_kmh: pd.Series,
                       lat_g: pd.Series,
                       yaw_rad_s: pd.Series,
                       steer_deg: pd.Series,
                       beta: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Calcula αF y αR en grados usando el modelo de bicicleta lineal.
    Devuelve (alpha_front, alpha_rear).
    """
    vx = (speed_kmh / 3.6).clip(lower=MIN_SPEED_MS)
    l_f = WHEELBASE_M * L_F_RATIO
    l_r = WHEELBASE_M * (1.0 - L_F_RATIO)

    # Ángulo de rueda frontal (del volante a la rueda)
    delta_wheel = steer_deg / STEER_RATIO  # °

    alpha_f = delta_wheel - beta - np.degrees(yaw_rad_s * l_f / vx)
    alpha_r =              -beta + np.degrees(yaw_rad_s * l_r / vx)

    return alpha_f, alpha_r


def _slip_summary(beta: pd.Series, alpha_f: pd.Series | None,
                  alpha_r: pd.Series | None) -> dict:
    """Aggregate statistics for one lap."""
    valid = beta.dropna()
    out: dict = {
        "beta_max":   round(float(valid.abs().max()), 2) if len(valid) else 0.0,
        "beta_mean":  round(float(valid.abs().mean()), 2) if len(valid) else 0.0,
        "beta_p95":   round(float(valid.abs().quantile(0.95)), 2) if len(valid) else 0.0,
    }
    if alpha_f is not None and alpha_r is not None:
        balance = alpha_f - alpha_r
        us_pct = float((balance > US_THRESHOLD).mean()) * 100
        os_pct = float((balance < -OS_THRESHOLD).mean()) * 100
        out["understeer_pct"]  = round(us_pct, 1)
        out["oversteer_pct"]   = round(os_pct, 1)
        out["neutral_pct"]     = round(100 - us_pct - os_pct, 1)
        out["balance_mean"]    = round(float(balance.mean()), 2)
    return out


def _slip_for_suffix(df: pd.DataFrame, suffix: str,
                     dist: pd.Series) -> dict | None:
    """Compute slip angle for one lap (suffix = '_Fast' or '_Slow')."""
    spd_col = f"Speed{suffix}"
    lat_col = f"LateralG{suffix}"
    yaw_col = f"YawRate{suffix}"
    str_col = f"SteerAngle{suffix}"

    if spd_col not in df.columns or lat_col not in df.columns:
        return None
    if yaw_col not in df.columns:
        logger.debug("YawRate%s no disponible — slip angle no calculable", suffix)
        return None

    spd = pd.to_numeric(df[spd_col], errors="coerce").fillna(0)
    lat = pd.to_numeric(df[lat_col], errors="coerce").fillna(0)
    yaw = _yaw_to_rad(pd.to_numeric(df[yaw_col], errors="coerce").fillna(0))

    beta = _integrate_slip(spd, lat, yaw)

    alpha_f, alpha_r = None, None
    has_steer = str_col in df.columns
    if has_steer:
        steer = pd.to_numeric(df[str_col], errors="coerce").fillna(0)
        alpha_f, alpha_r = _wheel_slip_angles(spd, lat, yaw, steer, beta)

    summary = _slip_summary(beta, alpha_f, alpha_r)
    summary["has_wheel_angles"] = has_steer

    idx = range(0, len(dist), DOWNSAMPLE)
    per_dist: dict = {
        "distance": [round(float(dist.iloc[i]), 1) for i in idx],
        "beta":     [round(float(beta.iloc[i]), 3) for i in idx],
    }
    if alpha_f is not None:
        per_dist["alpha_f"]  = [round(float(alpha_f.iloc[i]), 3) for i in idx]
        per_dist["alpha_r"]  = [round(float(alpha_r.iloc[i]), 3) for i in idx]
        per_dist["balance"]  = [
            round(float(alpha_f.iloc[i] - alpha_r.iloc[i]), 3) for i in idx
        ]

    return {"summary": summary, "per_distance": per_dist}


def analizar_slip_angle(df: pd.DataFrame) -> dict:
    """
    Entry point. Works on the aligned DataFrame (uses _Fast / _Slow suffixes).
    Returns body slip angle β and front/rear tire slip angles for both laps.
    """
    dist = df.get("Distance", pd.Series(range(len(df))))

    result_a = _slip_for_suffix(df, "_Fast", dist)
    result_b = _slip_for_suffix(df, "_Slow", dist)

    if result_a is None and result_b is None:
        logger.debug("Sin canales suficientes para estimar slip angle")
        return {"available": False}

    out: dict = {
        "available":    True,
        "wheelbase_m":  WHEELBASE_M,
        "steer_ratio":  STEER_RATIO,
        "available_a":  result_a is not None,
        "available_b":  result_b is not None,
    }
    if result_a:
        out["summary_a"]      = result_a["summary"]
        out["per_distance_a"] = result_a["per_distance"]
    if result_b:
        out["summary_b"]      = result_b["summary"]
        out["per_distance_b"] = result_b["per_distance"]

    logger.info(
        "Slip angle: β_max_A=%.2f° β_max_B=%.2f°, "
        "US_A=%.1f%% OS_A=%.1f%%",
        out.get("summary_a", {}).get("beta_max", 0),
        out.get("summary_b", {}).get("beta_max", 0),
        out.get("summary_a", {}).get("understeer_pct", 0),
        out.get("summary_a", {}).get("oversteer_pct", 0),
    )
    return out
