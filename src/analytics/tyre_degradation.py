"""
Tyre degradation prediction via Ridge polynomial regression.

Estimates per-lap wear progression from thermal stress, lateral/longitudinal
G-loads, and lap number. Projects remaining useful laps before a performance
cliff and provides axle-level wear asymmetry.
"""
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Channel name candidates ---------------------------------------------------
_TYRE_CORE: dict = {
    # iRacing native: LFtempCM/LFtempM = centre-strip (most representative)
    # MoTeC export names: "Tyre Temp FL Centre / Inner / Outer"
    'FL': ['Tyre Temp FL Centre', 'LFtempCM', 'LFtempM',
           'TyreTempCore_FL', 'Tyre Temp Core FL', 'TyreTempFL', 'Tyre Temp FL',
           'Tyre Temp FL Inner', 'LFtempCR', 'LFtempR', 'LFtempCL', 'LFtempL'],
    'FR': ['Tyre Temp FR Centre', 'RFtempCM', 'RFtempM',
           'TyreTempCore_FR', 'Tyre Temp Core FR', 'TyreTempFR', 'Tyre Temp FR',
           'Tyre Temp FR Inner', 'RFtempCL', 'RFtempL', 'RFtempCR', 'RFtempR'],
    'RL': ['Tyre Temp RL Centre', 'LRtempCM', 'LRtempM',
           'TyreTempCore_RL', 'Tyre Temp Core RL', 'TyreTempRL', 'Tyre Temp RL',
           'Tyre Temp RL Inner', 'LRtempCR', 'LRtempR', 'LRtempCL', 'LRtempL'],
    'RR': ['Tyre Temp RR Centre', 'RRtempCM', 'RRtempM',
           'TyreTempCore_RR', 'Tyre Temp Core RR', 'TyreTempRR', 'Tyre Temp RR',
           'Tyre Temp RR Inner', 'RRtempCL', 'RRtempL', 'RRtempCR', 'RRtempR'],
}
_TYRE_PRES: dict = {
    'FL': ['Tyre Pres FL', 'LFpressure', 'LFcoldPressure', 'TyrePres_FL'],
    'FR': ['Tyre Pres FR', 'RFpressure', 'RFcoldPressure', 'TyrePres_FR'],
    'RL': ['Tyre Pres RL', 'LRpressure', 'LRcoldPressure', 'TyrePres_RL'],
    'RR': ['Tyre Pres RR', 'RRpressure', 'RRcoldPressure', 'TyrePres_RR'],
}
_LAT_G  = ['LateralG', 'Lateral G', 'G Force Lat', 'LatAccel', 'LateralAcc', 'Lateral Acc']
_LONG_G = ['LongitudinalG', 'Longitudinal G', 'G Force Long', 'LongAccel',
           'LongitudinalAcc', 'Longitudinal Acc']
_SPEED  = ['Speed', 'Ground Speed', 'GPS Speed', 'VehicleSpeed']

_OPT_MIN = 75.0   # °C — lower bound of optimal tyre window
_OPT_MAX = 100.0  # °C — upper bound
_CLIFF_S = 1.5    # seconds — lap-time degradation threshold for "cliff"


def _col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _lap_features(df) -> dict:
    """Extract wear-proxy features for one lap DataFrame."""
    feat = {}

    for pos, cands in _TYRE_CORE.items():
        ch = _col(df, cands)
        key = pos.lower()
        if ch:
            vals = df[ch].dropna()
            if len(vals) > 5:
                feat[f'temp_{key}']   = float(vals.mean())
                feat[f'stress_{key}'] = float(((vals < _OPT_MIN) | (vals > _OPT_MAX)).mean())
            else:
                feat[f'temp_{key}']   = np.nan
                feat[f'stress_{key}'] = np.nan
        else:
            feat[f'temp_{key}']   = np.nan
            feat[f'stress_{key}'] = np.nan

    for pos, cands in _TYRE_PRES.items():
        ch = _col(df, cands)
        key = pos.lower()
        if ch:
            vals = df[ch].dropna()
            feat[f'pres_{key}'] = float(vals.mean()) if len(vals) > 5 else np.nan
        else:
            feat[f'pres_{key}'] = np.nan

    lat_ch = _col(df, _LAT_G)
    feat['mean_lat_g'] = float(df[lat_ch].abs().dropna().mean()) if lat_ch else np.nan

    long_ch = _col(df, _LONG_G)
    if long_ch:
        v = df[long_ch].dropna()
        neg = v[v < -0.1]
        feat['mean_brake_g'] = float(neg.abs().mean()) if len(neg) else 0.0
    else:
        feat['mean_brake_g'] = np.nan

    spd_ch = _col(df, _SPEED)
    feat['mean_speed'] = float(df[spd_ch].dropna().mean()) if spd_ch else np.nan

    return feat


def predecir_degradacion_neumatico(dfs: list, df_laps) -> dict:
    """
    Train a polynomial Ridge regression on session lap data to predict
    tyre wear state and project remaining useful laps.

    Returns dict with keys:
        available, wear_pct, remaining_laps, current_delta_s,
        degradation_rate_s_per_lap, n_laps_analyzed,
        top_wear_factors, lap_data, projection,
        front_temp_trend_c_per_lap, rear_temp_trend_c_per_lap,
        left_mean_temp, right_mean_temp, tyre_temps_available
    """
    try:
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import PolynomialFeatures, StandardScaler
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        import pandas as pd
    except ImportError:
        logger.warning("tyre_degradation: scikit-learn not found — skipped")
        return {"available": False, "reason": "scikit-learn not installed"}

    # ── Filter flying laps ──────────────────────────────────────────────────
    if 'is_pit_lap' in df_laps.columns:
        flying = df_laps[~df_laps['is_pit_lap'] & df_laps['lap_time_s'].notna()]
    else:
        flying = df_laps[df_laps['lap_time_s'].notna()]

    if len(flying) < 3:
        return {"available": False, "reason": "fewer than 3 flying laps"}

    lap_times = flying['lap_time_s'].values.astype(float)
    best_time = float(np.nanmin(lap_times))
    if best_time <= 0:
        return {"available": False, "reason": "invalid lap times"}

    lap_nums = (
        flying['lap_number'].values.astype(float)
        if 'lap_number' in flying.columns
        else np.arange(1, len(flying) + 1, dtype=float)
    )

    # ── Build per-lap feature table ─────────────────────────────────────────
    records = []
    for i, (row_idx, _) in enumerate(flying.iterrows()):
        df_idx = list(df_laps.index).index(row_idx) if row_idx in df_laps.index else i
        if df_idx >= len(dfs):
            df_idx = i
        if i >= len(dfs):
            break
        feats = _lap_features(dfs[df_idx] if df_idx < len(dfs) else dfs[i])
        feats['lap_number']    = float(lap_nums[i])
        feats['lap_time_s']    = float(lap_times[i])
        feats['delta_vs_best'] = float(lap_times[i] - best_time)
        records.append(feats)

    if len(records) < 3:
        return {"available": False, "reason": "insufficient data after extraction"}

    rec_df = pd.DataFrame(records)
    feat_cols = [c for c in rec_df.columns if c not in ('lap_time_s', 'delta_vs_best')]
    # Drop entirely-NaN columns — sklearn imputer emits a warning and skips them anyway
    feat_cols = [c for c in feat_cols if rec_df[c].notna().any()]
    if not feat_cols:
        feat_cols = ['lap_number']   # always available fallback

    X = rec_df[feat_cols].values.astype(float)
    y = rec_df['delta_vs_best'].values

    # ── Fit model ───────────────────────────────────────────────────────────
    degree = 2 if len(records) >= 6 else 1
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter('ignore')
        pipeline = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler',  StandardScaler()),
            ('poly',    PolynomialFeatures(degree=degree, include_bias=False)),
            ('model',   Ridge(alpha=1.0)),
        ])
        pipeline.fit(X, y)

    # ── Linear trend on delta (for projection) ──────────────────────────────
    lap_arr    = rec_df['lap_number'].values.astype(float)
    delta_arr  = rec_df['delta_vs_best'].values
    coeffs     = np.polyfit(lap_arr, delta_arr, deg=1) if len(lap_arr) >= 2 else [0.0, 0.0]
    slope      = float(coeffs[0])
    intercept  = float(coeffs[1])

    current_lap   = float(lap_arr[-1])
    current_delta = float(delta_arr[-1])

    # ── Remaining laps to cliff ─────────────────────────────────────────────
    future_laps = np.arange(current_lap + 1, current_lap + 41)
    proj_deltas = slope * future_laps + intercept

    remaining_laps: object = ">40"
    for fl, fd in zip(future_laps, proj_deltas):
        if fd >= _CLIFF_S:
            remaining_laps = int(fl - current_lap)
            break

    # Wear state 0-100%
    max_scale  = max(_CLIFF_S, float(np.nanmax(delta_arr)) * 1.2, 0.3)
    wear_pct   = min(100.0, max(0.0, current_delta / max_scale * 100.0))

    # ── Feature importance via correlation with delta ───────────────────────
    imp = {}
    for j, col in enumerate(feat_cols):
        vals = rec_df[col].fillna(rec_df[col].median()).values
        if np.nanstd(vals) > 0 and not np.all(np.isnan(vals)):
            corr = float(np.corrcoef(vals, delta_arr)[0, 1])
            if not np.isnan(corr):
                imp[col] = abs(corr)
    top_factors = sorted(imp.items(), key=lambda x: -x[1])[:6]

    # ── Per-lap chart data ──────────────────────────────────────────────────
    lap_data = []
    for i in range(len(records)):
        ln = float(rec_df['lap_number'].iloc[i])
        lap_data.append({
            "lap":       int(ln),
            "delta":     round(float(delta_arr[i]), 3),
            "trend":     round(float(slope * ln + intercept), 3),
        })

    projection = [
        {
            "lap":       int(fl),
            "projected": round(float(fd), 3),
            "cliff":     _CLIFF_S,
        }
        for fl, fd in zip(future_laps[:25], proj_deltas[:25])
    ]

    # ── Axle / side temp trends ─────────────────────────────────────────────
    def _temp_trend(cols):
        valid = [c for c in cols if c in rec_df.columns and not rec_df[c].isna().all()]
        if not valid or len(lap_arr) < 2:
            return None
        temps = rec_df[valid].mean(axis=1).bfill().ffill().values
        return float(np.polyfit(lap_arr, temps, 1)[0])

    front_trend = _temp_trend(['temp_fl', 'temp_fr'])
    rear_trend  = _temp_trend(['temp_rl', 'temp_rr'])

    def _mean_temp(cols):
        valid = [c for c in cols if c in rec_df.columns]
        if not valid:
            return None
        v = rec_df[valid].values.flatten()
        v = v[~np.isnan(v)]
        return round(float(np.mean(v)), 1) if len(v) else None

    left_mean  = _mean_temp(['temp_fl', 'temp_rl'])
    right_mean = _mean_temp(['temp_fr', 'temp_rr'])

    tyre_temps_available = any(
        f'temp_{p}' in rec_df.columns and not rec_df[f'temp_{p}'].isna().all()
        for p in ['fl', 'fr', 'rl', 'rr']
    )

    logger.info(
        "tyre_degradation: wear=%.1f%%, remaining=%s, slope=%.4fs/lap, n=%d",
        wear_pct, remaining_laps, slope, len(records),
    )
    return {
        "available":                    True,
        "wear_pct":                     round(wear_pct, 1),
        "remaining_laps":               remaining_laps,
        "current_delta_s":              round(current_delta, 3),
        "cliff_threshold_s":            _CLIFF_S,
        "degradation_rate_s_per_lap":   round(slope, 4),
        "n_laps_analyzed":              len(records),
        "top_wear_factors":             [{"factor": k, "correlation": round(v, 3)} for k, v in top_factors],
        "lap_data":                     lap_data,
        "projection":                   projection,
        "front_temp_trend_c_per_lap":   round(front_trend, 3) if front_trend is not None else None,
        "rear_temp_trend_c_per_lap":    round(rear_trend, 3) if rear_trend is not None else None,
        "left_mean_temp":               left_mean,
        "right_mean_temp":              right_mean,
        "tyre_temps_available":         tyre_temps_available,
    }
