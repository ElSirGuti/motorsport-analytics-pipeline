"""
Análisis de Frecuencia de Inputs del Piloto.

Aplica FFT y rolling-std sobre el canal SteerAngle para medir el
"nerviosismo" del piloto: micro-correcciones de alta frecuencia indican
falta de confianza en el agarre o fatiga.

También detecta solapamiento freno-gas (threshold > 0) como indicador
de estilo de conducción en la transición frenado→aceleración.
"""

import logging
import numpy as np
import pandas as pd
from scipy.signal import welch

logger = logging.getLogger(__name__)

DOWNSAMPLE      = 5      # reducción para series de distancia
ROLLING_WIN     = 80     # ventana rolling en muestras (~80 m a 1m/sample)
STEER_THRESHOLD = 1.0    # ° — ignorar micro-ruido por debajo de este valor


# ── Nervousness via rolling std of steer rate ─────────────────────────────────

def _nervousness_series(steer: pd.Series) -> pd.Series:
    """
    Rolling std of steer rate (first diff). Proxy for high-freq content.
    Normalised to [0, 1] by the per-lap 99th percentile to make values comparable.
    """
    rate = steer.diff().abs().fillna(0)
    smoothed = rate.rolling(ROLLING_WIN, center=True, min_periods=1).mean()
    p99 = float(smoothed.quantile(0.99))
    if p99 < 1e-6:
        return pd.Series(0.0, index=steer.index)
    return (smoothed / p99).clip(0, 1)


# ── FFT frequency-band analysis ───────────────────────────────────────────────

def _fft_bands(steer: pd.Series, sample_rate_hz: float = 10.0) -> dict:
    """
    Uses Welch PSD to compute power in three bands.
    Assumes the steer series is sampled at roughly sample_rate_hz.
    (The aligned df is at 1 m/sample; at ~50 km/h avg that's ~14 Hz,
    so we use the physical time via Speed if available, or assume 10 Hz.)
    """
    if len(steer) < 64:
        return {"low": 0.0, "mid": 0.0, "high": 0.0}
    try:
        s = steer.fillna(method="ffill").fillna(0).values
        freqs, psd = welch(s, fs=sample_rate_hz, nperseg=min(256, len(s) // 2))
        total = float(np.trapz(psd, freqs)) or 1.0
        low  = float(np.trapz(psd[freqs < 0.5],  freqs[freqs < 0.5]))  / total
        mid  = float(np.trapz(psd[(freqs >= 0.5) & (freqs < 2.0)],
                               freqs[(freqs >= 0.5) & (freqs < 2.0)])) / total
        high = float(np.trapz(psd[freqs >= 2.0],  freqs[freqs >= 2.0])) / total
        return {
            "low":  round(low,  3),
            "mid":  round(mid,  3),
            "high": round(high, 3),
        }
    except Exception as exc:
        logger.debug("FFT error: %s", exc)
        return {"low": 0.0, "mid": 0.0, "high": 0.0}


def _nervousness_label(score: float, high_band: float) -> str:
    if score < 0.15 and high_band < 0.15:
        return "Muy suave"
    if score < 0.30 and high_band < 0.25:
        return "Suave"
    if score < 0.50 and high_band < 0.40:
        return "Normal"
    if score < 0.70 or high_band < 0.55:
        return "Activo"
    return "Nervioso"


# ── Throttle-brake overlap ─────────────────────────────────────────────────────

def _overlap_pct(brake: pd.Series, throttle: pd.Series,
                 brake_thr: float = 5.0, thr_thr: float = 5.0) -> float:
    """Percentage of samples where both Brake > threshold and Throttle > threshold."""
    overlap = (brake > brake_thr) & (throttle > thr_thr)
    return round(float(overlap.mean()) * 100, 2)


# ── Main entry ────────────────────────────────────────────────────────────────

def analizar_inputs_piloto(df: pd.DataFrame) -> dict:
    """
    Analyses steering frequency and input quality for both laps.
    Expects aligned df with SteerAngle_Fast / SteerAngle_Slow columns.
    """
    has_a = "SteerAngle_Fast" in df.columns
    has_b = "SteerAngle_Slow" in df.columns

    if not has_a and not has_b:
        logger.debug("SteerAngle no disponible para análisis de inputs")
        return {"available": False}

    result: dict = {"available": True}
    dist = df["Distance"]
    per_dist: dict = {"distance": [round(float(d), 1) for d in dist.iloc[::DOWNSAMPLE]]}

    # Estimate effective sample rate from speed (if available)
    sample_rate = 10.0
    if "Speed_Fast" in df.columns:
        avg_speed_ms = float(df["Speed_Fast"].mean()) / 3.6
        if avg_speed_ms > 1:
            sample_rate = avg_speed_ms   # roughly Hz (1 m steps)

    for label, steer_col, brake_col, thr_col in [
        ("a", "SteerAngle_Fast", "Brake_Fast",   "Throttle_Fast"),
        ("b", "SteerAngle_Slow", "Brake_Slow",   "Throttle_Slow"),
    ]:
        if steer_col not in df.columns:
            result[f"available_{label}"] = False
            continue
        result[f"available_{label}"] = True

        steer = pd.to_numeric(df[steer_col], errors="coerce").fillna(0)

        nerv = _nervousness_series(steer)
        bands = _fft_bands(steer, sample_rate)
        overall = round(float(nerv.mean()), 4)

        result[f"nervousness_score_{label}"] = overall
        result[f"fft_bands_{label}"]         = bands
        result[f"nervousness_label_{label}"] = _nervousness_label(overall, bands["high"])

        if brake_col in df.columns and thr_col in df.columns:
            result[f"overlap_pct_{label}"] = _overlap_pct(
                pd.to_numeric(df[brake_col],  errors="coerce").fillna(0),
                pd.to_numeric(df[thr_col],    errors="coerce").fillna(0),
            )

        per_dist[f"nervousness_{label}"] = [
            round(float(nerv.iloc[i]), 4) for i in range(0, len(nerv), DOWNSAMPLE)
        ]

    result["per_distance"] = per_dist

    logger.info(
        "Inputs piloto: nerviosismo A=%.3f (%s), B=%.3f (%s)",
        result.get("nervousness_score_a", 0), result.get("nervousness_label_a", "—"),
        result.get("nervousness_score_b", 0), result.get("nervousness_label_b", "—"),
    )
    return result
