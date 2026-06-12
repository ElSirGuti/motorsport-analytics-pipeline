import logging
import numpy as np
import pandas as pd

from src.analytics.stint import segmentar_vueltas_desde_csv

logger = logging.getLogger(__name__)


def _clean(val):
    if pd.isna(val) or (isinstance(val, float) and np.isinf(val)):
        return None
    return float(val)


def _auto_select_map_axes(df):
    """Pick the two coordinate columns with the largest range — horizontal plane."""
    candidates = {}
    for col in ["CarCoordX", "CarCoordY", "CarCoordZ"]:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals) > 10:
                candidates[col] = float(vals.max() - vals.min())
    if len(candidates) < 2:
        return None, None
    ordered = sorted(candidates, key=candidates.get, reverse=True)
    return ordered[0], ordered[1]


def _lap_distance(lap_df, lap_time):
    """Compute lap distance in metres. Falls back to speed integral if column is absent or zero."""
    dist_col = next((c for c in ["Distance", "Dist"] if c in lap_df.columns), None)
    if dist_col:
        vals = pd.to_numeric(lap_df[dist_col], errors="coerce").dropna()
        if len(vals) > 0:
            d_range = float(vals.max() - vals.min())
            if d_range > 10:
                return round(d_range, 1)
            d_max = float(vals.max())
            if d_max > 10:
                return round(d_max, 1)

    # Speed-integral fallback
    if "Speed" not in lap_df.columns or not lap_time:
        return None
    spd_ms = pd.to_numeric(lap_df["Speed"], errors="coerce").fillna(0) / 3.6
    time_ch = next(
        (tc for tc in ["LR Sample Clock", "HR Sample Clock", "MR Sample Clock"]
         if tc in lap_df.columns),
        None,
    )
    if time_ch:
        t = pd.to_numeric(lap_df[time_ch], errors="coerce").ffill().bfill()
        dt = t.diff().fillna(0).clip(lower=0, upper=2.0)
        return round(float((spd_ms * dt).sum()), 1)
    # Last resort: mean_speed × time
    return round(float(spd_ms.mean()) * lap_time, 1)


def analyze_session(df: pd.DataFrame) -> dict:
    """
    Analiza un DataFrame de telemetría de sesión completa.
    Usa segmentar_vueltas_desde_csv para dividir en vueltas individuales,
    luego extrae estadísticas por vuelta y determina la vuelta más rápida.
    """
    try:
        lap_dfs = segmentar_vueltas_desde_csv(df)
    except ValueError as exc:
        logger.warning("No se pudieron segmentar vueltas: %s", exc)
        return {"laps": [], "fastest_lap": None, "track_map": [], "total_laps": 0}

    laps_data = []
    for i, lap_df in enumerate(lap_dfs, start=1):
        # Lap time — use LapTime (current-lap timer, last value) or session clock diff
        lap_time = None
        for tc in ["LapTime", "LR Sample Clock", "HR Sample Clock", "MR Sample Clock"]:
            if tc not in lap_df.columns:
                continue
            t = pd.to_numeric(lap_df[tc], errors="coerce")
            t0, t1 = float(t.iloc[0]), float(t.iloc[-1])
            if pd.isna(t0) or pd.isna(t1):
                continue
            if tc == "LapTime" and t0 < 10 and t1 > 5:
                lap_time = round(t1, 3)
            elif t1 > t0:
                lap_time = round(t1 - t0, 3)
            if lap_time:
                break

        # Skip laps shorter than 30 s (pit stop segments, partial laps)
        if lap_time is None or lap_time < 30:
            logger.debug("Vuelta %d descartada: tiempo=%.1fs", i, lap_time or 0)
            continue

        # Pit lap detection: In Pit channel, then time-outlier promotion
        in_pit_col = next((c for c in ["In Pit", "InPit", "in_pit"] if c in lap_df.columns), None)
        is_pit_lap = False
        if in_pit_col:
            in_pit_vals = pd.to_numeric(lap_df[in_pit_col], errors="coerce").fillna(0)
            is_pit_lap = bool((in_pit_vals > 0).any())

        spd = lap_df["Speed"] if "Speed" in lap_df.columns else None

        laps_data.append({
            "lap_number":   i,
            "lap_time":     lap_time,
            "lap_distance": _lap_distance(lap_df, lap_time),
            "max_speed":    _clean(spd.max())  if spd is not None else None,
            "min_speed":    _clean(spd.min())  if spd is not None else None,
            "max_brake":    _clean(lap_df["Brake"].max())       if "Brake"    in lap_df.columns else None,
            "avg_throttle": _clean(lap_df["Throttle"].mean())   if "Throttle" in lap_df.columns else None,
            "is_pit_lap":   is_pit_lap,
        })

    # Post-hoc outlier promotion to pit_lap (catches SC, out-laps, partial laps)
    racing_times = [l["lap_time"] for l in laps_data if not l["is_pit_lap"] and l["lap_time"]]
    if len(racing_times) >= 3:
        median_t = float(np.median(racing_times))
        for l in laps_data:
            if not l["is_pit_lap"] and l["lap_time"] is not None:
                t = l["lap_time"]
                if t < median_t * 0.70 or t > median_t * 1.15:
                    l["is_pit_lap"] = True

    # Fastest racing lap (non-pit)
    fastest_lap = None
    racing_laps = [l for l in laps_data if not l["is_pit_lap"]]
    if racing_laps:
        fastest_lap = min(racing_laps, key=lambda x: x["lap_time"])
        fl_num = fastest_lap["lap_number"]
        for lap in laps_data:
            lap["is_fastest"] = (lap["lap_number"] == fl_num)
    else:
        for lap in laps_data:
            lap["is_fastest"] = False

    # Track map from fastest lap — auto-select horizontal-plane axes
    track_map = []
    if fastest_lap and len(lap_dfs) >= fastest_lap["lap_number"]:
        fl_df = lap_dfs[fastest_lap["lap_number"] - 1]
        x_col, y_col = _auto_select_map_axes(fl_df)
        if x_col and y_col:
            step = max(1, len(fl_df) // 500)
            xs = fl_df[x_col].iloc[::step].fillna(0).tolist()
            ys = fl_df[y_col].iloc[::step].fillna(0).tolist()
            track_map = [{"x": float(x), "y": float(y)} for x, y in zip(xs, ys)]
            logger.info("Mapa del circuito: ejes '%s' vs '%s'", x_col, y_col)

    logger.info("Sesión analizada: %d vueltas válidas de %d segmentos", len(laps_data), len(lap_dfs))
    return {
        "laps":        laps_data,
        "fastest_lap": fastest_lap,
        "track_map":   track_map,
        "total_laps":  len(laps_data),
    }
