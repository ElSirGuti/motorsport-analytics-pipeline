"""
Análisis térmico de neumáticos.

Calcula el gradiente térmico (ΔT = superficie − núcleo), detecta violaciones
de la ventana óptima de temperatura y genera mapas de calor por vuelta.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CORNERS = ["FL", "FR", "RL", "RR"]
CORNER_LABELS = {"FL": "Delantero Izq.", "FR": "Delantero Der.",
                 "RL": "Trasero Izq.",   "RR": "Trasero Der."}
ZONES   = ["Inner", "Middle", "Outer"]
DOWNSAMPLE = 10   # 1 punto cada N metros para las series de distancia


def _surface_mean(df: pd.DataFrame, corner: str, suffix: str = "") -> pd.Series | None:
    """Average of Inner/Middle/Outer for one corner, with optional _Fast/_Slow suffix."""
    cols = []
    for z in ZONES:
        c = f"TyreTemp{z}{corner}{suffix}"
        if c in df.columns:
            cols.append(c)
    if not cols:
        return None
    return df[cols].mean(axis=1)


def _core_series(df: pd.DataFrame, corner: str, suffix: str = "") -> pd.Series | None:
    c = f"TyreTemp Core{corner}{suffix}"
    if c in df.columns:
        return df[c]
    return None


def _window_status(temp: float, t_min: float, t_max: float) -> str:
    if temp < t_min - 15:
        return "fria"
    if temp < t_min:
        return "suboptima"
    if temp <= t_max:
        return "optima"
    if temp <= t_max + 15:
        return "caliente"
    return "sobrecalentada"


def _corner_stats(df: pd.DataFrame, corner: str, suffix: str,
                  t_min: float, t_max: float) -> dict | None:
    surf = _surface_mean(df, corner, suffix)
    core = _core_series(df, corner, suffix)
    if surf is None and core is None:
        return None

    result: dict = {"corner": corner, "label": CORNER_LABELS[corner]}

    for z in ZONES:
        c = f"TyreTemp{z}{corner}{suffix}"
        result[z.lower()] = round(float(df[c].mean()), 1) if c in df.columns else None

    result["surface_mean"] = round(float(surf.mean()), 1) if surf is not None else None
    result["core_mean"]    = round(float(core.mean()), 1) if core is not None else None

    if surf is not None and core is not None:
        delta = surf - core
        result["delta_t_mean"] = round(float(delta.mean()), 2)
        result["delta_t_max"]  = round(float(delta.max()),  2)
        # thermal stress zones: ΔT > 20°C is concerning
        stress_mask = delta > 20
        result["high_stress_pct"] = round(float(stress_mask.mean()) * 100, 1)
    else:
        result["delta_t_mean"] = None
        result["delta_t_max"]  = None
        result["high_stress_pct"] = 0.0

    ref_temp = result["surface_mean"] if result["surface_mean"] is not None else result["core_mean"]
    result["window_status"]    = _window_status(ref_temp, t_min, t_max) if ref_temp else "desconocida"
    result["window_deviation"] = (
        round(float(ref_temp - t_max), 1) if ref_temp and ref_temp > t_max
        else round(float(t_min - ref_temp), 1) if ref_temp and ref_temp < t_min
        else 0.0
    )
    return result


def analizar_neumaticos(
    df: pd.DataFrame,
    suffix: str = "",
    t_min: float = 80.0,
    t_max: float = 100.0,
) -> dict:
    """
    Analyzes tire temperatures for one lap (suffix="" for raw df,
    or "_Fast" / "_Slow" for aligned df).

    Returns summary per corner + downsampled per-distance series.
    """
    corners_out = []
    any_data = False

    for corner in CORNERS:
        stats = _corner_stats(df, corner, suffix, t_min, t_max)
        if stats:
            any_data = True
            corners_out.append(stats)

    if not any_data:
        logger.debug("Sin canales de temperatura de neumáticos (suffix='%s')", suffix)
        return {"available": False}

    # Per-distance series (downsampled)
    dist_col = "Distance"
    per_dist: dict = {}

    if dist_col in df.columns:
        step = DOWNSAMPLE
        idx  = range(0, len(df), step)
        per_dist["distance"] = [round(float(df[dist_col].iloc[i]), 1) for i in idx]

        for corner in CORNERS:
            surf = _surface_mean(df, corner, suffix)
            core = _core_series(df, corner, suffix)
            if surf is not None:
                per_dist[f"{corner}_surface"] = [round(float(surf.iloc[i]), 1) for i in idx]
            if core is not None:
                per_dist[f"{corner}_core"]    = [round(float(core.iloc[i]), 1) for i in idx]
                if surf is not None:
                    delta = surf - core
                    per_dist[f"{corner}_delta"] = [round(float(delta.iloc[i]), 2) for i in idx]

    logger.info(
        "Análisis térmico: %d neumáticos, ventana %d–%d°C",
        len(corners_out), t_min, t_max,
    )
    return {
        "available": True,
        "t_min":    t_min,
        "t_max":    t_max,
        "corners":  corners_out,
        "per_distance": per_dist,
    }


def analizar_neumaticos_comparativo(
    df_adv: pd.DataFrame,
    t_min: float = 80.0,
    t_max: float = 100.0,
) -> dict:
    """
    Runs thermal analysis on both laps from the already-aligned DataFrame
    (uses _Fast / _Slow suffixes).
    """
    result_a = analizar_neumaticos(df_adv, suffix="_Fast", t_min=t_min, t_max=t_max)
    result_b = analizar_neumaticos(df_adv, suffix="_Slow", t_min=t_min, t_max=t_max)

    if not result_a["available"] and not result_b["available"]:
        return {"available": False}

    return {
        "available": True,
        "t_min": t_min,
        "t_max": t_max,
        "lap_a": result_a,
        "lap_b": result_b,
    }
