"""
Tyre degradation prediction via Ridge polynomial regression.

Estimates per-lap wear progression from thermal stress, lateral/longitudinal
G-loads, and lap number. Projects remaining useful laps before a performance
cliff and provides axle-level wear asymmetry.
"""
import logging

from src.i18n import _ as _tr
import numpy as np

logger = logging.getLogger(__name__)

# Channel name candidates ---------------------------------------------------
_TYRE_CORE: dict = {
    # iRacing native: LFtempCM/LFtempM = centre-strip (most representative)
    # MoTeC export names: "Tyre Temp FL Centre / Inner / Outer"
    'FL': ['TyreTempMiddleFL', 'TyreTempCoreFL', 'Tyre Temp FL Centre', 'LFtempCM', 'LFtempM',
           'TyreTempCore_FL', 'Tyre Temp Core FL', 'TyreTempFL', 'Tyre Temp FL',
           'Tyre Temp FL Inner', 'LFtempCR', 'LFtempR', 'LFtempCL', 'LFtempL'],
    'FR': ['TyreTempMiddleFR', 'TyreTempCoreFR', 'Tyre Temp FR Centre', 'RFtempCM', 'RFtempM',
           'TyreTempCore_FR', 'Tyre Temp Core FR', 'TyreTempFR', 'Tyre Temp FR',
           'Tyre Temp FR Inner', 'RFtempCL', 'RFtempL', 'RFtempCR', 'RFtempR'],
    'RL': ['TyreTempMiddleRL', 'TyreTempCoreRL', 'Tyre Temp RL Centre', 'LRtempCM', 'LRtempM',
           'TyreTempCore_RL', 'Tyre Temp Core RL', 'TyreTempRL', 'Tyre Temp RL',
           'Tyre Temp RL Inner', 'LRtempCR', 'LRtempR', 'LRtempCL', 'LRtempL'],
    'RR': ['TyreTempMiddleRR', 'TyreTempCoreRR', 'Tyre Temp RR Centre', 'RRtempCM', 'RRtempM',
           'TyreTempCore_RR', 'Tyre Temp Core RR', 'TyreTempRR', 'Tyre Temp RR',
           'Tyre Temp RR Inner', 'RRtempCL', 'RRtempL', 'RRtempCR', 'RRtempR'],
}
_TYRE_PRES: dict = {
    'FL': ['TyrePressFL', 'Tyre Pres FL', 'LFpressure', 'LFcoldPressure', 'TyrePres_FL'],
    'FR': ['TyrePressFR', 'Tyre Pres FR', 'RFpressure', 'RFcoldPressure', 'TyrePres_FR'],
    'RL': ['TyrePressRL', 'Tyre Pres RL', 'LRpressure', 'LRcoldPressure', 'TyrePres_RL'],
    'RR': ['TyrePressRR', 'Tyre Pres RR', 'RRpressure', 'RRcoldPressure', 'TyrePres_RR'],
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


_WEAR_RATE_CHANNELS = ['AID Tire Wear Rate', 'AID Tyre Wear Rate', 'Tire Wear Rate', 'Tyre Wear Rate',
                       'TyreWearRate', 'TireWearRate']
_WEAR_STATE_PREFIXES = ('tire rubber grip', 'tyre rubber grip', 'tire wear', 'tyre wear',
                        'tirewear', 'tyrewear', 'tire life', 'tyre life', 'tirelife', 'tyrelife', 'tyregrip')
_WEAR_CONST_RANGE = 0.05   # channel range below this over the whole session == constant
MIN_LAPS_FOR_FACTORS = 6   # correlations / thermal trends need at least this many laps


def detect_wear_tracking(dfs: list) -> dict:
    """
    Decide whether the simulator was actually modelling tyre wear.
    Returns {"active": True|False|None, "evidence": str}. None = no wear channel found
    (unknown: keep going, but the result is flagged accordingly).
    """
    import pandas as pd
    rate_seen, state_ranges = [], []
    for df in dfs:
        for c in df.columns:
            lc = str(c).lower()
            if c in _WEAR_RATE_CHANNELS:
                v = pd.to_numeric(df[c], errors='coerce').dropna()
                if len(v):
                    rate_seen.append((c, float(v.abs().max())))
            elif lc.startswith(_WEAR_STATE_PREFIXES):
                v = pd.to_numeric(df[c], errors='coerce').dropna()
                if len(v):
                    state_ranges.append((c, float(v.min()), float(v.max())))
    if rate_seen and max(r for _, r in rate_seen) <= 1e-9:
        return {"active": False, "evidence": f"{rate_seen[0][0]} == 0 for the whole session"}
    if state_ranges:
        by_ch: dict = {}
        for c, lo, hi in state_ranges:
            a, b = by_ch.get(c, (lo, hi))
            by_ch[c] = (min(a, lo), max(b, hi))
        if all((hi - lo) < _WEAR_CONST_RANGE for lo, hi in by_ch.values()):
            c0 = next(iter(by_ch))
            return {"active": False, "evidence": f"{c0} constant ({by_ch[c0][0]:g}) across the session"}
        return {"active": True, "evidence": "wear/grip channel varies across the session"}
    if rate_seen:
        return {"active": True, "evidence": f"{rate_seen[0][0]} > 0"}
    return {"active": None, "evidence": "no wear channel in the data"}


_GRIP_LEVELS = ((0.02, "none"), (0.15, "minimal"), (0.5, "moderate"))


def measure_rubber_grip(dfs: list) -> dict:
    """
    Wear measured by the simulator itself: the rubber-grip channel (% of the tyre grip left) per lap and
    tyre. Independent of lap times, so spins, traffic or fuel burn cannot hide it.
    ``{"available": False}`` when the log has no such channel or it never varies.
    """
    import pandas as pd
    names = {w: (f"TyreGrip{w}", f"Tire Rubber Grip {w}", f"Tyre Rubber Grip {w}") for w in ("FL", "FR", "RL", "RR")}
    per_lap, firsts, lasts = [], {}, {}
    for i, df in enumerate(dfs):
        row = {"lap": i + 1}
        for w, cands in names.items():
            col = next((c for c in cands if c in df.columns), None)
            if col is None:
                continue
            v = pd.to_numeric(df[col], errors="coerce").dropna()
            if v.empty:
                continue
            if float(v.max()) <= 1.5:
                v = v * 100.0
            row[w] = float(v.mean())
            firsts.setdefault(w, float(v.iloc[0]))
            lasts[w] = float(v.iloc[-1])
        if len(row) > 1:
            per_lap.append(row)
    if len(per_lap) < 2 or not firsts:
        return {"available": False}
    tyres = sorted(firsts)
    mean_lap = np.array([np.mean([r[w] for w in tyres if w in r]) for r in per_lap])
    laps = np.array([r["lap"] for r in per_lap], dtype=float)
    start = float(np.mean([firsts[w] for w in tyres]))
    end = float(np.mean([lasts[w] for w in tyres]))
    loss = start - end
    per_lap_loss = float(-np.polyfit(laps, mean_lap, 1)[0]) if len(laps) >= 3 else loss / max(1.0, laps[-1] - laps[0] + 1)
    if float(np.ptp(mean_lap)) < 1e-4 and abs(loss) < 1e-4:
        return {"available": False}
    level = "high"
    for limit, name in _GRIP_LEVELS:
        if per_lap_loss < limit:
            level = name
            break
    return {"available": True, "start_pct": round(start, 2), "end_pct": round(end, 2), "loss_pct": round(loss, 2),
            "loss_pct_per_lap": round(per_lap_loss, 3), "n_laps": len(per_lap), "level": level,
            "per_tyre": {w: {"start_pct": round(firsts[w], 2), "end_pct": round(lasts[w], 2),
                             "loss_pct": round(firsts[w] - lasts[w], 2)} for w in tyres},
            "laps": [{"lap": int(l), "grip_pct": round(float(g), 3)} for l, g in zip(laps, mean_lap)]}


def _wear_rate_value(dfs: list):
    import pandas as pd
    for df in dfs:
        for c in df.columns:
            if c in _WEAR_RATE_CHANNELS:
                v = pd.to_numeric(df[c], errors="coerce").dropna()
                if len(v):
                    return round(float(v.max()), 2)
    return None


def _grip_reason(grip: dict, wear_rate) -> str:
    key = {"none": "tyre_grip_none", "minimal": "tyre_grip_minimal"}.get(grip["level"], "tyre_grip_measured")
    return _tr(key, loss=grip["loss_pct"], per_lap=grip["loss_pct_per_lap"], n=grip["n_laps"],
               rate=("" if wear_rate is None else f" (x{wear_rate:g})"))


def predecir_degradacion_neumatico(dfs: list, df_laps) -> dict:
    """
    Tyre degradation estimate, consistent with the stint trend (analizar_degradacion_stint).

    - If the session has no tyre wear (wear-rate channel 0 / rubber grip constant) nothing is
      computed: available=False, wear_tracking=False.
    - Degradation slope is >= 0 (a negative fit is fuel / track evolution / noise and is
      reported separately in track_evolution_s_per_lap).
    - Needs MIN_LAPS_FOR_TREND valid laps; factors and thermal trends need MIN_LAPS_FOR_FACTORS.
    - remaining_laps only if the degradation is positive AND its CI excludes zero.
    """
    import pandas as pd
    from src.analytics.stint import (analizar_degradacion_stint, _projection_laps,
                                     MIN_LAPS_FOR_TREND)

    wear = detect_wear_tracking(dfs)
    if wear["active"] is False:
        return {"available": False, "wear_tracking": False, "reason_code": "wear_inactive",
                "reason": _tr("tyre_wear_inactive"), "wear_evidence": wear["evidence"]}

    grip = measure_rubber_grip(dfs)
    wear_rate = _wear_rate_value(dfs)
    excluded = ([int(x) for x in df_laps.loc[df_laps["is_incident_lap"].fillna(False).astype(bool), "lap_number"]]
                if "is_incident_lap" in df_laps.columns else [])

    valid = _projection_laps(df_laps)
    n = len(valid)
    if n < MIN_LAPS_FOR_TREND:
        reason = _tr("tyre_insufficient_laps", n=n, min=MIN_LAPS_FOR_TREND)
        if excluded:
            reason += " " + _tr("tyre_incident_laps_excluded", laps=", ".join(str(x) for x in excluded))
        if grip.get("available"):
            reason += " " + _grip_reason(grip, wear_rate)
        return {"available": False, "wear_tracking": wear["active"], "low_confidence": True,
                "confidence": "low", "n_laps_used": n, "reason_code": "insufficient_sample",
                "reason": reason, "grip_measured": grip, "wear_rate": wear_rate,
                "incident_laps_excluded": excluded}

    st = analizar_degradacion_stint(df_laps)
    if not st.get("available"):
        return {"available": False, "wear_tracking": wear["active"], "reason": _tr("unavail_few_flying_laps_3")}

    lap_arr = valid['lap_number'].values.astype(float)
    times = valid['lap_time_s'].values.astype(float)
    best_time = float(np.nanmin(times))
    delta_arr = times - best_time

    fuel_eff = float(st["fuel_effect_s_per_lap"])
    total = float(st["tasa_s_per_lap"])
    deg = max(0.0, total - fuel_eff)
    track_evo = min(0.0, total - fuel_eff)
    se = float(st["slope_se_s_per_lap"])
    ci = st.get("slope_ci")
    ci_lo_deg = (ci[0] - fuel_eff) if ci else None
    reliable = deg >= 0.01 and ci_lo_deg is not None and ci_lo_deg > 0

    anchor_lap = float(st["anchor_lap"])
    anchor_delta = float(st["anchor_time_s"]) - best_time
    last = float(lap_arr[-1])
    resid_sd = float(np.std(delta_arr - np.polyval(np.polyfit(lap_arr, delta_arr, 1), lap_arr), ddof=2))
    sigma = max(resid_sd, 0.25)

    future_laps = np.arange(last + 1, last + 41)
    proj = anchor_delta + deg * (future_laps - anchor_lap)
    band = 1.28 * np.sqrt((se * (future_laps - anchor_lap)) ** 2 + sigma ** 2)

    remaining_laps = None
    if reliable:
        remaining_laps = ">40"
        for fl, fd in zip(future_laps, proj):
            if fd >= _CLIFF_S:
                remaining_laps = int(fl - last)
                break

    current_delta = float(delta_arr[-1])
    wear_pct = None
    if reliable:
        max_scale = max(_CLIFF_S, float(np.nanmax(delta_arr)) * 1.2, 0.3)
        wear_pct = round(min(100.0, max(0.0, current_delta / max_scale * 100.0)), 1)

    lap_data = []
    for ln, d in zip(lap_arr, delta_arr):
        lap_data.append({"lap": int(ln), "delta": round(float(d), 3),
                         "trend": round(float(anchor_delta + deg * (ln - anchor_lap)), 3)})
    projection = [{"lap": int(fl), "projected": round(float(fd), 3),
                   "p10": round(float(max(0.0, fd - b)), 3), "p90": round(float(fd + b), 3),
                   "cliff": _CLIFF_S}
                  for fl, fd, b in zip(future_laps[:25], proj[:25], band[:25])]

    # ── Per-lap features (factors / thermal) ────────────────────────────────
    records = []
    for row_idx, ln, dl in zip(valid.index, lap_arr, delta_arr):
        i = int(row_idx)
        if i >= len(dfs):
            continue
        f = _lap_features(dfs[i])
        f['lap_number'] = float(ln)
        f['delta_vs_best'] = float(dl)
        records.append(f)
    rec_df = pd.DataFrame(records)

    top_factors, factors_reason = [], None
    front_trend = rear_trend = None
    thermal_reason = None
    if len(rec_df) >= MIN_LAPS_FOR_FACTORS:
        feat_cols = [c for c in rec_df.columns
                     if c not in ('delta_vs_best', 'lap_number', 'mean_speed') and rec_df[c].notna().any()]
        imp = {}
        for col in feat_cols:
            vals = rec_df[col].fillna(rec_df[col].median()).values
            if np.nanstd(vals) > 0:
                corr = float(np.corrcoef(vals, rec_df['delta_vs_best'].values)[0, 1])
                if not np.isnan(corr):
                    imp[col] = abs(corr)
        top_factors = sorted(imp.items(), key=lambda x: -x[1])[:6]

        def _temp_trend(cols):
            valid_c = [c for c in cols if c in rec_df.columns and not rec_df[c].isna().all()]
            if not valid_c:
                return None
            temps = rec_df[valid_c].mean(axis=1).bfill().ffill().values
            return float(np.polyfit(rec_df['lap_number'].values, temps, 1)[0])
        front_trend = _temp_trend(['temp_fl', 'temp_fr'])
        rear_trend = _temp_trend(['temp_rl', 'temp_rr'])
    else:
        factors_reason = thermal_reason = _tr("tyre_factors_few_laps", n=len(rec_df), min=MIN_LAPS_FOR_FACTORS)

    def _mean_temp(cols):
        cols = [c for c in cols if c in rec_df.columns]
        v = rec_df[cols].values.flatten() if (len(rec_df) and cols) else np.array([])
        v = v[~np.isnan(v)]
        return round(float(np.mean(v)), 1) if len(v) else None

    tyre_temps_available = bool(len(rec_df)) and any(
        f'temp_{p}' in rec_df.columns and not rec_df[f'temp_{p}'].isna().all()
        for p in ['fl', 'fr', 'rl', 'rr'])

    if reliable:
        reason_code, reason = None, None
    else:
        reason_code, reason = "no_detectable_degradation", _tr("tyre_no_degradation")
        if grip.get("available"):
            reason += " " + _grip_reason(grip, wear_rate)
            if grip["level"] in ("moderate", "high"):
                reason_code = "wear_measured_not_in_times"
        if excluded:
            reason += " " + _tr("tyre_incident_laps_excluded", laps=", ".join(str(x) for x in excluded))

    logger.info("tyre_degradation: deg=%.4f s/lap reliable=%s n=%d", deg, reliable, n)
    return {
        "available":                    True,
        "wear_tracking":                wear["active"],
        "wear_evidence":                wear["evidence"],
        "grip_measured":                grip,
        "wear_rate":                    wear_rate,
        "incident_laps_excluded":       excluded,
        "wear_pct":                     wear_pct,
        "remaining_laps":               remaining_laps,
        "current_delta_s":              round(current_delta, 3),
        "cliff_threshold_s":            _CLIFF_S,
        "degradation_rate_s_per_lap":   round(deg, 4),
        "degradation_detected":         bool(reliable),
        "track_evolution_s_per_lap":    round(track_evo, 4),
        "fuel_effect_s_per_lap":        round(fuel_eff, 4),
        "raw_slope_s_per_lap":          st.get("raw_slope_s_per_lap"),
        "slope_ci":                     ci,
        "confidence":                   st.get("confidence", "low"),
        "low_confidence":               bool(st.get("low_confidence")),
        "n_laps_used":                  n,
        "n_laps_analyzed":              n,
        "reason_code":                  reason_code,
        "reason":                       reason,
        "top_wear_factors":             [{"factor": k, "correlation": round(v, 3)} for k, v in top_factors],
        "wear_factors_reason":          factors_reason,
        "lap_data":                     lap_data,
        "projection":                   projection,
        "front_temp_trend_c_per_lap":   round(front_trend, 3) if front_trend is not None else None,
        "rear_temp_trend_c_per_lap":    round(rear_trend, 3) if rear_trend is not None else None,
        "temp_trend_reason":            thermal_reason,
        "left_mean_temp":               _mean_temp(['temp_fl', 'temp_rl']),
        "right_mean_temp":              _mean_temp(['temp_fr', 'temp_rr']),
        "tyre_temps_available":         tyre_temps_available,
    }
