import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def calcular_limites_dinamicos(
    df_aligned: pd.DataFrame,
    canal_lat: str = "LateralG",
    canal_long: str = "LongitudinalG",
) -> tuple[pd.DataFrame, float]:
    has_lat_fast = f"{canal_lat}_Fast" in df_aligned.columns
    has_lat_slow = f"{canal_lat}_Slow" in df_aligned.columns
    has_lon_fast = f"{canal_long}_Fast" in df_aligned.columns
    has_lon_slow = f"{canal_long}_Slow" in df_aligned.columns

    if not (has_lat_fast and has_lon_fast):
        logger.warning("Canales de fuerza G no disponibles. Omitiendo análisis dinámico.")
        return df_aligned, 0.0

    if has_lat_fast and has_lon_fast:
        g_lat = df_aligned[f"{canal_lat}_Fast"]
        g_lon = df_aligned[f"{canal_long}_Fast"]
        df_aligned["G_Sum_Fast"] = np.sqrt(g_lat**2 + g_lon**2)

    if has_lat_slow and has_lon_slow:
        g_lat = df_aligned[f"{canal_lat}_Slow"]
        g_lon = df_aligned[f"{canal_long}_Slow"]
        df_aligned["G_Sum_Slow"] = np.sqrt(g_lat**2 + g_lon**2)
    elif has_lat_fast and has_lon_fast:
        df_aligned["G_Sum_Slow"] = df_aligned["G_Sum_Fast"]

    g_max = df_aligned["G_Sum_Fast"].quantile(0.95)
    if g_max < 0.1:
        g_max = 1.0

    if "G_Sum_Fast" in df_aligned.columns:
        df_aligned["G_Efficiency_Fast"] = (df_aligned["G_Sum_Fast"] / g_max) * 100
    if "G_Sum_Slow" in df_aligned.columns:
        df_aligned["G_Efficiency_Slow"] = (df_aligned["G_Sum_Slow"] / g_max) * 100

    logger.info(f"Límite de adherencia (G_max p95): {g_max:.3f} G")
    return df_aligned, g_max


def _build_gg_points(
    df_aligned: pd.DataFrame,
    canal_lat: str = "LateralG",
    canal_long: str = "LongitudinalG",
) -> dict:
    gg = {"fast": [], "slow": []}
    for lap in ("Fast", "Slow"):
        lat_col = f"{canal_lat}_{lap}"
        lon_col = f"{canal_long}_{lap}"
        eff_col = f"G_Efficiency_{lap}"
        if lat_col not in df_aligned.columns or lon_col not in df_aligned.columns:
            continue
        subset = df_aligned[[lat_col, lon_col]].dropna()
        gg[lap.lower()] = [
            {
                "lat": round(float(row[lat_col]), 4),
                "lon": round(float(row[lon_col]), 4),
                "eff": round(float(row[eff_col]), 1) if eff_col in row else 0.0,
            }
            for _, row in subset.iterrows()
        ]
    return gg


def detectar_subviraje_sobreviraje(
    df_aligned: pd.DataFrame,
    apexes: pd.DataFrame,
    canal_lat: str = "LateralG",
    canal_steer: str = "SteerAngle",
    ventana_m: float = 60.0,
    umbral_sub: float = 0.15,
    umbral_over: float = 0.5,
) -> list[dict]:
    has_lat = f"{canal_lat}_Fast" in df_aligned.columns
    has_steer = f"{canal_steer}_Fast" in df_aligned.columns

    if not has_lat or not has_steer:
        logger.warning("Canales de steer o G-Lat no disponibles. Omitiendo detección de subviraje/sobreviraje.")
        return []

    eventos = []

    for idx, (_, apex) in enumerate(apexes.iterrows()):
        d_apex = apex["Distance"]
        ventana = df_aligned[
            (df_aligned["Distance"] >= d_apex - ventana_m)
            & (df_aligned["Distance"] <= d_apex + ventana_m * 0.5)
        ].copy()
        if len(ventana) < 5:
            continue

        steer = ventana[f"{canal_steer}_Fast"].values
        lat_g = ventana[f"{canal_lat}_Fast"].values
        dists = ventana["Distance"].values

        steer_smooth = pd.Series(steer).rolling(3, center=True, min_periods=1).mean().values
        lat_smooth = pd.Series(lat_g).rolling(3, center=True, min_periods=1).mean().values

        window_size = max(3, len(steer_smooth) // 4)
        d_steer = np.gradient(steer_smooth)
        d_lat = np.gradient(lat_smooth)

        # Understeer: steer increasing but lat G not following
        for i in range(window_size, len(steer_smooth) - window_size):
            if steer_smooth[i] < 3:
                continue
            steer_rising = d_steer[i] > 0.1
            lat_flat = abs(d_lat[i]) < umbral_sub * abs(steer_smooth[i])
            if steer_rising and lat_flat and d_apex - dists[i] > 0:
                eventos.append({
                    "tipo": "subviraje",
                    "curva": idx + 1,
                    "distancia": round(float(dists[i]), 1),
                    "steer_angle": round(float(steer_smooth[i]), 1),
                    "lat_g": round(float(lat_smooth[i]), 3),
                    "severidad": "media",
                    "diagnostico": f"Subviraje en entrada de curva {idx+1}: "
                                   f"el volante sigue girando ({steer_smooth[i]:.1f}°) "
                                   f"pero el G lateral no aumenta ({lat_smooth[i]:.2f}G). "
                                   f"Falta rotación del tren delantero.",
                })
                break

        # Oversteer: sudden lat G spike + steer correction
        for i in range(window_size, len(lat_smooth) - window_size):
            if abs(lat_smooth[i]) < 0.3:
                continue
            lat_jerk = abs(lat_smooth[i + 1] - lat_smooth[i - 1])
            steer_correction = False
            if i > 0 and i < len(steer_smooth) - 1:
                before = abs(steer_smooth[i - 1])
                after = abs(steer_smooth[i + 1])
                steer_correction = after < before * 0.7 or after > before * 1.3
            if lat_jerk > umbral_over and steer_correction:
                eventos.append({
                    "tipo": "sobreviraje",
                    "curva": idx + 1,
                    "distancia": round(float(dists[i]), 1),
                    "lat_g": round(float(lat_smooth[i]), 3),
                    "jerkyness": round(float(lat_jerk), 3),
                    "severidad": "alta" if lat_jerk > umbral_over * 1.5 else "media",
                    "diagnostico": f"Sobreviraje en curva {idx+1} a {dists[i]:.0f}m: "
                                   f"pico de G lateral ({lat_smooth[i]:.2f}G) "
                                   f"con corrección de volante. "
                                   f"Pérdida de agarre trasero.",
                })
                break

    logger.info(f"Eventos de dinámica: {len([e for e in eventos if e['tipo']=='subviraje'])} subviraje, "
                f"{len([e for e in eventos if e['tipo']=='sobreviraje'])} sobreviraje")
    return eventos
