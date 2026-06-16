import logging
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from src.i18n import _ as t

logger = logging.getLogger(__name__)


def calcular_g_desde_cinematica(
    df_aligned: pd.DataFrame,
    df_geo: pd.DataFrame,
    canal_speed: str = "Speed",
) -> pd.DataFrame:
    """
    Estima LateralG y LongitudinalG desde cinemática cuando el CSV no tiene sensores de G.

    - LongitudinalG = (dv/ds) × v / 9.81        (derivada de velocidad × velocidad)
    - LateralG      = v² × κ / 9.81              (curvatura de pista × velocidad²)

    Requiere que df_geo tenga columnas 'Distance' y 'Curvature'.
    df_aligned debe estar en pasos de distancia uniformes (1 m).
    """
    if "Distance" not in df_geo.columns or "Curvature" not in df_geo.columns:
        logger.warning("df_geo no tiene Distance/Curvature — no se puede calcular G cinemático.")
        return df_aligned

    dist_geo = df_geo["Distance"].values
    kappa_geo = np.abs(df_geo["Curvature"].values)
    dist_aligned = df_aligned["Distance"].values

    # Interpolar curvatura sobre el eje de distancia alineado
    f_kappa = interp1d(
        dist_geo, kappa_geo,
        kind="linear", bounds_error=False, fill_value=0.0,
    )
    kappa = f_kappa(dist_aligned)

    for lap in ("Fast", "Slow"):
        speed_col = f"{canal_speed}_{lap}"
        if speed_col not in df_aligned.columns:
            continue

        speed_ms = df_aligned[speed_col].fillna(0).values / 3.6  # km/h → m/s
        speed_ms = np.clip(speed_ms, 0.5, None)                  # evitar /0

        # LongitudinalG: a_lon = (dv/ds) × v  [chain rule: dv/dt = (dv/ds)*(ds/dt) = (dv/ds)*v]
        dv_ds = np.gradient(speed_ms, 1.0)          # m/s por metro
        lon_acc = dv_ds * speed_ms                  # m/s²
        df_aligned[f"LongitudinalG_{lap}"] = np.round(lon_acc / 9.81, 4)

        # LateralG: a_lat = v² × κ
        lat_acc = speed_ms**2 * kappa               # m/s²
        df_aligned[f"LateralG_{lap}"] = np.round(lat_acc / 9.81, 4)

    logger.info("  ✓ G cinemático calculado (LateralG = v²κ, LongitudinalG = v·dv/ds)")
    return df_aligned


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
        g_cols = [c for c in df_aligned.columns if any(k in c.lower() for k in ("lat", "lon", "g_", "_g", "accel", "force"))]
        logger.warning(
            f"Canales de fuerza G no disponibles. "
            f"Buscando '{canal_lat}_Fast' y '{canal_long}_Fast'. "
            f"Columnas con 'g/lat/lon/accel' disponibles: {g_cols or '(ninguna)'}"
        )
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
    max_points: int = 500,
) -> dict:
    gg = {"fast": [], "slow": []}
    for lap in ("Fast", "Slow"):
        lat_col = f"{canal_lat}_{lap}"
        lon_col = f"{canal_long}_{lap}"
        eff_col = f"G_Efficiency_{lap}"
        if lat_col not in df_aligned.columns or lon_col not in df_aligned.columns:
            continue

        cols = [lat_col, lon_col] + ([eff_col] if eff_col in df_aligned.columns else [])
        subset = df_aligned[cols].dropna(subset=[lat_col, lon_col])

        if len(subset) > max_points:
            subset = subset.iloc[:: len(subset) // max_points]

        lats = subset[lat_col].round(4).tolist()
        lons = subset[lon_col].round(4).tolist()
        effs = subset[eff_col].round(1).tolist() if eff_col in subset.columns else [0.0] * len(lats)

        gg[lap.lower()] = [
            {"lat": lat, "lon": lon, "eff": eff}
            for lat, lon, eff in zip(lats, lons, effs)
        ]
    return gg


def _sev_subviraje(d_steer: float, steer_angle: float, lang: str = "es") -> str:
    if d_steer >= 0.6 or steer_angle > 15:
        return t("sev_critico", lang=lang)
    if d_steer >= 0.3 or steer_angle > 8:
        return t("sev_media", lang=lang)
    return t("sev_leve", lang=lang)


def _diag_subviraje(sev: str, curva: int, steer: float, lat_g: float, lang: str = "es") -> str:
    base = t("dyn_base_subviraje", lang=lang, curva=curva, steer=f"{steer:.1f}", lat_g=f"{lat_g:.2f}")
    if sev == "critico":
        return t("dyn_subviraje_critico", lang=lang, base=base)
    if sev == "media":
        return t("dyn_subviraje_media", lang=lang, base=base)
    return t("dyn_subviraje_leve", lang=lang, base=base)


def _sev_sobreviraje(lat_jerk: float, umbral: float, lang: str = "es") -> str:
    if lat_jerk >= umbral * 2.5:
        return t("sev_critico", lang=lang)
    if lat_jerk >= umbral * 1.5:
        return t("sev_media", lang=lang)
    return t("sev_leve", lang=lang)


def _diag_sobreviraje(sev: str, curva: int, dist: float, lat_g: float, lang: str = "es") -> str:
    base = t("dyn_base_sobreviraje", lang=lang, curva=curva, dist=f"{dist:.0f}", lat_g=f"{lat_g:.2f}")
    if sev == "critico":
        return t("dyn_sobreviraje_critico", lang=lang, base=base)
    if sev == "media":
        return t("dyn_sobreviraje_media", lang=lang, base=base)
    return t("dyn_sobreviraje_leve", lang=lang, base=base)


def detectar_subviraje_sobreviraje(
    df_aligned: pd.DataFrame,
    apexes: pd.DataFrame,
    canal_lat: str = "LateralG",
    canal_steer: str = "SteerAngle",
    ventana_m: float = 60.0,
    umbral_sub: float = 0.15,
    umbral_over: float = 0.5,
    lang: str = "es",
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
                sev = _sev_subviraje(d_steer[i], steer_smooth[i], lang=lang)
                eventos.append({
                    "tipo": t("tipo_subviraje", lang=lang),
                    "curva": idx + 1,
                    "distancia": round(float(dists[i]), 1),
                    "steer_angle": round(float(steer_smooth[i]), 1),
                    "lat_g": round(float(lat_smooth[i]), 3),
                    "severidad": sev,
                    "diagnostico": _diag_subviraje(sev, idx + 1, steer_smooth[i], lat_smooth[i], lang=lang),
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
                sev = _sev_sobreviraje(lat_jerk, umbral_over, lang=lang)
                eventos.append({
                    "tipo": t("tipo_sobreviraje", lang=lang),
                    "curva": idx + 1,
                    "distancia": round(float(dists[i]), 1),
                    "lat_g": round(float(lat_smooth[i]), 3),
                    "jerkyness": round(float(lat_jerk), 3),
                    "severidad": sev,
                    "diagnostico": _diag_sobreviraje(sev, idx + 1, dists[i], lat_smooth[i], lang=lang),
                })
                break

    n_sub = len([e for e in eventos if e['tipo'] == t("tipo_subviraje", lang=lang)])
    n_over = len([e for e in eventos if e['tipo'] == t("tipo_sobreviraje", lang=lang)])
    logger.info(t("dyn_log_summary", lang=lang, n_sub=n_sub, n_over=n_over))
    return eventos
