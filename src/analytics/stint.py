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

logger = logging.getLogger(__name__)

FUEL_CHANNELS = ["Fuel", "FuelLevel", "Fuel Level", "fuel_level", "FuelMass", "Fuel Mass"]
TYRE_CHANNELS = {
    "FL": ["TyreTemp_FL", "Tyre Temp FL", "TyreTempFL"],
    "FR": ["TyreTemp_FR", "Tyre Temp FR", "TyreTempFR"],
    "RL": ["TyreTemp_RL", "Tyre Temp RL", "TyreTempRL"],
    "RR": ["TyreTemp_RR", "Tyre Temp RR", "TyreTempRR"],
}
N_SIMULATIONS = 500
N_FUTURE_LAPS = 12
FUEL_SIGMA_SCALE = 1.65  # percentil 95


def _find_channel(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


_LAP_CHANNELS  = ["Session Lap Count", "SessionLapCount", "Lap", "LapNumber",
                  "Lap Number", "LapCount", "session_lap_count"]
_DIST_CHANNELS = ["Distance", "Dist", "LapDistance", "lap_distance"]


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
            reset = seg["Distance"] - seg["Distance"].iloc[0]
            if reset.max() > 10.0:
                seg["Distance"] = reset
                return seg
        # Distance absent or flat (all-zero CSV column) — synthesize from Speed×time
        time_ch = next(
            (c for c in ["LR Sample Clock", "HR Sample Clock", "MR Sample Clock"]
             if c in seg.columns),
            None,
        )
        if "Speed" in seg.columns and time_ch:
            spd = pd.to_numeric(seg["Speed"], errors="coerce").fillna(0) / 3.6
            t = pd.to_numeric(seg[time_ch], errors="coerce").ffill().bfill()
            dt = t.diff().fillna(0).clip(lower=0, upper=2.0)
            seg["Distance"] = (spd * dt).cumsum()
        elif "Distance" in seg.columns:
            seg["Distance"] = seg["Distance"] - seg["Distance"].iloc[0]
        return seg

    lap_col = _find_channel(df, _LAP_CHANNELS)
    if lap_col is not None:
        try:
            lap_nums = df[lap_col].fillna(-1).astype(int)
            unique_laps = sorted(n for n in lap_nums.unique() if n >= 0)
            dfs = [_reset_distance(df[lap_nums == n].reset_index(drop=True)) for n in unique_laps]
            dfs = [d for d in dfs if len(d) >= 10]
            if len(dfs) >= 2:
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
            logger.info("Segmentación por reset de distancia: %d vueltas", len(dfs))
            return dfs

    raise ValueError(
        "No se detectaron múltiples vueltas en el CSV. "
        "Asegúrate de que el archivo de sesión incluya el canal 'Session Lap Count' "
        "o que la distancia se reinicie en cada vuelta."
    )


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
        t_col = _find_channel(df, ["LapTime", "Time", "LR Sample Clock", "HR Sample Clock", "MR Sample Clock"])
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
            g_sum = np.sqrt(df[lat]**2 + df[lon]**2)
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


def analizar_degradacion_stint(df_laps):
    """
    Linear regression of lap time and G-sum vs lap number.
    Projects N_FUTURE_LAPS laps forward.
    Returns dict with trend, actual, and projected data.
    """
    valid = df_laps[_racing_laps_mask(df_laps)]
    if len(valid) < 3:
        return {"available": False}

    X = valid[["lap_number"]].values
    y = valid["lap_time_s"].values

    model = LinearRegression().fit(X, y)
    tasa = float(model.coef_[0])

    y_pred = model.predict(X)
    ss_res = float(np.sum((y - y_pred)**2))
    ss_tot = float(np.sum((y - y.mean())**2))
    r2 = round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else 0.0

    last_lap = int(valid["lap_number"].max())
    future_laps = list(range(last_lap + 1, last_lap + N_FUTURE_LAPS + 1))
    future_X = np.array(future_laps).reshape(-1, 1)

    result = {
        "available":       True,
        "tasa_s_per_lap":  round(tasa, 4),
        "r_squared":       r2,
        "actual_laps":     valid["lap_number"].tolist(),
        "actual_times":    [round(float(t), 3) for t in y],
        "trend_laps":      valid["lap_number"].tolist(),
        "trend_times":     [round(float(t), 3) for t in y_pred],
        "projected_laps":  future_laps,
        "projected_times": [round(float(t), 3) for t in model.predict(future_X)],
    }

    valid_g = df_laps[_racing_laps_mask(df_laps)].dropna(subset=["max_g_sum"])
    if len(valid_g) >= 3:
        mg = LinearRegression().fit(valid_g[["lap_number"]].values, valid_g["max_g_sum"].values)
        result["grip_tasa_per_lap"] = round(float(mg.coef_[0]), 4)
        result["grip_trend"]        = [round(float(v), 3) for v in mg.predict(valid_g[["lap_number"]].values)]
        result["grip_projected"]    = [round(float(v), 3) for v in mg.predict(future_X)]
        result["grip_actual_laps"]  = valid_g["lap_number"].tolist()
        result["grip_actual"]       = [round(float(v), 3) for v in valid_g["max_g_sum"].values]

    return result


def calcular_estrategia_combustible(df_laps):
    """
    Computes per-lap consumption, std, and safe pit window (95th percentile).
    """
    valid = df_laps[_racing_laps_mask(df_laps)].dropna(subset=["fuel_burned"])
    if valid.empty or valid["fuel_burned"].abs().sum() < 0.01:
        return {"available": False}

    consumo_medio = float(valid["fuel_burned"].mean())
    consumo_std   = float(valid["fuel_burned"].std()) if len(valid) > 1 else 0.0
    combustible_actual = float(df_laps["fuel_end"].dropna().iloc[-1]) if not df_laps["fuel_end"].isna().all() else 0.0

    consumo_conservador = consumo_medio + FUEL_SIGMA_SCALE * consumo_std if len(valid) > 3 else consumo_medio
    consumo_optimista   = max(0.01, consumo_medio - consumo_std * 0.5)

    vueltas_min = int(combustible_actual // consumo_conservador) if consumo_conservador > 0 else 0
    vueltas_max = int(combustible_actual // consumo_optimista)   if consumo_optimista   > 0 else 0
    vuelta_actual = int(df_laps["lap_number"].max())

    return {
        "available":             True,
        "consumo_medio_l":       round(consumo_medio, 3),
        "consumo_std_l":         round(consumo_std, 3),
        "combustible_actual_l":  round(combustible_actual, 2),
        "vueltas_restantes_min": vueltas_min,
        "vueltas_restantes_max": vueltas_max,
        "pit_window":            [max(0, vuelta_actual + vueltas_min - 1), vuelta_actual + vueltas_max],
        "fuel_per_lap":          valid[["lap_number", "fuel_burned"]].to_dict(orient="records"),
    }


def simular_tiempos_stint(df_laps, degradacion, seed=42):
    """
    Monte Carlo projection using real observed lap time variance.
    Returns P10/P25/P50/P75/P90 bands — reproducible with seed.
    """
    valid = df_laps[_racing_laps_mask(df_laps)]
    if len(valid) < 3 or not degradacion.get("available"):
        return {"available": False}

    rng = np.random.default_rng(seed)
    tasa = degradacion["tasa_s_per_lap"]
    sigma_real = float(valid["lap_time_s"].std())
    ultimo_tiempo = float(valid["lap_time_s"].iloc[-1])
    n_future = N_FUTURE_LAPS
    last_lap = int(valid["lap_number"].max())

    sims = np.zeros((N_SIMULATIONS, n_future))
    for s in range(N_SIMULATIONS):
        t = ultimo_tiempo
        for lap in range(n_future):
            t += tasa
            noise = rng.normal(0, sigma_real)
            noise = max(noise, -sigma_real * 0.5)
            sims[s, lap] = t + noise

    future_laps = list(range(last_lap + 1, last_lap + n_future + 1))
    return {
        "available":    True,
        "future_laps":  future_laps,
        "sigma_real_s": round(sigma_real, 3),
        "p10":  [round(float(v), 3) for v in np.percentile(sims, 10,  axis=0)],
        "p25":  [round(float(v), 3) for v in np.percentile(sims, 25,  axis=0)],
        "p50":  [round(float(v), 3) for v in np.percentile(sims, 50,  axis=0)],
        "p75":  [round(float(v), 3) for v in np.percentile(sims, 75,  axis=0)],
        "p90":  [round(float(v), 3) for v in np.percentile(sims, 90,  axis=0)],
    }
