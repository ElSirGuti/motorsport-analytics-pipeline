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
    """Pick the two coordinate columns with the largest range — horizontal plane.

    Checks canonical ACTI names first, then iRacing GPS-style columns.
    Returns (x_col, y_col) or (None, None) if no suitable pair found.
    """
    # ACTI / Assetto Corsa coordinates
    candidates = {}
    for col in ["CarCoordX", "CarCoordY", "CarCoordZ"]:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals) > 10:
                candidates[col] = float(vals.max() - vals.min())
    if len(candidates) >= 2:
        ordered = sorted(candidates, key=candidates.get, reverse=True)
        return ordered[0], ordered[1]

    # iRacing GPS-style columns (lat/lon in decimal degrees or similar)
    iracing_pairs = [
        ("Lat", "Lon"),
        ("GPSlat", "GPSlon"),
        ("GPS Lat", "GPS Lon"),
        ("gps_lat", "gps_lon"),
    ]
    for x_cand, y_cand in iracing_pairs:
        if x_cand in df.columns and y_cand in df.columns:
            vx = pd.to_numeric(df[x_cand], errors="coerce").dropna()
            vy = pd.to_numeric(df[y_cand], errors="coerce").dropna()
            if len(vx) > 10 and len(vy) > 10:
                return x_cand, y_cand

    return None, None


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


def _dead_reckoning_map(lap_df: pd.DataFrame, n_points: int = 500) -> list:
    """Reconstruct the circuit shape using dead-reckoning when no GPS/coord columns exist.

    Uses Speed (km/h) and one of:
      - YawRate (rad/s or deg/s) — most accurate
      - SteerAngle (deg) as a proxy heading rate

    Integrates to build (x, y) positions in metres.
    Returns a list of {x, y, distance} dicts (max n_points), or [] if insufficient data.
    """
    if "Speed" not in lap_df.columns:
        return []

    # ── Time step ────────────────────────────────────────────────────────────
    time_candidates = [
        "LR Sample Clock", "HR Sample Clock", "MR Sample Clock",
        "SessionTime", "Session Time", "Time", "time",
    ]
    time_col = next((c for c in time_candidates if c in lap_df.columns), None)

    speed_ms = pd.to_numeric(lap_df["Speed"], errors="coerce").fillna(0) / 3.6  # km/h → m/s

    if time_col:
        t = pd.to_numeric(lap_df[time_col], errors="coerce").ffill().bfill()
        dt = t.diff().fillna(0).clip(lower=0, upper=0.5)
    else:
        # Assume ~60 Hz iRacing default sample rate
        dt = pd.Series(1.0 / 60.0, index=lap_df.index)

    # ── Heading rate ─────────────────────────────────────────────────────────
    heading_rate = None  # rad/s

    if "YawRate" in lap_df.columns:
        yr = pd.to_numeric(lap_df["YawRate"], errors="coerce").fillna(0)
        # Detect if unit is deg/s (typical range > 5) or rad/s (typical range < 2)
        if yr.abs().max() > 5.0:
            yr = np.deg2rad(yr)
        heading_rate = yr

    elif "SteerAngle" in lap_df.columns:
        # Rough proxy: treat steer angle (deg) as proportional to yaw rate
        # Scale factor calibrated empirically (~0.003 rad·s⁻¹ per deg at circuit speeds)
        steer_deg = pd.to_numeric(lap_df["SteerAngle"], errors="coerce").fillna(0)
        heading_rate = steer_deg * 0.003

    if heading_rate is None:
        logger.debug("Dead-reckoning: sin YawRate ni SteerAngle — mapa no disponible")
        return []

    # ── Integrate heading and position ───────────────────────────────────────
    heading = np.cumsum((heading_rate * dt).fillna(0).values)  # radians
    dx = (speed_ms * np.cos(heading) * dt).fillna(0)
    dy = (speed_ms * np.sin(heading) * dt).fillna(0)
    x_pos = np.cumsum(dx.values)
    y_pos = np.cumsum(dy.values)
    dist  = (speed_ms * dt).cumsum().fillna(0).values

    # ── Downsample to n_points ───────────────────────────────────────────────
    n = len(x_pos)
    step = max(1, n // n_points)
    indices = range(0, n, step)

    return [
        {"x": float(x_pos[i]), "y": float(y_pos[i]), "distance": float(dist[i])}
        for i in indices
    ]


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
        for tc in ["LapTime", "Time", "SessionTime", "Session Time", "LR Sample Clock", "HR Sample Clock", "MR Sample Clock"]:
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
            xs    = fl_df[x_col].iloc[::step].fillna(0).tolist()
            ys    = fl_df[y_col].iloc[::step].fillna(0).tolist()
            dists = (
                fl_df["Distance"].iloc[::step].fillna(0).tolist()
                if "Distance" in fl_df.columns else [0.0] * len(xs)
            )
            track_map = [
                {"x": float(x), "y": float(y), "distance": float(d)}
                for x, y, d in zip(xs, ys, dists)
            ]
            logger.info("Mapa del circuito: ejes '%s' vs '%s'", x_col, y_col)
        else:
            # Dead-reckoning fallback for iRacing (no absolute coords)
            # Integrate velocity and heading angle to reconstruct path
            track_map = _dead_reckoning_map(fl_df)
            if track_map:
                logger.info("Mapa del circuito: dead-reckoning (sin coordenadas absolutas)")

    logger.info("Sesión analizada: %d vueltas válidas de %d segmentos", len(laps_data), len(lap_dfs))
    return {
        "laps":        laps_data,
        "fastest_lap": fastest_lap,
        "track_map":   track_map,
        "total_laps":  len(laps_data),
    }
