"""
Detección de Anomalías Multivariable — Isolation Forest

Entrena el modelo en la vuelta rápida (referencia limpia) y calcula el
"reconstruction error" por metro en la vuelta lenta. Las zonas donde el
score se dispara son señaladas automáticamente como errores de conducción.
"""
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Canales que componen el vector de estado del carro
ML_FEATURES = ["Speed", "Brake", "Throttle", "SteerAngle", "LateralG", "LongitudinalG"]
MAX_SCORE_POINTS = 500
ANOMALY_THRESHOLD = 0.60
MIN_ZONE_METERS = 15.0


def detectar_anomalias(
    df_aligned: pd.DataFrame,
    contamination: float = 0.10,
) -> dict:
    """
    Entrena IsolationForest sobre la vuelta rápida y detecta zonas anómalas en la lenta.

    Returns:
        {
            "scores_fast": [{"distance": float, "score": float}],
            "scores_slow": [{"distance": float, "score": float}],
            "zones":       [{"start_m", "end_m", "severity", "avg_score", "descripcion"}]
        }
    """
    fast_cols = [f"{f}_Fast" for f in ML_FEATURES if f"{f}_Fast" in df_aligned.columns]
    slow_cols = [f"{f}_Slow" for f in ML_FEATURES if f"{f}_Slow" in df_aligned.columns]

    if len(fast_cols) < 2:
        logger.warning("IsolationForest: menos de 2 features disponibles — omitiendo.")
        return {"scores_fast": [], "scores_slow": [], "zones": []}

    distances = df_aligned["Distance"].values

    # ── Matrices de features ──────────────────────────────────────────────────
    X_fast = df_aligned[fast_cols].fillna(method="ffill").fillna(0).values

    shared_features = [f for f in ML_FEATURES if f"{f}_Fast" in df_aligned.columns and f"{f}_Slow" in df_aligned.columns]
    slow_cols_ordered = [f"{f}_Slow" for f in shared_features]
    X_slow = df_aligned[slow_cols_ordered].fillna(method="ffill").fillna(0).values if slow_cols_ordered else X_fast

    # ── Escalado ──────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_fast_sc = scaler.fit_transform(X_fast)
    X_slow_sc = scaler.transform(X_slow) if slow_cols_ordered else X_fast_sc

    # ── Entrenamiento (solo vuelta rápida) ────────────────────────────────────
    model = IsolationForest(
        n_estimators=120,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_fast_sc)

    # decision_function: valores altos = normal, bajos = anomalía
    raw_fast = model.decision_function(X_fast_sc)
    raw_slow = model.decision_function(X_slow_sc)

    # Normalizar a [0, 1] donde 1 = más anómalo
    def _normalize(arr: np.ndarray) -> np.ndarray:
        mn, mx = arr.min(), arr.max()
        return np.clip((mx - arr) / (mx - mn + 1e-9), 0, 1)

    score_fast = _normalize(raw_fast)
    score_slow = _normalize(raw_slow)

    # Suavizado (ventana 5 muestras)
    score_fast = pd.Series(score_fast).rolling(5, center=True, min_periods=1).mean().values
    score_slow = pd.Series(score_slow).rolling(5, center=True, min_periods=1).mean().values

    # ── Detección de zonas continuas ──────────────────────────────────────────
    zones = _extraer_zonas(distances, score_slow)

    # ── Downsample para frontend ──────────────────────────────────────────────
    step = max(1, len(distances) // MAX_SCORE_POINTS)

    def _to_list(dist_arr, score_arr):
        return [
            {"distance": round(float(d), 1), "score": round(float(s), 4)}
            for d, s in zip(dist_arr[::step], score_arr[::step])
        ]

    logger.info(f"IsolationForest: {len(zones)} zonas anómalas | features: {fast_cols}")
    return {
        "scores_fast": _to_list(distances, score_fast),
        "scores_slow": _to_list(distances, score_slow),
        "zones": zones,
    }


def _extraer_zonas(distances: np.ndarray, scores: np.ndarray) -> list[dict]:
    zones = []
    in_zone = False
    start_d = 0.0
    zone_scores: list[float] = []

    for d, s in zip(distances, scores):
        if s > ANOMALY_THRESHOLD:
            if not in_zone:
                in_zone = True
                start_d = float(d)
                zone_scores = []
            zone_scores.append(float(s))
        else:
            if in_zone:
                end_d = float(d)
                if end_d - start_d >= MIN_ZONE_METERS:
                    zones.append(_build_zone(start_d, end_d, zone_scores))
                in_zone = False
                zone_scores = []

    if in_zone and zone_scores:
        end_d = float(distances[-1])
        if end_d - start_d >= MIN_ZONE_METERS:
            zones.append(_build_zone(start_d, end_d, zone_scores))

    return zones


def _build_zone(start_m: float, end_m: float, scores: list[float]) -> dict:
    avg = float(np.mean(scores))
    peak = float(np.max(scores))

    if avg > 0.82:
        sev = "critico"
        desc = (f"Error crítico de ejecución entre {start_m:.0f}m y {end_m:.0f}m. "
                f"El modelo detecta desviaciones severas en múltiples canales simultáneos. "
                f"Revisar trazada, punto de frenada y dinámica del carro.")
    elif avg > 0.68:
        sev = "media"
        desc = (f"Anomalía moderada entre {start_m:.0f}m y {end_m:.0f}m. "
                f"La combinación de velocidad, pedales y volante difiere de la ejecución de referencia. "
                f"Posible sobrecalentamiento de neumáticos o error de línea.")
    else:
        sev = "leve"
        desc = (f"Desviación leve entre {start_m:.0f}m y {end_m:.0f}m. "
                f"El perfil de conducción se separa marginalmente de la vuelta óptima.")

    return {
        "start_m": round(start_m, 1),
        "end_m": round(end_m, 1),
        "length_m": round(end_m - start_m, 1),
        "avg_score": round(avg, 3),
        "peak_score": round(peak, 3),
        "severity": sev,
        "descripcion": desc,
    }
