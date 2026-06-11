"""
Predicción de Tiempo de Vuelta Potencial — 3 Capas

Capa 1 — Reachable Lap (inmediata):
  Percentil-10 por curva desde el historial SQLite.
  "En el 10% de tus mejores intentos en esta curva, lograste X."
  Más honesta que el mínimo absoluto (que puede ser ruido).

Capa 2 — Consistency Score (con ≥3 obs por curva):
  consistency = 1 - std(time_loss) / |mean(time_loss)|
  Mide qué tan repetible es el piloto curva por curva.
  Un score bajo = el piloto sabe cómo hacerlo pero no consistentemente.

Capa 3 — XGBoost + Explicaciones (con ≥30 obs totales):
  Predice el tiempo óptimo dado el perfil de ejecución actual.
  Devuelve las top-2 features que más alejan al piloto del perfil rápido.
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "laptime_history.db"
MIN_SAMPLES_FOR_ML = 30

HISTORY_FEATURES = [
    "venue", "vehicle", "corner_number", "track_length_m",
    "entry_speed_kmh", "apex_speed_kmh", "exit_throttle_pct",
    "braking_delta_m", "throttle_delta_m", "g_efficiency_pct",
    "steer_variance", "curvature_radius_m",
    "time_loss_s",
]

FEATURE_COLS = [
    "entry_speed_kmh", "apex_speed_kmh", "exit_throttle_pct",
    "braking_delta_m", "throttle_delta_m", "g_efficiency_pct",
    "steer_variance", "curvature_radius_m",
]

# (label_ui, unit, sign): sign=-1 → higher=better, sign=+1 → lower=better, None → skip
FEATURE_META = {
    "entry_speed_kmh":    ("V. entrada",   "km/h",  -1),
    "apex_speed_kmh":     ("V. apex",      "km/h",  -1),
    "exit_throttle_pct":  ("Gas salida",   "%",     -1),
    "braking_delta_m":    ("Frenada",      "m",     -1),
    "throttle_delta_m":   ("Gas delta",    "m",     +1),
    "g_efficiency_pct":   ("Efic. G",      "%",     -1),
    "steer_variance":     ("Var. volante", "",      +1),
    "curvature_radius_m": None,
}

STATUS_THRESHOLDS = [
    (0.05,         "consistente"),
    (0.25,         "optimizable"),
    (float("inf"), "critico"),
]


def _status(gap_s: float) -> str:
    for threshold, label in STATUS_THRESHOLDS:
        if gap_s < threshold:
            return label
    return "critico"


# ── Capa 1 + 2: Historial por curva ──────────────────────────────────────────

def _get_hist_by_corner(corners: list[dict], metadata: dict) -> dict:
    """
    Carga del SQLite el historial de time_loss_s por corner_number (filtrado por venue).

    Returns:
        {corner_number: {p10, p25, mean, std, consistency_pct, n_samples}}
    """
    if not DB_PATH.exists():
        return {}
    venue = metadata.get("venue") or ""
    if not venue:
        return {}

    corner_numbers = [c.get("corner_number") for c in corners if c.get("corner_number")]
    if not corner_numbers:
        return {}

    conn = sqlite3.connect(str(DB_PATH))
    try:
        placeholders = ",".join("?" * len(corner_numbers))
        df = pd.read_sql(
            f"SELECT * FROM lap_history WHERE venue=? AND corner_number IN ({placeholders})",
            conn,
            params=[venue] + corner_numbers,
        )
    finally:
        conn.close()

    if df.empty:
        return {}

    result = {}
    for cn, group in df.groupby("corner_number"):
        tl = group["time_loss_s"].dropna()
        if len(tl) < 2:
            continue
        mean_val = float(tl.mean())
        std_val  = float(tl.std()) if len(tl) > 1 else 0.0
        result[int(cn)] = {
            "p10":             float(np.percentile(tl, 10)),
            "p25":             float(np.percentile(tl, 25)),
            "mean":            mean_val,
            "std":             std_val,
            "n_samples":       len(tl),
            "consistency_pct": round(max(0.0, 100.0 * (1.0 - std_val / (abs(mean_val) + 0.01))), 1),
        }
    return result


def enriquecer_corners_con_historial(corners: list[dict], metadata: dict) -> list[dict]:
    """
    Capa 1 + 2: Añade p10_time_loss_s, consistency_pct, n_hist_samples a cada corner dict.
    Estos campos se renderizan en CornerReport como badge de consistencia.
    """
    hist = _get_hist_by_corner(corners, metadata)
    if not hist:
        return corners

    enriched = []
    for c in corners:
        cn = c.get("corner_number")
        h  = hist.get(cn)
        if h and h["n_samples"] >= 3:
            c = dict(c)
            c["p10_time_loss_s"]  = round(h["p10"], 4)
            c["consistency_pct"]  = h["consistency_pct"]
            c["n_hist_samples"]   = h["n_samples"]
        enriched.append(c)
    return enriched


# ── Reachable Lap ─────────────────────────────────────────────────────────────

def calcular_tiempo_potencial(
    sectores: list[dict],
    corners:  list[dict],
    metadata: dict,
) -> dict:
    """
    Capa 1: Reachable Lap usando percentil-10 del historial por curva.
    Fallback a suma de deltas positivos cuando no hay historial suficiente.

    Returns:
        {
            "theoretical_best_delta_s": float,
            "potential_gain_s":         float,
            "use_reachable":            bool,
            "sectors": [
                {sector, zona, delta_actual_s, gain_posible_s,
                 reachable_s, consistency_pct, n_hist_samples, optimized, estado}
            ]
        }
    """
    if not sectores:
        return {"theoretical_best_delta_s": 0.0, "potential_gain_s": 0.0,
                "use_reachable": False, "sectors": []}

    hist           = _get_hist_by_corner(corners, metadata)
    corner_by_num  = {c.get("corner_number"): c for c in corners}
    use_reachable  = False
    sector_results = []
    potential_gain = 0.0

    for s in sectores:
        sector_num = int(s.get("sector", 0))
        delta      = float(s.get("delta_parcial", 0.0))
        h          = hist.get(sector_num)
        corner     = corner_by_num.get(sector_num)

        reachable_s     = 0.0
        consistency_pct = None
        n_samples       = 0

        if h and h["n_samples"] >= 3 and corner is not None:
            actual      = float(corner.get("time_loss_seconds") or 0)
            reachable_s = round(max(0.0, actual - h["p10"]), 3)
            consistency_pct = h["consistency_pct"]
            n_samples   = h["n_samples"]
            potential_gain += reachable_s
            use_reachable  = True
        else:
            gain        = max(0.0, delta)
            reachable_s = round(gain, 3)
            potential_gain += gain

        gap    = reachable_s if consistency_pct is not None else max(0.0, delta)
        estado = _status(gap)

        sector_results.append({
            "sector":           sector_num,
            "zona":             s.get("descripcion", ""),
            "delta_actual_s":   round(delta, 3),
            "gain_posible_s":   round(max(0.0, delta), 3),
            "reachable_s":      reachable_s,
            "consistency_pct":  consistency_pct,
            "n_hist_samples":   n_samples,
            "optimized":        gap < 0.05,
            "estado":           estado,
        })

    return {
        "theoretical_best_delta_s": round(-potential_gain, 3),
        "potential_gain_s":         round(potential_gain, 3),
        "use_reachable":            use_reachable,
        "sectors":                  sector_results,
    }


# ── Historial SQLite ──────────────────────────────────────────────────────────

def guardar_en_historial(
    metadata:   dict,
    corners:    list[dict],
    apexes_df,
    df_aligned: pd.DataFrame,
) -> int:
    """Persiste el vector de features de cada curva en SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    _init_db(conn)
    rows = _build_history_rows(metadata, corners, apexes_df, df_aligned)
    if not rows:
        conn.close()
        return 0

    cursor = conn.cursor()
    cursor.executemany(
        f"INSERT OR IGNORE INTO lap_history ({', '.join(HISTORY_FEATURES)}) "
        f"VALUES ({', '.join(['?'] * len(HISTORY_FEATURES))})",
        [tuple(r[f] for f in HISTORY_FEATURES) for r in rows],
    )
    conn.commit()
    inserted = cursor.rowcount
    conn.close()
    logger.info(f"Historial: {inserted} observaciones guardadas en {DB_PATH}")
    return inserted


def n_observaciones_historial() -> int:
    if not DB_PATH.exists():
        return 0
    conn = sqlite3.connect(str(DB_PATH))
    try:
        n = conn.execute("SELECT COUNT(*) FROM lap_history").fetchone()[0]
    finally:
        conn.close()
    return n


# ── Capa 3: XGBoost + Explicaciones ──────────────────────────────────────────

def predecir_tiempo_potencial_ml(
    corners:  list[dict],
    metadata: dict,
) -> dict | None:
    """
    Capa 3: entrena XGBoost y predice el tiempo óptimo por curva.
    Incluye top-2 explicaciones: features que más alejan al piloto del perfil rápido.
    Retorna None si hay < MIN_SAMPLES_FOR_ML observaciones.
    """
    n = n_observaciones_historial()
    if n < MIN_SAMPLES_FOR_ML:
        logger.info(f"XGBoost: {n}/{MIN_SAMPLES_FOR_ML} obs — no disponible aún.")
        return None

    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("xgboost no instalado — pip install xgboost")
        return None

    conn = sqlite3.connect(str(DB_PATH))
    df_hist = pd.read_sql("SELECT * FROM lap_history", conn)
    conn.close()

    target_col = "time_loss_s"
    df_hist = df_hist.dropna(subset=FEATURE_COLS + [target_col])
    if len(df_hist) < MIN_SAMPLES_FOR_ML:
        return None

    X = df_hist[FEATURE_COLS].values
    y = df_hist[target_col].values

    model = xgb.XGBRegressor(
        n_estimators=80, max_depth=4, learning_rate=0.1,
        subsample=0.8, random_state=42, verbosity=0,
    )
    model.fit(X, y)

    predictions = []
    for c in corners:
        features = _corner_to_features(c)
        if features is None:
            continue
        pred_loss    = float(model.predict([features])[0])
        explanations = _compute_explanations(features, model, df_hist)

        predictions.append({
            "corner_number":            c.get("corner_number"),
            "predicted_optimal_loss_s": round(max(0.0, pred_loss), 3),
            "actual_loss_s":            round(float(c.get("time_loss_seconds") or 0), 3),
            "explanations":             explanations,
        })

    total_optimal = sum(p["predicted_optimal_loss_s"] for p in predictions)
    total_actual  = sum(p["actual_loss_s"]            for p in predictions)

    logger.info(
        f"XGBoost: predicción lista ({len(df_hist)} obs) — "
        f"mejora estimada {total_actual - total_optimal:.3f}s"
    )
    return {
        "model":              "XGBoost",
        "training_samples":   len(df_hist),
        "predicted_gain_s":   round(total_actual - total_optimal, 3),
        "corner_predictions": predictions,
    }


# ── Helpers privados ──────────────────────────────────────────────────────────

def _compute_explanations(
    features_vec: list,
    model,
    df_hist: pd.DataFrame,
) -> list[dict]:
    """
    Compara las features del corner actual vs el perfil de los corners más rápidos
    (bottom 25% time_loss). Devuelve top-2 desviaciones ponderadas por importancia.
    """
    fast_threshold = df_hist["time_loss_s"].quantile(0.25)
    fast = df_hist[df_hist["time_loss_s"] <= fast_threshold]

    if len(fast) < 3:
        return []

    importances = model.feature_importances_
    results = []

    for i, feat in enumerate(FEATURE_COLS):
        meta = FEATURE_META.get(feat)
        if meta is None:
            continue
        label, unit, sign = meta

        val       = float(features_vec[i])
        fast_mean = float(fast[feat].mean())
        fast_std  = float(fast[feat].std()) + 1e-6

        # deviation > 0 → peor que el perfil rápido
        deviation = (fast_mean - val) * sign
        z         = deviation / fast_std

        if z < 0.4:
            continue

        results.append({
            "feature":    label,
            "unit":       unit,
            "actual":     round(val, 1),
            "optimal":    round(fast_mean, 1),
            "gap":        round(val - fast_mean, 1),
            "importance": round(float(importances[i]), 3),
            "z":          round(z, 2),
        })

    results.sort(key=lambda x: x["importance"] * x["z"], reverse=True)
    return results[:2]


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS lap_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(
                f'{f} REAL' if f not in ('venue', 'vehicle') else f'{f} TEXT'
                for f in HISTORY_FEATURES
            )},
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _build_history_rows(
    metadata:   dict,
    corners:    list[dict],
    apexes_df,
    df_aligned: pd.DataFrame,
) -> list[dict]:
    rows         = []
    venue        = metadata.get("venue")        or ""
    vehicle      = metadata.get("vehicle_fast") or ""
    track_length = float(df_aligned["Distance"].iloc[-1]) if not df_aligned.empty else 0.0

    for corner in corners:
        cn    = corner.get("corner_number")
        start = corner.get("start_distance")
        end   = corner.get("end_distance")
        if cn is None or start is None:
            continue

        window = df_aligned[
            (df_aligned["Distance"] >= start) &
            (df_aligned["Distance"] <= (end or start + 200))
        ]

        entry_speed = float(window["Speed_Fast"].iloc[0])    if "Speed_Fast"        in window.columns and not window.empty else 0.0
        apex_speed  = 0.0
        if apexes_df is not None and not apexes_df.empty and cn - 1 < len(apexes_df):
            apex_speed = float(apexes_df.iloc[cn - 1].get("Speed", 0))
        exit_thr    = float(window["Throttle_Fast"].iloc[-1]) if "Throttle_Fast"     in window.columns and not window.empty else 0.0
        g_eff       = float(window["G_Efficiency_Fast"].mean()) if "G_Efficiency_Fast" in window.columns else 0.0
        steer_var   = float(window["SteerAngle_Fast"].var())    if "SteerAngle_Fast"   in window.columns else 0.0

        curvature_r = 0.0
        if apexes_df is not None and not apexes_df.empty and cn - 1 < len(apexes_df):
            kappa = float(apexes_df.iloc[cn - 1].get("Curvature", 0))
            curvature_r = (1 / kappa) if kappa > 0 else 999.0

        rows.append({
            "venue":              venue,
            "vehicle":            vehicle,
            "corner_number":      int(cn),
            "track_length_m":     round(track_length, 1),
            "entry_speed_kmh":    round(entry_speed, 2),
            "apex_speed_kmh":     round(apex_speed, 2),
            "exit_throttle_pct":  round(exit_thr, 2),
            "braking_delta_m":    round(float(corner.get("braking_delta_meters")  or 0), 1),
            "throttle_delta_m":   round(float(corner.get("throttle_delta_meters") or 0), 1),
            "g_efficiency_pct":   round(g_eff, 2),
            "steer_variance":     round(steer_var, 2),
            "curvature_radius_m": round(curvature_r, 1),
            "time_loss_s":        round(float(corner.get("time_loss_seconds") or 0), 4),
        })

    return rows


def _corner_to_features(corner: dict) -> list[float] | None:
    if corner.get("time_loss_seconds") is None:
        return None
    return [
        float(corner.get("entry_speed_kmh")      or 0),
        float(corner.get("apex_speed_kmh")        or 0),
        float(corner.get("exit_throttle_pct")     or 0),
        float(corner.get("braking_delta_meters")  or 0),
        float(corner.get("throttle_delta_meters") or 0),
        float(corner.get("g_efficiency_pct")      or 0),
        float(corner.get("steer_variance")        or 0),
        float(corner.get("curvature_radius_m")    or 0),
    ]
