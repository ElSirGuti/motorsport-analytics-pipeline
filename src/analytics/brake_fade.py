"""
Análisis de Brake Fade — eficiencia de frenado.

Cruza la presión del pedal (Brake) con la desaceleración longitudinal
(LongitudinalG negativo) para detectar zonas donde los frenos pierden eficacia.

Un driver que aplica la misma presión pero genera menos G en el freno al final
del stint tiene brake fade térmico.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BRAKE_THRESHOLD  = 15.0   # % — ignorar frenadas ligeras
DECEL_THRESHOLD  = 0.05   # g — mínima desaceleración para considerar zona de frenado
EFFICIENCY_FLOOR = 0.01   # evitar div/0
DOWNSAMPLE       = 5      # puntos cada N metros en la serie de salida
FADE_DROP        = 0.15   # caída relativa >15 % = brake fade significativo


def _efficiency_series(brake: pd.Series, lon_g: pd.Series) -> pd.Series:
    """
    efficiency = |deceleration_g| / brake_pressure_pct  (only where brake > threshold)
    Values outside braking zones are NaN.
    """
    eff = pd.Series(np.nan, index=brake.index)
    braking = (brake >= BRAKE_THRESHOLD) & (lon_g < -DECEL_THRESHOLD)
    denom = brake[braking].clip(lower=EFFICIENCY_FLOOR)
    eff[braking] = (-lon_g[braking]) / (denom / 100.0)
    return eff


def _fade_zones(distance: pd.Series, eff: pd.Series, baseline: float) -> list[dict]:
    """Detect contiguous zones where efficiency drops >FADE_DROP below baseline."""
    threshold = baseline * (1 - FADE_DROP)
    low = eff < threshold
    zones, in_zone, start = [], False, 0.0

    for i in range(len(low)):
        if low.iloc[i] and not in_zone:
            in_zone = True
            start   = float(distance.iloc[i])
        elif not low.iloc[i] and in_zone:
            in_zone = False
            zones.append({
                "start":    round(start, 0),
                "end":      round(float(distance.iloc[i - 1]), 0),
                "severity": round(float(1 - eff.iloc[i - 1] / max(baseline, EFFICIENCY_FLOOR)), 3),
            })
    if in_zone:
        zones.append({
            "start":    round(start, 0),
            "end":      round(float(distance.iloc[-1]), 0),
            "severity": round(float(1 - eff.iloc[-1] / max(baseline, EFFICIENCY_FLOOR)), 3),
        })
    return zones


def analizar_eficiencia_frenado(df: pd.DataFrame) -> dict:
    """
    Works on the aligned DataFrame (has Brake_Fast, LongitudinalG_Fast etc.).
    Returns per-distance efficiency for both laps, fade zones, and overall scores.
    """
    has_a = ("Brake_Fast" in df.columns) and ("LongitudinalG_Fast" in df.columns)
    has_b = ("Brake_Slow" in df.columns) and ("LongitudinalG_Slow" in df.columns)

    if not has_a and not has_b:
        logger.debug("Sin canales Brake/LongitudinalG para brake fade")
        return {"available": False}

    result: dict = {"available": True}
    dist = df["Distance"]

    per_dist: dict = {"distance": [round(float(d), 1) for d in dist.iloc[::DOWNSAMPLE]]}

    for label, bk, lon in [("a", "Brake_Fast", "LongitudinalG_Fast"),
                            ("b", "Brake_Slow", "LongitudinalG_Slow")]:
        if bk not in df.columns or lon not in df.columns:
            result[f"available_{label}"] = False
            continue
        result[f"available_{label}"] = True

        eff = _efficiency_series(
            pd.to_numeric(df[bk], errors="coerce").fillna(0),
            pd.to_numeric(df[lon], errors="coerce").fillna(0),
        )

        # Baseline: mean of the first third of the lap
        first_third = eff.iloc[:len(eff)//3].dropna()
        baseline = float(first_third.mean()) if len(first_third) > 0 else float(eff.dropna().mean() or 1.0)

        # Overall efficiency (mean of braking zones)
        mean_eff = float(eff.dropna().mean()) if eff.notna().any() else 0.0

        result[f"score_{label}"]    = round(mean_eff, 4)
        result[f"baseline_{label}"] = round(baseline, 4)
        result[f"fade_zones_{label}"] = _fade_zones(dist, eff.fillna(method="ffill").fillna(0), baseline)

        per_dist[f"efficiency_{label}"] = [
            round(float(eff.iloc[i]), 4) if not pd.isna(eff.iloc[i]) else None
            for i in range(0, len(eff), DOWNSAMPLE)
        ]

    result["per_distance"] = per_dist

    logger.info(
        "Brake fade: score_A=%.3f, score_B=%.3f, zonas_A=%d, zonas_B=%d",
        result.get("score_a", 0),
        result.get("score_b", 0),
        len(result.get("fade_zones_a", [])),
        len(result.get("fade_zones_b", [])),
    )
    return result
