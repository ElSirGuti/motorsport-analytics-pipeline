"""
Análisis de Suspensión — pitch, roll y detección de fondo.

Usa SuspTravelFL/FR/RL/RR para calcular:
- Roll del chasis: diferencia L-R del eje delantero (y trasero)
- Pitch del chasis: diferencia delantera-trasera del promedio izquierdo-derecho
- Bottoming events: cuando el viaje supera el 90 % del recorrido máximo disponible

Convención de signo: roll positivo = carga a la derecha (paso por curva a izquierda).
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DOWNSAMPLE      = 5      # puntos cada N metros en la serie de salida
BOTTOM_FRACTION = 0.90   # fracción del rango observado → bottoming threshold
MIN_DURATION_M  = 3.0    # mínima duración (metros) de un evento de fondo


def _roll(fl: pd.Series, fr: pd.Series) -> pd.Series:
    """Roll en mm: (FR - FL). Positivo = más compresión a la derecha."""
    return fr - fl


def _pitch(front_avg: pd.Series, rear_avg: pd.Series) -> pd.Series:
    """Pitch en mm: (front_avg - rear_avg). Positivo = morro bajo (frenada)."""
    return front_avg - rear_avg


def _bottoming_events(distance: pd.Series, travel: pd.Series,
                      corner_label: str) -> list[dict]:
    """
    Detect contiguous zones where travel >= BOTTOM_FRACTION of observed max.
    Returns list of {corner, start_m, end_m, max_travel, severity}.
    """
    max_t = float(travel.max())
    if max_t < 1.0:
        return []
    threshold = max_t * BOTTOM_FRACTION
    bottoming = travel >= threshold
    events, in_ev, start_idx = [], False, 0

    for i in range(len(bottoming)):
        if bottoming.iloc[i] and not in_ev:
            in_ev, start_idx = True, i
        elif not bottoming.iloc[i] and in_ev:
            in_ev = False
            start_m = float(distance.iloc[start_idx])
            end_m   = float(distance.iloc[i - 1])
            if end_m - start_m >= MIN_DURATION_M:
                seg_max = float(travel.iloc[start_idx:i].max())
                events.append({
                    "corner":     corner_label,
                    "start_m":    round(start_m, 0),
                    "end_m":      round(end_m, 0),
                    "max_travel": round(seg_max, 1),
                    "severity":   round(seg_max / max_t, 3),
                })
    if in_ev:
        start_m = float(distance.iloc[start_idx])
        end_m   = float(distance.iloc[-1])
        if end_m - start_m >= MIN_DURATION_M:
            seg_max = float(travel.iloc[start_idx:].max())
            events.append({
                "corner":     corner_label,
                "start_m":    round(start_m, 0),
                "end_m":      round(end_m, 0),
                "max_travel": round(seg_max, 1),
                "severity":   round(seg_max / max_t, 3),
            })
    return events


def _suspension_for_suffix(df: pd.DataFrame, suffix: str, dist: pd.Series) -> dict | None:
    """
    Compute suspension metrics for one lap (suffix = "_Fast" or "_Slow").
    Returns None if no channels found.
    """
    fl_col, fr_col = f"SuspTravelFL{suffix}", f"SuspTravelFR{suffix}"
    rl_col, rr_col = f"SuspTravelRL{suffix}", f"SuspTravelRR{suffix}"

    available_cols = [c for c in [fl_col, fr_col, rl_col, rr_col] if c in df.columns]
    if not available_cols:
        return None

    fl = pd.to_numeric(df[fl_col], errors="coerce").fillna(0) if fl_col in df.columns else pd.Series(0, index=df.index)
    fr = pd.to_numeric(df[fr_col], errors="coerce").fillna(0) if fr_col in df.columns else pd.Series(0, index=df.index)
    rl = pd.to_numeric(df[rl_col], errors="coerce").fillna(0) if rl_col in df.columns else pd.Series(0, index=df.index)
    rr = pd.to_numeric(df[rr_col], errors="coerce").fillna(0) if rr_col in df.columns else pd.Series(0, index=df.index)

    front_avg = (fl + fr) / 2
    rear_avg  = (rl + rr) / 2
    roll_f    = _roll(fl, fr)
    roll_r    = _roll(rl, rr)
    pitch_s   = _pitch(front_avg, rear_avg)

    idx = range(0, len(dist), DOWNSAMPLE)

    per_dist: dict = {
        "distance": [round(float(dist.iloc[i]), 1) for i in idx],
        "roll_f":   [round(float(roll_f.iloc[i]), 2) for i in idx],
        "roll_r":   [round(float(roll_r.iloc[i]), 2) for i in idx],
        "pitch":    [round(float(pitch_s.iloc[i]), 2) for i in idx],
    }
    for label, series in [("fl", fl), ("fr", fr), ("rl", rl), ("rr", rr)]:
        per_dist[label] = [round(float(series.iloc[i]), 2) for i in idx]

    # Bottoming events
    bottoming = []
    for label, col, series in [
        ("FL", fl_col, fl), ("FR", fr_col, fr),
        ("RL", rl_col, rl), ("RR", rr_col, rr),
    ]:
        if col in df.columns:
            bottoming.extend(_bottoming_events(dist, series, label))

    # Summary statistics
    summary = {
        "max_roll_f":  round(float(roll_f.abs().max()), 2),
        "max_roll_r":  round(float(roll_r.abs().max()), 2),
        "max_pitch":   round(float(pitch_s.abs().max()), 2),
        "mean_roll_f": round(float(roll_f.abs().mean()), 2),
        "mean_pitch":  round(float(pitch_s.abs().mean()), 2),
        "bottoming_events": len(bottoming),
    }

    return {"summary": summary, "per_distance": per_dist, "bottoming": bottoming}


def analizar_suspension(df: pd.DataFrame) -> dict:
    """
    Works on the aligned DataFrame (SuspTravelFL_Fast, SuspTravelFL_Slow, etc.).
    Returns per-distance pitch/roll series and bottoming events for both laps.
    """
    dist = df.get("Distance", pd.Series(range(len(df))))

    result_a = _suspension_for_suffix(df, "_Fast", dist)
    result_b = _suspension_for_suffix(df, "_Slow", dist)

    if result_a is None and result_b is None:
        logger.debug("Sin canales SuspTravel para análisis de suspensión")
        return {"available": False}

    out: dict = {"available": True}
    if result_a is not None:
        out["available_a"] = True
        out["summary_a"]   = result_a["summary"]
        out["bottoming_a"] = result_a["bottoming"]
        out["per_distance_a"] = result_a["per_distance"]
    else:
        out["available_a"] = False

    if result_b is not None:
        out["available_b"] = True
        out["summary_b"]   = result_b["summary"]
        out["bottoming_b"] = result_b["bottoming"]
        out["per_distance_b"] = result_b["per_distance"]
    else:
        out["available_b"] = False

    total_bottom = len(out.get("bottoming_a", [])) + len(out.get("bottoming_b", []))
    logger.info(
        "Suspensión: eventos de fondo totales=%d (A=%d, B=%d)",
        total_bottom,
        len(out.get("bottoming_a", [])),
        len(out.get("bottoming_b", [])),
    )
    return out
