"""
Análisis de Stint Completo — 4 módulos:
1. extraer_metricas_por_vuelta — resume cada vuelta en KPIs
2. analizar_degradacion — regresión lineal tiempo/G-sum vs vuelta
3. calcular_estrategia_combustible — pit window con σ conservador
4. simular_tiempos_stint — Monte Carlo reproducible con varianza real
"""
import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.i18n import _ as _tr

logger = logging.getLogger(__name__)

FUEL_CHANNELS     = ["Fuel", "FuelLevel", "Fuel Level", "fuel_level", "FuelMass", "Fuel Mass"]
MAX_FUEL_CHANNELS = ["Max Fuel", "MaxFuel", "max_fuel", "FuelCapacity", "Fuel Capacity"]
TYRE_CHANNELS = {
    "FL": ["TyreTemp_FL", "Tyre Temp FL", "TyreTempFL"],
    "FR": ["TyreTemp_FR", "Tyre Temp FR", "TyreTempFR"],
    "RL": ["TyreTemp_RL", "Tyre Temp RL", "TyreTempRL"],
    "RR": ["TyreTemp_RR", "Tyre Temp RR", "TyreTempRR"],
}
N_SIMULATIONS = 500
N_FUTURE_LAPS = 12
FUEL_SIGMA_SCALE = 1.65  # percentil 95

# --- Projection realism ---
MIN_LAPS_FOR_TREND = 5          # fewer valid race laps -> flat projection, low confidence
MAX_ABS_SLOPE_S_PER_LAP = 0.15  # physically plausible |tyre+fuel+track| slope
SLOPE_PRIOR_SD = 0.05           # prior sd (s/lap) of the slope around its physical prior mean
FUEL_S_PER_L = 0.035            # lap-time gain per litre burned (mass effect)
MIN_FUEL_BURN_L = 0.05          # below this the fuel channel is considered not logged
LEVEL_DRIFT_SD = 0.08           # s/lap random-walk drift of the pace level (widens the band)
SIGMA_FLOOR_S = 0.25


def _find_channel(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


_LAP_CHANNELS  = ["Session Lap Count", "SessionLapCount", "Lap", "LapNumber",
                  "Lap Number", "LapCount", "session_lap_count"]
_DIST_CHANNELS = ["Distance", "Dist", "LapDistance", "lap_distance"]


MIN_LAP_SEGMENT_S = 30.0   # segments shorter than this are partial laps (end of log, pit stub)

_TIME_CHANNELS = ["LapTime", "Time", "SessionTime", "Session Time",
                  "LR Sample Clock", "HR Sample Clock", "MR Sample Clock"]


def _segment_duration_s(seg: pd.DataFrame) -> float:
    """Duration of a lap segment in seconds (NaN if no usable time channel)."""
    for c in _TIME_CHANNELS:
        if c not in seg.columns:
            continue
        t = pd.to_numeric(seg[c], errors="coerce").dropna()
        if len(t) < 2:
            continue
        t0, t1 = float(t.iloc[0]), float(t.iloc[-1])
        if c == "LapTime" and t0 < 10 and t1 > 5:
            return t1
        if t1 > t0:
            return t1 - t0
    return float("nan")


def descartar_segmentos_parciales(dfs: list, min_s: float = MIN_LAP_SEGMENT_S) -> list:
    """Drop partial segments (< min_s seconds) so every endpoint sees the same laps.

    Segments whose duration cannot be measured are kept. If dropping would leave
    fewer than 2 laps, the original list is returned unchanged.
    """
    kept = [d for d in dfs if not (_segment_duration_s(d) < min_s)]
    if len(kept) < len(dfs):
        logger.info("Segmentos parciales descartados (<%.0fs): %d", min_s, len(dfs) - len(kept))
    return kept if len(kept) >= 2 else dfs


def segmentar_vueltas_desde_csv(df: pd.DataFrame) -> list:
    """
    Splits a single multi-lap session DataFrame into a list of per-lap DataFrames.

    Strategy 1 — Lap counter channel: groups rows by unique integer values in a
    recognised lap-number column (e.g. MoTeC "Session Lap Count").

    Strategy 2 — Distance reset: detects when the distance channel drops to less
    than 30 % of the previous value, indicating a new lap has started.

    Returns a list of DataFrames (one per lap) with at least 10 rows each.
    Raises ValueError when fewer than 2 valid laps are detected.
    """
    def _reset_distance(seg: pd.DataFrame) -> pd.DataFrame:
        """Resets the Distance column so each lap segment starts at 0."""
        seg = seg.copy()
        if "Distance" in seg.columns:
            reset = pd.to_numeric(seg["Distance"], errors="coerce") - pd.to_numeric(seg["Distance"], errors="coerce").iloc[0]
            if float(reset.max()) > 10.0:
                seg["Distance"] = reset
                return seg
        # Distance absent or flat — synthesize from Speed × time
        time_ch = next(
            (c for c in ["LR Sample Clock", "HR Sample Clock", "MR Sample Clock",
                          "SessionTime", "Session Time", "Time", "time"]
             if c in seg.columns),
            None,
        )
        if "Speed" in seg.columns:
            spd = pd.to_numeric(seg["Speed"], errors="coerce").fillna(0) / 3.6
            if time_ch:
                t = pd.to_numeric(seg[time_ch], errors="coerce").ffill().bfill()
                dt = t.diff().fillna(0).clip(lower=0, upper=2.0)
            else:
                # No time channel — use 100 Hz fixed interval as fallback
                dt = pd.Series(1.0 / 100.0, index=seg.index)
            seg["Distance"] = (spd * dt).cumsum()
        elif "Distance" in seg.columns:
            seg["Distance"] = pd.to_numeric(seg["Distance"], errors="coerce") - pd.to_numeric(seg["Distance"], errors="coerce").iloc[0]
        return seg

    lap_col = _find_channel(df, _LAP_CHANNELS)
    if lap_col is not None:
        try:
            lap_nums = df[lap_col].fillna(-1).astype(int)
            unique_laps = sorted(n for n in lap_nums.unique() if n >= 0)
            dfs = [_reset_distance(df[lap_nums == n].reset_index(drop=True)) for n in unique_laps]
            dfs = [d for d in dfs if len(d) >= 10]
            if len(dfs) >= 2:
                dfs = descartar_segmentos_parciales(dfs)
                logger.info("Segmentación por canal '%s': %d vueltas", lap_col, len(dfs))
                return dfs
        except Exception as exc:
            logger.warning("Fallo en segmentación por canal de vuelta: %s", exc)

    dist_col = _find_channel(df, _DIST_CHANNELS)
    if dist_col is not None:
        dist = df[dist_col].reset_index(drop=True)
        splits = [0]
        for i in range(1, len(dist)):
            prev = dist.iloc[i - 1]
            curr = dist.iloc[i]
            if prev > 50 and curr < prev * 0.30:
                splits.append(i)
        splits.append(len(dist))
        dfs = [
            _reset_distance(df.iloc[splits[j]: splits[j + 1]].reset_index(drop=True))
            for j in range(len(splits) - 1)
        ]
        dfs = [d for d in dfs if len(d) >= 10]
        if len(dfs) >= 2:
            dfs = descartar_segmentos_parciales(dfs)
            logger.info("Segmentación por reset de distancia: %d vueltas", len(dfs))
            return dfs

    raise ValueError(
        _tr("stint_err_no_laps"))


def _format_laptime(seconds):
    if seconds <= 0 or np.isnan(seconds):
        return "—"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


def _racing_laps_mask(df_laps: pd.DataFrame) -> pd.Series:
    """
    Boolean mask for laps to include in regression and Monte Carlo.
    Excludes: pit laps (In Pit channel) and time outliers (< 70% or > 115% of median).
    """
    mask = pd.Series(True, index=df_laps.index)

    if "is_pit_lap" in df_laps.columns:
        mask &= ~df_laps["is_pit_lap"]

    valid_times = df_laps.loc[mask & df_laps["lap_time_s"].notna(), "lap_time_s"]
    if len(valid_times) >= 3:
        median_t = valid_times.median()
        mask &= (
            df_laps["lap_time_s"].isna() |
            ((df_laps["lap_time_s"] >= median_t * 0.70) &
             (df_laps["lap_time_s"] <= median_t * 1.15))
        )

    return mask & df_laps["lap_time_s"].notna()


def extraer_metricas_por_vuelta(dfs):
    """
    dfs: list of DataFrames (one per lap, already normalized by load_telemetry_data).
    Returns a DataFrame with one row per lap.
    """
    rows = []
    for i, df in enumerate(dfs, start=1):
        row = {"lap_number": i}

        # LapTime = current-lap timer (starts near 0, last value = lap duration)
        # LR/HR Sample Clock = absolute session clock (diff = lap duration)
        # Time / LapTime after alias resolution may be either
        lap_time_s = float("nan")
        t_col = _find_channel(df, ["LapTime", "Time", "SessionTime", "Session Time", "LR Sample Clock", "HR Sample Clock", "MR Sample Clock"])
        if t_col:
            t = pd.to_numeric(df[t_col], errors="coerce")
            t_start, t_end = float(t.iloc[0]), float(t.iloc[-1])
            if not (np.isnan(t_start) or np.isnan(t_end)):
                diff = t_end - t_start
                # Current-lap timer: starts near 0, duration = last value
                if t_start < 10 and t_end > 5:
                    lap_time_s = round(t_end, 3)
                elif diff > 0:
                    lap_time_s = round(diff, 3)
        row["lap_time_s"]   = lap_time_s
        row["lap_time_str"] = _format_laptime(lap_time_s)

        spd = _find_channel(df, ["Speed", "Ground Speed"])
        if spd:
            row["mean_speed_kmh"] = round(float(df[spd].mean()), 1)
            row["max_speed_kmh"]  = round(float(df[spd].max()),  1)
        else:
            row["mean_speed_kmh"] = float("nan")
            row["max_speed_kmh"]  = float("nan")

        lat = _find_channel(df, ["LateralG", "Lateral G"])
        lon = _find_channel(df, ["LongitudinalG", "Longitudinal G"])
        if lat and lon:
            g_lat = pd.to_numeric(df[lat], errors="coerce")
            g_lon = pd.to_numeric(df[lon], errors="coerce")
            g_sum = np.sqrt(g_lat**2 + g_lon**2)
            row["max_g_sum"]  = round(float(g_sum.max()),  3)
            row["mean_g_sum"] = round(float(g_sum.mean()), 3)
        else:
            row["max_g_sum"]  = float("nan")
            row["mean_g_sum"] = float("nan")

        fuel_col = _find_channel(df, FUEL_CHANNELS)
        if fuel_col:
            row["fuel_start"]  = round(float(df[fuel_col].iloc[0]),  2)
            row["fuel_end"]    = round(float(df[fuel_col].iloc[-1]), 2)
            row["fuel_burned"] = round(row["fuel_start"] - row["fuel_end"], 3)
        else:
            row["fuel_start"]  = float("nan")
            row["fuel_end"]    = float("nan")
            row["fuel_burned"] = float("nan")

        tyre_temps = []
        for corner, candidates in TYRE_CHANNELS.items():
            col = _find_channel(df, candidates)
            if col:
                tyre_temps.append(float(df[col].mean()))
        row["tyre_temp_avg"] = round(float(np.mean(tyre_temps)), 1) if tyre_temps else float("nan")

        in_pit_col = _find_channel(df, ["In Pit", "InPit", "in_pit"])
        if in_pit_col:
            in_pit_vals = pd.to_numeric(df[in_pit_col], errors="coerce").fillna(0)
            row["is_pit_lap"] = bool((in_pit_vals > 0).any())
        else:
            row["is_pit_lap"] = False

        rows.append(row)

    df_result = pd.DataFrame(rows)

    # Post-hoc outlier detection: laps outside 70–115% of median are also excluded
    # from regression regardless of pit channel (catches out-laps, SC laps, etc.)
    valid_times = df_result.loc[~df_result["is_pit_lap"] & df_result["lap_time_s"].notna(), "lap_time_s"]
    if len(valid_times) >= 3:
        median_t = float(valid_times.median())
        df_result["is_outlier"] = (
            df_result["lap_time_s"].notna() &
            ((df_result["lap_time_s"] < median_t * 0.70) |
             (df_result["lap_time_s"] > median_t * 1.15))
        )
        # Promote outlier laps to pit_lap so they're excluded everywhere
        df_result.loc[df_result["is_outlier"], "is_pit_lap"] = True
    else:
        df_result["is_outlier"] = False

    return df_result


def _projection_laps(df_laps: pd.DataFrame) -> pd.DataFrame:
    """
    Laps that may feed the trend: racing laps minus out-laps (the lap right after a
    pit/outlier lap) and, when there is enough data, the session's first lap
    (standing/rolling start on cold tyres).
    """
    valid = df_laps[_racing_laps_mask(df_laps)]
    if "is_pit_lap" in df_laps.columns and len(valid) > MIN_LAPS_FOR_TREND:
        pit_nums = set(df_laps.loc[df_laps["is_pit_lap"], "lap_number"].astype(int))
        out_laps = {n + 1 for n in pit_nums}
        keep = ~valid["lap_number"].astype(int).isin(out_laps)
        if keep.sum() >= MIN_LAPS_FOR_TREND:
            valid = valid[keep]
    if len(valid) > MIN_LAPS_FOR_TREND and int(valid["lap_number"].iloc[0]) == 1:
        valid = valid.iloc[1:]
    return valid


def _fit_trend(valid: pd.DataFrame) -> dict:
    """
    Robust slope estimate: OLS + 95% CI, empirical-Bayes shrinkage towards the known
    physical effect (fuel burn) with prior sd SLOPE_PRIOR_SD, hard-clamped to
    +/-MAX_ABS_SLOPE_S_PER_LAP. Below MIN_LAPS_FOR_TREND the slope used is the fuel
    effect only (no extrapolated trend).
    """
    from scipy import stats

    x = valid["lap_number"].astype(float).values
    y = valid["lap_time_s"].astype(float).values
    n = len(x)

    # Explicit fuel-mass effect (negative = faster as the tank empties)
    fuel_effect = 0.0
    if "fuel_burned" in valid.columns:
        fb = valid["fuel_burned"].dropna()
        if len(fb) and float(fb.mean()) >= MIN_FUEL_BURN_L:
            fuel_effect = -FUEL_S_PER_L * float(fb.mean())

    slope_hat, se = 0.0, float("inf")
    ci = [None, None]
    r2 = 0.0
    if n >= 3 and np.ptp(x) > 0:
        slope_hat, intercept = np.polyfit(x, y, 1)
        resid = y - (slope_hat * x + intercept)
        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        sxx = float(np.sum((x - x.mean()) ** 2))
        se = float(np.sqrt(ss_res / (n - 2) / sxx))
        tcrit = float(stats.t.ppf(0.975, n - 2))
        ci = [float(slope_hat - tcrit * se), float(slope_hat + tcrit * se)]

    if n < MIN_LAPS_FOR_TREND or not np.isfinite(se):
        slope_used = float(np.clip(fuel_effect, -MAX_ABS_SLOPE_S_PER_LAP, MAX_ABS_SLOPE_S_PER_LAP))
        slope_se = SLOPE_PRIOR_SD
    else:
        tau2, se2 = SLOPE_PRIOR_SD ** 2, se ** 2
        w = tau2 / (tau2 + se2)
        post = fuel_effect + w * (float(slope_hat) - fuel_effect)
        slope_used = float(np.clip(post, -MAX_ABS_SLOPE_S_PER_LAP, MAX_ABS_SLOPE_S_PER_LAP))
        slope_se = min(float(np.sqrt(w) * se), SLOPE_PRIOR_SD)

    half = (ci[1] - ci[0]) / 2 if ci[0] is not None else float("inf")
    if n < MIN_LAPS_FOR_TREND or half > 0.2:
        confidence = "low"
    elif n >= 10 and half <= 0.05:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "n": n, "slope_hat": float(slope_hat), "slope_ci": ci, "r2": float(r2),
        "slope_used": slope_used, "slope_se": slope_se,
        "fuel_effect": fuel_effect, "confidence": confidence, "ci_half": half,
    }


def analizar_degradacion_stint(df_laps):
    """
    Lap-time trend vs lap number and a realistic projection N_FUTURE_LAPS ahead.

    The projected slope is NOT the raw OLS slope: it is shrunk (by n and slope
    uncertainty) towards the explicit fuel-burn effect and clamped to a plausible
    range. With fewer than MIN_LAPS_FOR_TREND valid laps the projection is flat
    around the recent pace and flagged low_confidence.
    Existing keys are unchanged; `tasa_s_per_lap` is now the robust slope used
    (raw OLS slope is in `raw_slope_s_per_lap`).
    """
    valid = _projection_laps(df_laps)
    if len(valid) < 3:
        return {"available": False}

    fit = _fit_trend(valid)
    n = fit["n"]
    y = valid["lap_time_s"].astype(float).values
    laps = valid["lap_number"].astype(float).values

    # Descriptive OLS line over the actual laps
    ols_slope, ols_icpt = np.polyfit(laps, y, 1)
    y_pred = ols_slope * laps + ols_icpt
    r2 = round(fit["r2"], 3)

    slope_used = fit["slope_used"]
    last_lap = int(valid["lap_number"].max())
    future_laps = list(range(last_lap + 1, last_lap + N_FUTURE_LAPS + 1))

    # Anchor: median of the recent laps, at their mean lap number
    k = min(3, n) if n >= MIN_LAPS_FOR_TREND else n
    anchor_t = float(np.median(y[-k:]))
    anchor_lap = float(np.mean(laps[-k:]))
    proj = [anchor_t + slope_used * (l - anchor_lap) for l in future_laps]
    # Never leave the observed range (+ small margin)
    lo = float(y.min()) - 0.5
    hi = float(y.max()) + max(1.5, abs(slope_used) * N_FUTURE_LAPS)
    proj = [min(max(v, lo), hi) for v in proj]

    low_conf = fit["confidence"] == "low"
    if n < MIN_LAPS_FOR_TREND:
        reason_code = "insufficient_sample"
        reason = _tr("stint_proj_low_n", n=n, min=MIN_LAPS_FOR_TREND, median=round(float(np.median(y)), 3))
    elif low_conf:
        reason_code = "wide_slope_ci"
        reason = _tr("stint_proj_wide_ci", hw=round(fit["ci_half"], 2))
    else:
        reason_code, reason = None, None

    ci = fit["slope_ci"]
    result = {
        "available":       True,
        "tasa_s_per_lap":  round(slope_used, 4),
        "r_squared":       r2,
        "actual_laps":     valid["lap_number"].tolist(),
        "actual_times":    [round(float(t), 3) for t in y],
        "trend_laps":      valid["lap_number"].tolist(),
        "trend_times":     [round(float(t), 3) for t in y_pred],
        "projected_laps":  future_laps,
        "projected_times": [round(float(t), 3) for t in proj],
        # --- new fields ---
        "confidence":      fit["confidence"],
        "low_confidence":  low_conf,
        "n_laps_used":     n,
        "slope_ci":        [round(ci[0], 4), round(ci[1], 4)] if ci[0] is not None else None,
        "raw_slope_s_per_lap":   round(fit["slope_hat"], 4),
        "fuel_effect_s_per_lap": round(fit["fuel_effect"], 4),
        "degradation_s_per_lap": round(slope_used - fit["fuel_effect"], 4),
        "slope_se_s_per_lap":    round(fit["slope_se"], 4),
        "reason_code":     reason_code,
        "reason":          reason,
        "anchor_time_s":   round(anchor_t, 3),
        "anchor_lap":      round(anchor_lap, 2),
        "min_laps_for_trend": MIN_LAPS_FOR_TREND,
    }

    valid_g = valid.dropna(subset=["max_g_sum"])
    if len(valid_g) >= 3:
        future_X = np.array(future_laps).reshape(-1, 1)
        mg = LinearRegression().fit(valid_g[["lap_number"]].values, valid_g["max_g_sum"].values)
        result["grip_tasa_per_lap"] = round(float(mg.coef_[0]), 4)
        result["grip_trend"]        = [round(float(v), 3) for v in mg.predict(valid_g[["lap_number"]].values)]
        result["grip_projected"]    = [round(float(v), 3) for v in mg.predict(future_X)]
        result["grip_actual_laps"]  = valid_g["lap_number"].tolist()
        result["grip_actual"]       = [round(float(v), 3) for v in valid_g["max_g_sum"].values]

    return result


def calcular_estrategia_combustible(df_laps, dfs: list | None = None):
    """
    Computes per-lap consumption, std, and safe pit window (95th percentile).
    If dfs (raw per-lap DataFrames) is provided, also reads Max Fuel for
    tank-relative metrics.
    """
    valid = df_laps[_racing_laps_mask(df_laps)].dropna(subset=["fuel_burned"])
    if valid.empty or valid["fuel_burned"].abs().sum() < 0.01:
        return {"available": False}

    consumo_medio = float(valid["fuel_burned"].mean())
    consumo_std   = float(valid["fuel_burned"].std()) if len(valid) > 1 else 0.0
    combustible_actual = float(df_laps["fuel_end"].dropna().iloc[-1]) if not df_laps["fuel_end"].isna().all() else 0.0
    combustible_inicio = float(df_laps["fuel_start"].dropna().iloc[0]) if not df_laps["fuel_start"].isna().all() else 0.0

    consumo_conservador = consumo_medio + FUEL_SIGMA_SCALE * consumo_std if len(valid) > 3 else consumo_medio
    consumo_optimista   = max(0.01, consumo_medio - consumo_std * 0.5)

    vueltas_min = int(combustible_actual // consumo_conservador) if consumo_conservador > 0 else 0
    vueltas_max = int(combustible_actual // consumo_optimista)   if consumo_optimista   > 0 else 0
    vuelta_actual = int(df_laps["lap_number"].max())

    # Per-lap trend: positive slope = consumption increasing (fuel weight effect or tyre/track changes)
    trend = None
    if len(valid) >= 4:
        x = np.arange(len(valid), dtype=float)
        slope = float(np.polyfit(x, valid["fuel_burned"].values, 1)[0])
        trend = round(slope, 4)   # L per lap change

    result = {
        "available":             True,
        "consumo_medio_l":       round(consumo_medio, 3),
        "consumo_std_l":         round(consumo_std, 3),
        "combustible_inicio_l":  round(combustible_inicio, 2),
        "combustible_actual_l":  round(combustible_actual, 2),
        "combustible_usado_l":   round(combustible_inicio - combustible_actual, 2),
        "vueltas_restantes_min": vueltas_min,
        "vueltas_restantes_max": vueltas_max,
        "pit_window":            [max(0, vuelta_actual + vueltas_min - 1), vuelta_actual + vueltas_max],
        "fuel_per_lap":          valid[["lap_number", "fuel_burned"]].to_dict(orient="records"),
        "trend_l_per_lap":       trend,
    }

    # Tank capacity from Max Fuel channel (AC only)
    if dfs:
        for df in dfs:
            tank_ch = _find_channel(df, MAX_FUEL_CHANNELS)
            if tank_ch:
                tank_vals = pd.to_numeric(df[tank_ch], errors="coerce").dropna()
                if not tank_vals.empty:
                    tank_cap = round(float(tank_vals.max()), 1)
                    result["tank_capacity_l"]     = tank_cap
                    result["laps_on_full_tank"]   = int(tank_cap // consumo_conservador) if consumo_conservador > 0 else None
                    result["pct_used"]            = round((combustible_inicio - combustible_actual) / tank_cap * 100, 1) if tank_cap > 0 else None
                    result["pct_remaining"]       = round(combustible_actual / tank_cap * 100, 1) if tank_cap > 0 else None
                    break

    return result


def simular_tiempos_stint(df_laps, degradacion, seed=42):
    """
    Monte Carlo projection (reproducible with seed). Uncertainty has three parts that
    make the P10-P90 band widen with the horizon: lap-to-lap noise, uncertainty of the
    slope (slope_se * horizon) and a small random-walk drift of the pace level.
    Projections are clipped to [best real lap - 0.5 s, worst real lap + margin].
    """
    valid = _projection_laps(df_laps)
    if len(valid) < 3 or not degradacion.get("available"):
        return {"available": False}

    rng = np.random.default_rng(seed)
    y = valid["lap_time_s"].astype(float).values
    laps = valid["lap_number"].astype(float).values
    n = len(y)
    n_future = N_FUTURE_LAPS
    last_lap = int(valid["lap_number"].max())

    slope = float(degradacion.get("tasa_s_per_lap", 0.0))
    slope_se = float(degradacion.get("slope_se_s_per_lap", SLOPE_PRIOR_SD))
    anchor_t = float(degradacion.get("anchor_time_s", np.median(y[-3:])))
    anchor_lap = float(degradacion.get("anchor_lap", np.mean(laps[-3:])))
    confidence = degradacion.get("confidence", "low")
    low_conf = bool(degradacion.get("low_confidence", n < MIN_LAPS_FOR_TREND))

    # Lap-to-lap noise: residual spread (never below a floor); inflated for tiny samples
    if n >= MIN_LAPS_FOR_TREND:
        resid = y - np.polyval(np.polyfit(laps, y, 1), laps)
        sigma = float(np.std(resid, ddof=2))
    else:
        sigma = float(np.std(y, ddof=1))
    sigma = max(sigma, SIGMA_FLOOR_S)

    h = np.arange(1, n_future + 1)
    horizon_from_anchor = (last_lap + h) - anchor_lap

    slope_draw = np.clip(rng.normal(slope, slope_se, size=(N_SIMULATIONS, 1)),
                         -MAX_ABS_SLOPE_S_PER_LAP, MAX_ABS_SLOPE_S_PER_LAP)
    level0 = rng.normal(0.0, sigma / np.sqrt(max(min(n, 3), 1)), size=(N_SIMULATIONS, 1))
    drift = np.cumsum(rng.normal(0.0, LEVEL_DRIFT_SD, size=(N_SIMULATIONS, n_future)), axis=1)
    noise = np.maximum(rng.normal(0.0, sigma, size=(N_SIMULATIONS, n_future)), -sigma)
    sims = anchor_t + level0 + slope_draw * horizon_from_anchor + drift + noise

    lo = float(y.min()) - 0.5
    hi = float(y.max()) + max(1.5, 3 * sigma, abs(slope) * n_future)
    sims = np.clip(sims, lo, hi)

    future_laps = list(range(last_lap + 1, last_lap + n_future + 1))
    return {
        "available":    True,
        "future_laps":  future_laps,
        "sigma_real_s": round(sigma, 3),
        "p10":  [round(float(v), 3) for v in np.percentile(sims, 10,  axis=0)],
        "p25":  [round(float(v), 3) for v in np.percentile(sims, 25,  axis=0)],
        "p50":  [round(float(v), 3) for v in np.percentile(sims, 50,  axis=0)],
        "p75":  [round(float(v), 3) for v in np.percentile(sims, 75,  axis=0)],
        "p90":  [round(float(v), 3) for v in np.percentile(sims, 90,  axis=0)],
        # --- new fields ---
        "confidence":     confidence,
        "low_confidence": low_conf,
        "n_laps_used":    n,
        "slope_ci":       degradacion.get("slope_ci"),
        "slope_used_s_per_lap": round(slope, 4),
        "clip_range_s":   [round(lo, 3), round(hi, 3)],
        "reason_code":    degradacion.get("reason_code"),
        "reason":         degradacion.get("reason"),
    }


def calcular_evolucion_pista(df_laps: pd.DataFrame) -> dict:
    if df_laps is None or df_laps.empty:
        return {"available": False, "reason": "no laps"}
    # extraer_metricas_por_vuelta() names the column 'lap_time_s'; older callers used LapTime.
    time_col = next((c for c in ["lap_time_s", "LapTime", "Lap Time", "lap_time", "Time"]
                     if c in df_laps.columns), None)
    if time_col is None:
        return {"available": False, "reason": "no lap-time column"}
    # Only representative laps: pit/out/in laps would swamp the grip trend.
    sel = df_laps
    if time_col == "lap_time_s" and "is_pit_lap" in df_laps.columns:
        sel = df_laps[_racing_laps_mask(df_laps)]
    times = sel[time_col].dropna()
    if len(times) < 4:
        return {"available": False, "reason": _tr("unavail_few_repr_laps_4")}
    lap_ids = (sel.loc[times.index, "lap_number"].astype(int).tolist()
               if "lap_number" in sel.columns else list(range(1, len(times) + 1)))
    window = min(3, len(times))
    rolling_min = times.rolling(window, min_periods=1).min()
    x = np.arange(len(rolling_min))
    slope, _ = np.polyfit(x, rolling_min.values, 1)
    total_gain = slope * (len(rolling_min) - 1)
    direction = "improving" if slope < -0.05 else "degrading" if slope > 0.05 else "stable"
    gain_txt = str(round(abs(total_gain), 2))
    note = (
        _tr("stint_track_improving", gain=gain_txt) if direction == "improving"
        else _tr("stint_track_degrading", gain=gain_txt) if direction == "degrading"
        else _tr("stint_track_stable")
    )
    per_lap = [{"lap": int(l), "rolling_min_s": round(float(v), 3)}
               for l, v in zip(lap_ids, rolling_min)]
    return {
        "available": True,
        "direction": direction,
        "trend_s_per_lap": round(float(slope), 4),
        "total_gain_s": round(float(total_gain), 3),
        "note": note,
        "per_lap": per_lap,
    }
