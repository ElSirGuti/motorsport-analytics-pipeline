"""
Session-level telemetry analysis.

Analyses each flying lap individually using raw telemetry channels (no _Fast/_Slow
alignment needed). Results are aggregated across the session to produce the full
signal set required by analizar_setup_sesion():

  • Tyre temperatures — per corner (FL/FR/RL/RR), including inner/outer camber gradient
  • Brake fade         — efficiency ratio (brake pressure vs deceleration G)
  • Suspension         — roll front/rear, pitch, bottoming events
  • Aero/balance       — understeer/oversteer % from lateral G + yaw rate
  • Driver inputs      — nervousness (steer FFT), brake-throttle overlap
"""

import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.signal import welch

logger = logging.getLogger(__name__)

# ── Channel name candidates ───────────────────────────────────────────────────
# Covers iRacing (native + MoTeC export), ACTI/Assetto Corsa, generic MoTeC.
# iRacing exports via MoTeC use descriptive names; the loader already remaps
# some aliases (e.g. "G Force Lat" → "LateralG", "Lap Distance" → "Distance").

_SPEED_CH   = ["Speed", "Ground Speed", "GPS Speed", "VehicleSpeed"]
_BRAKE_CH   = ["Brake", "Brake Pedal Pos", "Brake Pressure", "BrakePressure",
               "Brake Pos"]
_THROTTLE_CH= ["Throttle", "Throttle Pos", "Throttle Position", "ThrottlePosition"]
_LONG_G_CH  = ["LongitudinalG", "Longitudinal G", "G Force Long",
               "LongAccel", "Longitudinal Accel", "LongG"]
_LAT_G_CH   = ["LateralG", "Lateral G", "G Force Lat", "LatAccel",
               "Lateral Accel", "LatG"]
_YAW_CH     = ["YawRate", "Gyro - Yaw Velocity", "Yaw Rate", "YawRateVehicle",
               "Yaw Rate Vehicle", "YawVelocity"]
_STEER_CH   = ["SteeringWheelAngle", "Steering Wheel Angle",
               "SteerAngle", "Steer Angle", "Steering Angle", "SteeringAngle"]

# iRacing tyre temps: LFtempCL/CM/CR = Center-Left/Middle/Right strip across tread
#   MoTeC export renames: "Tyre Temp FL Centre / Inner / Outer"
#   Inner  = towards car centre  → LFtempCR / RFtempCL
#   Centre = middle strip        → LFtempCM / RFtempCM
#   Outer  = kerb side           → LFtempCL / RFtempCR
_TYRE_SURF  = {   # best single-channel summary per corner (middle strip / average)
    "FL": ["Tyre Temp FL Centre", "LFtempCM", "LFtempM",
           "TyreTemp_FL", "Tyre Temp FL", "TyreTempFL"],
    "FR": ["Tyre Temp FR Centre", "RFtempCM", "RFtempM",
           "TyreTemp_FR", "Tyre Temp FR", "TyreTempFR"],
    "RL": ["Tyre Temp RL Centre", "LRtempCM", "LRtempM",
           "TyreTemp_RL", "Tyre Temp RL", "TyreTempRL"],
    "RR": ["Tyre Temp RR Centre", "RRtempCM", "RRtempM",
           "TyreTemp_RR", "Tyre Temp RR", "TyreTempRR"],
}
_TYRE_INNER = {   # inner edge (towards centre of car)
    "FL": ["Tyre Temp FL Inner", "LFtempCR", "LFtempR",
           "TyreTempInnerFL", "Tyre Temp Inner FL"],
    "FR": ["Tyre Temp FR Inner", "RFtempCL", "RFtempL",
           "TyreTempInnerFR", "Tyre Temp Inner FR"],
    "RL": ["Tyre Temp RL Inner", "LRtempCR", "LRtempR",
           "TyreTempInnerRL", "Tyre Temp Inner RL"],
    "RR": ["Tyre Temp RR Inner", "RRtempCL", "RRtempL",
           "TyreTempInnerRR", "Tyre Temp Inner RR"],
}
_TYRE_OUTER = {   # outer edge (towards kerb)
    "FL": ["Tyre Temp FL Outer", "LFtempCL", "LFtempL",
           "TyreTempOuterFL", "Tyre Temp Outer FL"],
    "FR": ["Tyre Temp FR Outer", "RFtempCR", "RFtempR",
           "TyreTempOuterFR", "Tyre Temp Outer FR"],
    "RL": ["Tyre Temp RL Outer", "LRtempCL", "LRtempL",
           "TyreTempOuterRL", "Tyre Temp Outer RL"],
    "RR": ["Tyre Temp RR Outer", "RRtempCR", "RRtempR",
           "TyreTempOuterRR", "Tyre Temp Outer RR"],
}
_TYRE_PRES = {    # tyre pressure (kPa in iRacing native, psi in MoTeC export)
    "FL": ["Tyre Pres FL", "LFpressure", "LFcoldPressure",
           "TyrePres_FL", "Tyre Pressure FL"],
    "FR": ["Tyre Pres FR", "RFpressure", "RFcoldPressure",
           "TyrePres_FR", "Tyre Pressure FR"],
    "RL": ["Tyre Pres RL", "LRpressure", "LRcoldPressure",
           "TyrePres_RL", "Tyre Pressure RL"],
    "RR": ["Tyre Pres RR", "RRpressure", "RRcoldPressure",
           "TyrePres_RR", "Tyre Pressure RR"],
}
_BRAKE_TEMP = {   # iRacing does not export brake disc temps; ACTI does
    "FL": ["BrakeTemp_FL", "Brake Temp FL", "BrakeTempFL", "Brake Disc Temp FL"],
    "FR": ["BrakeTemp_FR", "Brake Temp FR", "BrakeTempFR", "Brake Disc Temp FR"],
    "RL": ["BrakeTemp_RL", "Brake Temp RL", "BrakeTempRL", "Brake Disc Temp RL"],
    "RR": ["BrakeTemp_RR", "Brake Temp RR", "BrakeTempRR", "Brake Disc Temp RR"],
}
_SUSP = {         # shock deflection / suspension travel
    "FL": ["LFshockDefl", "Susp Pos FL", "Ride Height FL",
           "SuspTravelFL", "Susp Travel FL", "SuspensionTravelFL"],
    "FR": ["RFshockDefl", "Susp Pos FR", "Ride Height FR",
           "SuspTravelFR", "Susp Travel FR", "SuspensionTravelFR"],
    "RL": ["LRshockDefl", "Susp Pos RL", "Ride Height RL",
           "SuspTravelRL", "Susp Travel RL", "SuspensionTravelRL"],
    "RR": ["RRshockDefl", "Susp Pos RR", "Ride Height RR",
           "SuspTravelRR", "Susp Travel RR", "SuspensionTravelRR"],
}

# Tyre operating window (°C)
T_OPT_MIN, T_OPT_MAX = 80.0, 100.0

# Thresholds
BRAKE_THRESH    = 15.0   # % — ignore light braking
DECEL_THRESH    = 0.05   # g
FADE_DROP       = 0.15   # >15% drop from baseline = fade
BOTTOMING_PCT   = 0.90   # >90% of observed max travel = bottoming
STEER_FFT_WIN   = 256
OVERLAP_THRESH  = 5.0    # % for both brake and throttle simultaneously


# ── Generic helpers ───────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, candidates: list) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _window_status(t: float) -> str:
    if t < T_OPT_MIN - 15:
        return "fria"
    if t < T_OPT_MIN:
        return "suboptima"
    if t <= T_OPT_MAX:
        return "optima"
    if t <= T_OPT_MAX + 15:
        return "caliente"
    return "sobrecalentada"


# ── Per-lap analysis functions ────────────────────────────────────────────────

def _analyse_tyres_lap(df: pd.DataFrame) -> dict:
    """Extract tyre temperature stats from one lap."""
    result = {}
    for pos in ("FL", "FR", "RL", "RR"):
        surf_col   = _col(df, _TYRE_SURF[pos])
        inner_col  = _col(df, _TYRE_INNER[pos])
        outer_col  = _col(df, _TYRE_OUTER[pos])
        btemp_col  = _col(df, _BRAKE_TEMP[pos])
        pres_col   = _col(df, _TYRE_PRES[pos])

        vals = {}
        if surf_col:
            s = _num(df, surf_col).dropna()
            if len(s) >= 10:
                vals["surf_mean"] = float(s.mean())
                vals["surf_max"]  = float(s.max())
                vals["status"]    = _window_status(vals["surf_mean"])

        if pres_col:
            p = _num(df, pres_col).dropna()
            if len(p) >= 10:
                vals["pressure_mean"] = float(p.mean())
                vals["pressure_max"]  = float(p.max())
                vals["pressure_min"]  = float(p.min())

        if inner_col and outer_col:
            inn = _num(df, inner_col).dropna()
            out = _num(df, outer_col).dropna()
            if len(inn) >= 10 and len(out) >= 10:
                vals["inner_mean"] = float(inn.mean())
                vals["outer_mean"] = float(out.mean())
                vals["camber_grad"] = round(float(inn.mean()) - float(out.mean()), 1)

        if btemp_col:
            bt = _num(df, btemp_col).dropna()
            if len(bt) >= 10:
                vals["brake_temp_mean"] = float(bt.mean())
                vals["brake_temp_max"]  = float(bt.max())

        if vals:
            result[pos] = vals
    return result


def _analyse_brake_lap(df: pd.DataFrame) -> dict:
    """Compute brake efficiency ratio for one lap."""
    brake_col = _col(df, _BRAKE_CH)
    long_col  = _col(df, _LONG_G_CH)
    if not brake_col or not long_col:
        return {}

    brake = _num(df, brake_col)
    long_g = _num(df, long_col)
    if brake.isna().all() or long_g.isna().all():
        return {}

    braking_mask = (brake >= BRAKE_THRESH) & (long_g < -DECEL_THRESH)
    if braking_mask.sum() < 20:
        return {}

    denom = brake[braking_mask].clip(lower=0.01)
    eff   = (-long_g[braking_mask]) / (denom / 100.0)
    eff   = eff.clip(upper=eff.quantile(0.95))  # remove outliers

    # Baseline from first 30% of braking events (early in lap)
    n_base = max(int(len(eff) * 0.30), 10)
    baseline = float(eff.iloc[:n_base].mean())

    # Fade zones: contiguous windows where efficiency < baseline * (1 - FADE_DROP)
    threshold = baseline * (1 - FADE_DROP)
    fade_count  = int((eff < threshold).sum())
    fade_pct    = round(fade_count / len(eff) * 100, 1)
    mean_eff    = round(float(eff.mean()), 3)
    fade_severity = round(max(0.0, 1.0 - mean_eff / max(baseline, 0.01)), 3)

    return {
        "efficiency_mean": mean_eff,
        "baseline":        round(baseline, 3),
        "fade_pct":        fade_pct,
        "fade_severity":   fade_severity,
    }


def _analyse_suspension_lap(df: pd.DataFrame) -> dict:
    """Suspension roll, pitch and bottoming detection for one lap."""
    pos_data = {}
    for pos in ("FL", "FR", "RL", "RR"):
        col = _col(df, _SUSP[pos])
        if not col:
            continue
        s = _num(df, col).dropna()
        if len(s) < 20:
            continue
        travel_range = float(s.max() - s.min())
        if travel_range < 1.0:
            continue
        threshold = float(s.max()) * BOTTOMING_PCT
        pos_data[pos] = {
            "mean":          float(s.mean()),
            "max":           float(s.max()),
            "range":         travel_range,
            "bottoming_pct": round(float((s >= threshold).mean() * 100), 2),
        }

    if not pos_data:
        return {}

    result = {"corners": pos_data}
    fl = pos_data.get("FL", {}).get("mean") or 0
    fr = pos_data.get("FR", {}).get("mean") or 0
    rl = pos_data.get("RL", {}).get("mean") or 0
    rr = pos_data.get("RR", {}).get("mean") or 0

    if fl and fr:
        result["roll_f_mm"]   = round(abs(fl - fr), 2)
        result["max_roll_f"]  = round(max(
            pos_data.get("FL", {}).get("max", 0),
            pos_data.get("FR", {}).get("max", 0)), 2)
    if rl and rr:
        result["roll_r_mm"]   = round(abs(rl - rr), 2)
        result["max_roll_r"]  = round(max(
            pos_data.get("RL", {}).get("max", 0),
            pos_data.get("RR", {}).get("max", 0)), 2)
    if fl and fr and rl and rr:
        front_mean = (fl + fr) / 2
        rear_mean  = (rl + rr) / 2
        result["pitch_mm"]  = round(front_mean - rear_mean, 2)

    result["bottoming_events"] = sum(
        1 for v in pos_data.values() if v.get("bottoming_pct", 0) > 2.0
    )
    return result


def _analyse_inputs_lap(df: pd.DataFrame) -> dict:
    """Nervousness + throttle-brake overlap for one lap."""
    steer_col    = _col(df, _STEER_CH)
    brake_col    = _col(df, _BRAKE_CH)
    throttle_col = _col(df, _THROTTLE_CH)
    speed_col    = _col(df, _SPEED_CH)

    result = {}

    if steer_col:
        steer = _num(df, steer_col).ffill().fillna(0)
        # Rolling std of steer rate
        rate     = steer.diff().abs().fillna(0)
        smoothed = rate.rolling(80, center=True, min_periods=1).mean()
        p99      = float(smoothed.quantile(0.99)) or 1e-6
        nerv_series = (smoothed / p99).clip(0, 1)
        nerv_score  = round(float(nerv_series.mean()), 3)

        # FFT bands — estimate sample rate from speed if available
        if speed_col:
            spd_ms  = _num(df, speed_col).ffill().fillna(50) / 3.6
            n       = len(steer)
            dist    = df["Distance"].max() - df["Distance"].min() if "Distance" in df.columns else n
            avg_spd = float(spd_ms.mean()) if float(spd_ms.mean()) > 1 else 10.0
            sr      = avg_spd  # samples at ~1m spacing → effective Hz ≈ avg_speed_m/s
        else:
            sr = 10.0

        try:
            s = steer.values
            freqs, psd = welch(s, fs=sr, nperseg=min(STEER_FFT_WIN, len(s) // 2))
            total = float(np.trapz(psd, freqs)) or 1.0
            low  = float(np.trapz(psd[freqs < 0.5],  freqs[freqs < 0.5]))  / total
            mid  = float(np.trapz(psd[(freqs >= 0.5) & (freqs < 2.0)],
                                   freqs[(freqs >= 0.5) & (freqs < 2.0)])) / total
            high = float(np.trapz(psd[freqs >= 2.0], freqs[freqs >= 2.0])) / total
            result["nervousness"] = nerv_score
            result["fft_low"]     = round(low,  3)
            result["fft_mid"]     = round(mid,  3)
            result["fft_high"]    = round(high, 3)
        except Exception:
            result["nervousness"] = nerv_score

    if brake_col and throttle_col:
        brake    = _num(df, brake_col)
        throttle = _num(df, throttle_col)
        overlap_mask = (brake > OVERLAP_THRESH) & (throttle > OVERLAP_THRESH)
        result["overlap_pct"] = round(float(overlap_mask.mean() * 100), 1)

    return result


def _analyse_balance_lap(df: pd.DataFrame) -> dict:
    """Understeer/oversteer classification from LateralG + YawRate + Speed."""
    lat_col  = _col(df, _LAT_G_CH)
    yaw_col  = _col(df, _YAW_CH)
    spd_col  = _col(df, _SPEED_CH)
    str_col  = _col(df, _STEER_CH)

    if not lat_col or not spd_col:
        return {}

    speed   = _num(df, spd_col).ffill().fillna(0)
    lat_g   = _num(df, lat_col).ffill().fillna(0)

    # Only analyse when cornering (lat G significant)
    cornering = (lat_g.abs() > 0.2) & (speed > 40)
    if cornering.sum() < 20:
        return {}

    result = {"n_cornering_samples": int(cornering.sum())}

    if yaw_col:
        yaw  = _num(df, yaw_col).ffill().fillna(0)
        # Kinematic yaw rate from speed and lat G: ω_kin = (lat_g * 9.81) / speed_ms
        speed_ms   = (speed / 3.6).clip(lower=1.0)
        lat_ms2    = lat_g * 9.81
        yaw_kin    = lat_ms2 / speed_ms  # rad/s (kinematic, neutral steer)

        # Actual yaw rate — detect unit (rad/s or °/s)
        yaw_actual = yaw.copy()
        if yaw_actual.abs().max() > 5:  # likely °/s
            yaw_actual = yaw_actual * (np.pi / 180)

        # Body slip rate proxy: difference between actual and kinematic yaw
        delta_yaw = (yaw_actual - yaw_kin)[cornering]

        # Positive delta → actual yaw > kinematic → oversteer tendency
        # Negative delta → actual yaw < kinematic → understeer tendency
        us_pct = round(float((delta_yaw < -0.05).mean() * 100), 1)
        os_pct = round(float((delta_yaw >  0.05).mean() * 100), 1)
        result["understeer_pct"] = us_pct
        result["oversteer_pct"]  = os_pct
        result["neutral_pct"]    = round(100 - us_pct - os_pct, 1)
        result["balance_mean"]   = round(float(delta_yaw.mean()), 3)

    if str_col:
        steer = _num(df, str_col).ffill().fillna(0)
        # High steer angle in corners but low lateral G = understeer indicator
        # β proxy from steer saturation: steer RMS in corners
        steer_rms = round(float(np.sqrt((steer[cornering] ** 2).mean())), 2)
        result["steer_rms_cornering"] = steer_rms

    return result


# ── Session aggregation ───────────────────────────────────────────────────────

def analizar_telemetria_sesion(dfs: list, df_laps: pd.DataFrame) -> dict:
    """
    Run per-lap telemetry analysis across all flying laps and aggregate results.

    Args:
        dfs:     List of per-lap DataFrames (same order as df_laps rows).
        df_laps: Output of extraer_metricas_por_vuelta() (is_pit_lap, lap_time_s, etc.).

    Returns:
        Aggregated session-level telemetry dict consumed by analizar_setup_sesion().
    """
    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]

    if len(flying) < 1:
        return {"available": False}

    logger.info("session_telemetry: analizando %d vueltas volantes", len(flying))

    tyre_per_lap: list  = []
    brake_per_lap: list = []
    susp_per_lap: list  = []
    inputs_per_lap: list = []
    balance_per_lap: list = []

    for idx in flying.index:
        lap_df = dfs[idx]
        try:
            t = _analyse_tyres_lap(lap_df)
            if t:
                tyre_per_lap.append(t)
        except Exception as e:
            logger.debug("session_telemetry tyres idx=%d: %s", idx, e)

        try:
            b = _analyse_brake_lap(lap_df)
            if b:
                brake_per_lap.append(b)
        except Exception as e:
            logger.debug("session_telemetry brake idx=%d: %s", idx, e)

        try:
            s = _analyse_suspension_lap(lap_df)
            if s:
                susp_per_lap.append(s)
        except Exception as e:
            logger.debug("session_telemetry susp idx=%d: %s", idx, e)

        try:
            i = _analyse_inputs_lap(lap_df)
            if i:
                inputs_per_lap.append(i)
        except Exception as e:
            logger.debug("session_telemetry inputs idx=%d: %s", idx, e)

        try:
            bl = _analyse_balance_lap(lap_df)
            if bl:
                balance_per_lap.append(bl)
        except Exception as e:
            logger.debug("session_telemetry balance idx=%d: %s", idx, e)

    if not any([tyre_per_lap, brake_per_lap, susp_per_lap,
                inputs_per_lap, balance_per_lap]):
        logger.info("session_telemetry: sin canales de telemetría avanzada disponibles")
        return {"available": False}

    out: dict = {"available": True, "n_laps": len(flying)}

    # ── Tyres ─────────────────────────────────────────────────────────────────
    if tyre_per_lap:
        tyre_agg: dict = {}
        for pos in ("FL", "FR", "RL", "RR"):
            vals = [lap[pos] for lap in tyre_per_lap if pos in lap]
            if not vals:
                continue
            surf_means  = [v["surf_mean"]  for v in vals if "surf_mean"  in v]
            surf_maxes  = [v["surf_max"]   for v in vals if "surf_max"   in v]
            statuses    = [v["status"]     for v in vals if "status"     in v]
            camber_grads= [v["camber_grad"]for v in vals if "camber_grad"in v]
            btemp_means = [v["brake_temp_mean"] for v in vals if "brake_temp_mean" in v]
            inner_means = [v["inner_mean"] for v in vals if "inner_mean" in v]
            outer_means = [v["outer_mean"] for v in vals if "outer_mean" in v]

            entry: dict = {"n_laps": len(vals)}
            if surf_means:
                entry["mean_temp"]      = round(float(np.mean(surf_means)), 1)
                entry["max_temp"]       = round(float(np.max(surf_maxes)),  1)
                entry["status"]         = max(set(statuses), key=statuses.count)
            if camber_grads:
                entry["camber_gradient"]= round(float(np.mean(camber_grads)), 1)
            if inner_means and outer_means:
                entry["inner_mean"]     = round(float(np.mean(inner_means)), 1)
                entry["outer_mean"]     = round(float(np.mean(outer_means)), 1)
            if btemp_means:
                entry["brake_temp_mean"]= round(float(np.mean(btemp_means)), 1)
                entry["brake_temp_max"] = round(float(np.max(
                    [v["brake_temp_max"] for v in vals if "brake_temp_max" in v])), 1)
            tyre_agg[pos] = entry

        # Front/rear and left/right balance
        f_temps = [tyre_agg[p]["mean_temp"] for p in ("FL","FR") if p in tyre_agg and "mean_temp" in tyre_agg[p]]
        r_temps = [tyre_agg[p]["mean_temp"] for p in ("RL","RR") if p in tyre_agg and "mean_temp" in tyre_agg[p]]
        l_temps = [tyre_agg[p]["mean_temp"] for p in ("FL","RL") if p in tyre_agg and "mean_temp" in tyre_agg[p]]
        r_side  = [tyre_agg[p]["mean_temp"] for p in ("FR","RR") if p in tyre_agg and "mean_temp" in tyre_agg[p]]

        if f_temps and r_temps:
            tyre_agg["front_rear_delta"] = round(float(np.mean(f_temps)) - float(np.mean(r_temps)), 1)
        if l_temps and r_side:
            tyre_agg["left_right_delta"] = round(float(np.mean(l_temps)) - float(np.mean(r_side)), 1)

        out["tyre"] = tyre_agg

    # ── Brake fade ────────────────────────────────────────────────────────────
    if brake_per_lap:
        out["brake"] = {
            "mean_efficiency":    round(float(np.mean([b["efficiency_mean"] for b in brake_per_lap])), 3),
            "min_efficiency":     round(float(np.min([b["efficiency_mean"]  for b in brake_per_lap])), 3),
            "mean_fade_severity": round(float(np.mean([b["fade_severity"]   for b in brake_per_lap])), 3),
            "mean_fade_pct":      round(float(np.mean([b["fade_pct"]        for b in brake_per_lap])), 1),
            "n_laps":             len(brake_per_lap),
        }

    # ── Suspension ────────────────────────────────────────────────────────────
    if susp_per_lap:
        roll_f  = [s["roll_f_mm"]  for s in susp_per_lap if "roll_f_mm"  in s]
        roll_r  = [s["roll_r_mm"]  for s in susp_per_lap if "roll_r_mm"  in s]
        pitch   = [s["pitch_mm"]   for s in susp_per_lap if "pitch_mm"   in s]
        bev     = [s["bottoming_events"] for s in susp_per_lap if "bottoming_events" in s]
        max_rf  = [s["max_roll_f"] for s in susp_per_lap if "max_roll_f" in s]
        max_rr  = [s["max_roll_r"] for s in susp_per_lap if "max_roll_r" in s]

        susp_out: dict = {"n_laps": len(susp_per_lap)}
        if roll_f:
            susp_out["mean_roll_f"]     = round(float(np.mean(roll_f)), 2)
            susp_out["max_roll_f"]      = round(float(np.max(max_rf)),  2)
        if roll_r:
            susp_out["mean_roll_r"]     = round(float(np.mean(roll_r)), 2)
            susp_out["max_roll_r"]      = round(float(np.max(max_rr)),  2)
        if roll_f and roll_r:
            denom = float(np.mean(roll_r)) or 0.1
            susp_out["roll_ratio"]      = round(float(np.mean(roll_f)) / denom, 2)
        if pitch:
            susp_out["mean_pitch"]      = round(float(np.mean(pitch)),  2)
        if bev:
            susp_out["mean_bottoming_events"] = round(float(np.mean(bev)), 2)
            susp_out["max_bottoming_events"]  = int(np.max(bev))

        # Per-corner bottoming stats
        corner_bottoming: dict = {}
        for pos in ("FL", "FR", "RL", "RR"):
            pcts = [
                s["corners"][pos]["bottoming_pct"]
                for s in susp_per_lap
                if "corners" in s and pos in s["corners"]
            ]
            if pcts:
                corner_bottoming[pos] = round(float(np.mean(pcts)), 2)
        if corner_bottoming:
            susp_out["corner_bottoming_pct"] = corner_bottoming

        out["suspension"] = susp_out

    # ── Driver inputs ─────────────────────────────────────────────────────────
    if inputs_per_lap:
        nerv    = [i["nervousness"] for i in inputs_per_lap if "nervousness" in i]
        fft_h   = [i["fft_high"]    for i in inputs_per_lap if "fft_high"    in i]
        fft_m   = [i["fft_mid"]     for i in inputs_per_lap if "fft_mid"     in i]
        overlap = [i["overlap_pct"] for i in inputs_per_lap if "overlap_pct" in i]

        inp_out: dict = {"n_laps": len(inputs_per_lap)}
        if nerv:
            inp_out["mean_nervousness"] = round(float(np.mean(nerv)), 3)
            inp_out["max_nervousness"]  = round(float(np.max(nerv)),  3)
        if fft_h:
            inp_out["mean_fft_high"] = round(float(np.mean(fft_h)), 3)
            inp_out["mean_fft_mid"]  = round(float(np.mean(fft_m)), 3)
        if overlap:
            inp_out["mean_overlap_pct"] = round(float(np.mean(overlap)), 1)
        out["inputs"] = inp_out

    # ── Balance / aero ────────────────────────────────────────────────────────
    if balance_per_lap:
        us  = [b["understeer_pct"] for b in balance_per_lap if "understeer_pct" in b]
        os_ = [b["oversteer_pct"]  for b in balance_per_lap if "oversteer_pct"  in b]
        bm  = [b["balance_mean"]   for b in balance_per_lap if "balance_mean"   in b]
        sr  = [b["steer_rms_cornering"] for b in balance_per_lap if "steer_rms_cornering" in b]

        bal_out: dict = {"n_laps": len(balance_per_lap)}
        if us:
            bal_out["mean_understeer_pct"] = round(float(np.mean(us)),  1)
            bal_out["mean_oversteer_pct"]  = round(float(np.mean(os_)), 1)
        if bm:
            bal_out["balance_mean"] = round(float(np.mean(bm)), 3)
        if sr:
            bal_out["steer_rms"] = round(float(np.mean(sr)), 2)
        out["balance"] = bal_out

    logger.info(
        "session_telemetry OK — canales: %s",
        [k for k in ("tyre","brake","suspension","inputs","balance") if k in out]
    )
    return out
