"""
Thermal Management Analysis.

Analyzes: brake temperatures, tyre pressures, engine water/oil temperatures,
and brake bias. Compatible with AC (brake temps + PSI pressures) and
iRacing (water/oil temps + kPa pressures + dcBrakeBias).

All pressure outputs are reported in both bar and PSI.
"""
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Unit constants ────────────────────────────────────────────────────────────
_BAR_TO_PSI = 14.5038
_PSI_TO_BAR = 1.0 / _BAR_TO_PSI
_KPA_TO_BAR = 0.01

# ── Temperature thresholds (°C) ───────────────────────────────────────────────
_BRAKE_COLD   = 200   # under-temp → close ducts, glazing risk
_BRAKE_OPT_LO = 300   # optimal window lower
_BRAKE_OPT_HI = 700   # optimal window upper
_BRAKE_HOT    = 800   # over-temp → open ducts, brake fluid boil risk

_WATER_WARN   = 105
_WATER_CRIT   = 115
_OIL_WARN     = 130
_OIL_CRIT     = 140

# ── Tyre pressure delta thresholds (bar, hot − cold) ─────────────────────────
_DP_LOW  = 0.05   # too little build-up → raise cold pressure
_DP_HIGH = 0.28   # too much build-up → lower cold pressure
_DP_MID  = 0.15   # ideal midpoint

# ── Brake bias limits ─────────────────────────────────────────────────────────
_BIAS_SOFT_MIN = 52.0  # % front — warn if below
_BIAS_SOFT_MAX = 63.0  # % front — warn if above

# ── Channel name candidates ───────────────────────────────────────────────────
_WATER_CH = ["WaterTemp", "Water Temp", "Engine Temp", "CoolantTemp",
             "Coolant Temp", "Eng Coolant Temp"]
_OIL_CH   = ["OilTemp", "Oil Temp", "Eng Oil Temp", "Engine Oil Temp",
              "EngOilTemp"]
_BIAS_CH  = ["BrakeBias", "dcBrakeBias", "Brake Bias", "brake_bias"]

_BRAKE_CH = {
    "FL": ["BrakeTempFL", "Brake Temp FL", "BrakeTempFrontLeft"],
    "FR": ["BrakeTempFR", "Brake Temp FR", "BrakeTempFrontRight"],
    "RL": ["BrakeTempRL", "Brake Temp RL", "BrakeTempRearLeft"],
    "RR": ["BrakeTempRR", "Brake Temp RR", "BrakeTempRearRight"],
}
_PRES_HOT_CH = {
    "FL": ["TyrePressFL", "Tire Pressure FL", "Tyre Pres FL", "LFpressure"],
    "FR": ["TyrePressFR", "Tire Pressure FR", "Tyre Pres FR", "RFpressure"],
    "RL": ["TyrePressRL", "Tire Pressure RL", "Tyre Pres RL", "LRpressure"],
    "RR": ["TyrePressRR", "Tire Pressure RR", "Tyre Pres RR", "RRpressure"],
}
_PRES_COLD_CH = {
    "FL": ["LFcoldPressure", "TyrePressColdFL"],
    "FR": ["RFcoldPressure", "TyrePressColdFR"],
    "RL": ["LRcoldPressure", "TyrePressColdRL"],
    "RR": ["RRcoldPressure", "TyrePressColdRR"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, candidates: list) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _to_bar(series: pd.Series) -> pd.Series:
    """Auto-detect pressure unit and convert to bar."""
    valid = series.dropna()
    if valid.empty:
        return series
    mx = float(valid.max())
    if mx > 100:       # kPa (iRacing ~170-250 kPa)
        return series * _KPA_TO_BAR
    elif mx > 10:      # PSI (AC ~20-40 PSI)
        return series * _PSI_TO_BAR
    return series      # already bar


def _to_pct_bias(series: pd.Series) -> pd.Series:
    """Normalise brake bias to front percentage (0-100)."""
    valid = series.dropna()
    if valid.empty:
        return series
    if float(valid.max()) <= 1.05:   # fraction 0.0-1.0 (iRacing dcBrakeBias)
        return series * 100.0
    return series                     # already %


def _pbar(bar_val: float) -> dict:
    """Return a pressure value formatted as {bar, psi}."""
    return {
        "bar": round(float(bar_val), 2),
        "psi": round(float(bar_val) * _BAR_TO_PSI, 1),
    }


def _lap_mean(df: pd.DataFrame, candidates: list, transform=None) -> float | None:
    ch = _col(df, candidates)
    if ch is None:
        return None
    vals = pd.to_numeric(df[ch], errors="coerce").dropna()
    if vals.empty:
        return None
    if transform:
        vals = transform(vals)
    return float(vals.mean())


# ── Water / oil temperature analysis ─────────────────────────────────────────

def _analyse_fluid(dfs: list, candidates: list, warn: float, crit: float,
                   name: str) -> dict:
    """Compute per-lap mean for a fluid temperature channel."""
    per_lap = []
    for lap_idx, df in enumerate(dfs):
        v = _lap_mean(df, candidates)
        if v is not None:
            per_lap.append({"lap": lap_idx + 1, "mean_c": round(v, 1)})
    if not per_lap:
        return {"available": False}
    temps = [r["mean_c"] for r in per_lap]
    peak  = max(temps)
    trend = None
    if len(temps) >= 3:
        x = np.arange(len(temps), dtype=float)
        trend = round(float(np.polyfit(x, temps, 1)[0]), 2)  # °C per lap

    status = "normal"
    if peak >= crit:
        status = "critical"
    elif peak >= warn:
        status = "warning"

    out = {
        "available":   True,
        "channel":     name,
        "per_lap":     per_lap,
        "mean_c":      round(float(np.mean(temps)), 1),
        "max_c":       round(peak, 1),
        "trend_c_per_lap": trend,
        "status":      status,
        "warn_threshold_c":  warn,
        "crit_threshold_c":  crit,
    }
    if status == "critical":
        out["alert"] = f"{name} temp crítica ({peak:.0f}°C ≥ {crit}°C) — revisar sistema de refrigeración"
    elif status == "warning":
        out["alert"] = f"{name} temp elevada ({peak:.0f}°C ≥ {warn}°C) — monitorear de cerca"
    return out


# ── Brake temperature analysis (AC) ──────────────────────────────────────────

def _brake_corner_status(mean_c: float) -> str:
    if mean_c < _BRAKE_COLD:   return "too_cold"
    if mean_c < _BRAKE_OPT_LO: return "suboptimal"
    if mean_c <= _BRAKE_OPT_HI: return "optimal"
    if mean_c <= _BRAKE_HOT:   return "hot"
    return "critical"


def _analyse_brake_temps(dfs: list) -> dict:
    corners_data: dict[str, list] = {c: [] for c in ("FL", "FR", "RL", "RR")}
    found = False
    for lap_idx, df in enumerate(dfs):
        for corner, cands in _BRAKE_CH.items():
            ch = _col(df, cands)
            if ch is None:
                continue
            found = True
            vals = pd.to_numeric(df[ch], errors="coerce").dropna()
            if not vals.empty:
                corners_data[corner].append({
                    "lap":    lap_idx + 1,
                    "mean_c": round(float(vals.mean()), 1),
                    "max_c":  round(float(vals.max()), 1),
                })
    if not found:
        return {"available": False}

    summary = {}
    for corner, laps in corners_data.items():
        if not laps:
            continue
        means = [r["mean_c"] for r in laps]
        avg   = float(np.mean(means))
        peak  = max(r["max_c"] for r in laps)
        summary[corner] = {
            "mean_c":   round(avg, 1),
            "max_c":    round(peak, 1),
            "status":   _brake_corner_status(avg),
            "per_lap":  laps,
        }

    if not summary:
        return {"available": False}

    # Front / rear thermal balance → brake bias direction
    front_means = [summary[c]["mean_c"] for c in ("FL", "FR") if c in summary]
    rear_means  = [summary[c]["mean_c"] for c in ("RL", "RR") if c in summary]
    balance = None
    if front_means and rear_means:
        f_avg = float(np.mean(front_means))
        r_avg = float(np.mean(rear_means))
        balance = {
            "front_mean_c": round(f_avg, 1),
            "rear_mean_c":  round(r_avg, 1),
            "ratio_f_r":    round(f_avg / r_avg, 2) if r_avg > 0 else None,
        }

    # Duct recommendations per corner
    duct_recs = []
    for corner, s in summary.items():
        if s["status"] == "too_cold":
            duct_recs.append({
                "corner": corner,
                "action": "close",
                "reason": f"{s['mean_c']:.0f}°C — under optimal range, close brake duct to build heat",
                "priority": "media",
            })
        elif s["status"] in ("hot", "critical"):
            duct_recs.append({
                "corner": corner,
                "action": "open",
                "reason": f"{s['mean_c']:.0f}°C — over optimal range, open brake duct to reduce heat",
                "priority": "alta" if s["status"] == "critical" else "media",
            })

    return {
        "available":    True,
        "corners":      summary,
        "balance":      balance,
        "duct_recs":    duct_recs,
        "optimal_range_c": [_BRAKE_OPT_LO, _BRAKE_OPT_HI],
    }


# ── Tyre pressure analysis ────────────────────────────────────────────────────

def _analyse_tyre_pressure(dfs: list) -> dict:
    corners_data: dict[str, list] = {c: [] for c in ("FL", "FR", "RL", "RR")}
    found = False

    for lap_idx, df in enumerate(dfs):
        for corner in ("FL", "FR", "RL", "RR"):
            # live (hot) pressure
            hot_ch   = _col(df, _PRES_HOT_CH[corner])
            cold_ch  = _col(df, _PRES_COLD_CH[corner])

            if hot_ch is None:
                continue
            found = True
            hot_vals = _to_bar(pd.to_numeric(df[hot_ch], errors="coerce").dropna())
            if hot_vals.empty:
                continue

            # mean hot pressure for the lap
            hot_mean = float(hot_vals.mean())
            hot_max  = float(hot_vals.max())

            # cold pressure: from cold channel if available, else estimate from first-10-samples min
            if cold_ch is not None:
                cold_vals  = _to_bar(pd.to_numeric(df[cold_ch], errors="coerce").dropna())
                cold_mean  = float(cold_vals.mean()) if not cold_vals.empty else None
            else:
                # Estimate cold from the first 5% of the lap (tyre not yet heated)
                n5 = max(1, len(hot_vals) // 20)
                cold_mean = float(_to_bar(
                    pd.to_numeric(df[hot_ch], errors="coerce")
                ).dropna().iloc[:n5].mean())

            delta = (hot_mean - cold_mean) if cold_mean is not None else None

            corners_data[corner].append({
                "lap":        lap_idx + 1,
                "hot_bar":    round(hot_mean, 3),
                "hot_max_bar":round(hot_max, 3),
                "cold_bar":   round(cold_mean, 3) if cold_mean else None,
                "delta_bar":  round(delta, 3) if delta is not None else None,
            })

    if not found:
        return {"available": False}

    summary = {}
    recommendations = []
    for corner, laps in corners_data.items():
        if not laps:
            continue
        hot_means   = [r["hot_bar"] for r in laps]
        cold_means  = [r["cold_bar"] for r in laps if r.get("cold_bar") is not None]
        deltas      = [r["delta_bar"] for r in laps if r.get("delta_bar") is not None]

        avg_hot   = float(np.mean(hot_means))
        avg_cold  = float(np.mean(cold_means)) if cold_means else None
        avg_delta = float(np.mean(deltas)) if deltas else None

        status = "ok"
        if avg_delta is not None:
            if avg_delta < _DP_LOW:
                status = "low_delta"   # starting pressure too high
            elif avg_delta > _DP_HIGH:
                status = "high_delta"  # starting pressure too low

        entry = {
            "hot":     _pbar(avg_hot),
            "per_lap": laps,
            "status":  status,
        }
        if avg_cold is not None:
            entry["cold"] = _pbar(avg_cold)
        if avg_delta is not None:
            entry["delta"] = _pbar(avg_delta)

        # Recommendation
        if avg_delta is not None and avg_cold is not None:
            target_cold = avg_cold - (avg_delta - _DP_MID)
            target_cold = max(0.8, target_cold)  # safety floor
            delta_adjust = target_cold - avg_cold
            if abs(delta_adjust) >= 0.03:   # only recommend if change > 0.03 bar
                direction = "lower" if delta_adjust < 0 else "raise"
                adj_bar   = abs(delta_adjust)
                adj_psi   = adj_bar * _BAR_TO_PSI
                recommendations.append({
                    "corner":      corner,
                    "direction":   direction,
                    "delta_bar":   round(adj_bar, 2),
                    "delta_psi":   round(adj_psi, 1),
                    "current_cold": _pbar(avg_cold),
                    "target_cold":  _pbar(target_cold),
                    "current_hot":  _pbar(avg_hot),
                    "reason":      (
                        f"Hot-cold delta {avg_delta:.2f} bar ({avg_delta*_BAR_TO_PSI:.1f} PSI) "
                        f"— target is {_DP_MID:.2f} bar ({_DP_MID*_BAR_TO_PSI:.1f} PSI). "
                        f"{direction.capitalize()} cold pressure by "
                        f"{adj_bar:.2f} bar ({adj_psi:.1f} PSI)."
                    ),
                    "priority": "media" if abs(delta_adjust) > 0.1 else "baja",
                })

        summary[corner] = entry

    return {
        "available":     True,
        "corners":       summary,
        "recommendations": recommendations,
        "delta_target":  _pbar(_DP_MID),
        "delta_window":  {"low": _pbar(_DP_LOW), "high": _pbar(_DP_HIGH)},
    }


# ── Brake bias analysis ───────────────────────────────────────────────────────

def _analyse_brake_bias(dfs: list, brake_temps: dict | None = None) -> dict:
    values = []
    for df in dfs:
        ch = _col(df, _BIAS_CH)
        if ch is None:
            continue
        vals = _to_pct_bias(pd.to_numeric(df[ch], errors="coerce").dropna())
        if not vals.empty:
            values.append(round(float(vals.mean()), 1))

    if not values:
        return {"available": False}

    current_pct = round(float(np.mean(values)), 1)
    recommendation = None

    # Primary: use brake temp balance if available
    if brake_temps and brake_temps.get("available") and brake_temps.get("balance"):
        bal   = brake_temps["balance"]
        ratio = bal.get("ratio_f_r")
        f_avg = bal.get("front_mean_c", 0)
        r_avg = bal.get("rear_mean_c", 0)
        if ratio is not None and f_avg > 50 and r_avg > 50:   # both hot enough to be meaningful
            if ratio > 1.30:
                # Fronts running much hotter → reduce front bias
                suggested = max(_BIAS_SOFT_MIN, round(current_pct - 2.0, 1))
                recommendation = {
                    "direction": "reduce",
                    "suggested_pct": suggested,
                    "current_pct":   current_pct,
                    "reason": (
                        f"Front brakes {f_avg:.0f}°C vs rear {r_avg:.0f}°C "
                        f"(ratio {ratio:.2f}) — fronts overloaded. "
                        f"Reduce bias from {current_pct}% to ~{suggested}% front."
                    ),
                    "priority": "media",
                }
            elif ratio < 0.75:
                # Rears running hotter → increase front bias
                suggested = min(_BIAS_SOFT_MAX, round(current_pct + 2.0, 1))
                recommendation = {
                    "direction": "increase",
                    "suggested_pct": suggested,
                    "current_pct":   current_pct,
                    "reason": (
                        f"Rear brakes {r_avg:.0f}°C vs front {f_avg:.0f}°C "
                        f"(ratio {ratio:.2f}) — rears overloaded. "
                        f"Increase bias from {current_pct}% to ~{suggested}% front."
                    ),
                    "priority": "media",
                }

    # Secondary: flag if bias is outside typical range
    out_of_range = None
    if current_pct < _BIAS_SOFT_MIN:
        out_of_range = f"Bias {current_pct}% is below typical floor ({_BIAS_SOFT_MIN}%) — check rear locking risk"
    elif current_pct > _BIAS_SOFT_MAX:
        out_of_range = f"Bias {current_pct}% is above typical ceiling ({_BIAS_SOFT_MAX}%) — check front fade/lock risk"

    return {
        "available":      True,
        "current_pct":    current_pct,
        "per_lap":        [{"lap": i + 1, "bias_pct": v} for i, v in enumerate(values)],
        "recommendation": recommendation,
        "out_of_range":   out_of_range,
        "typical_range":  [_BIAS_SOFT_MIN, _BIAS_SOFT_MAX],
    }


# ── Main entry points ─────────────────────────────────────────────────────────

def analizar_termica(dfs: list, df_laps: pd.DataFrame) -> dict:
    """
    Stint-level thermal analysis. Called with all session laps.
    """
    water = _analyse_fluid(dfs, _WATER_CH, _WATER_WARN, _WATER_CRIT, "Water")
    oil   = _analyse_fluid(dfs, _OIL_CH,   _OIL_WARN,   _OIL_CRIT,   "Oil")
    brake = _analyse_brake_temps(dfs)
    pres  = _analyse_tyre_pressure(dfs)
    bias  = _analyse_brake_bias(dfs, brake_temps=brake)

    has_data = any([
        water.get("available"), oil.get("available"),
        brake.get("available"), pres.get("available"), bias.get("available"),
    ])

    if not has_data:
        return {"available": False}

    n_recs = (
        len(brake.get("duct_recs", []))
        + len(pres.get("recommendations", []))
        + (1 if bias.get("recommendation") else 0)
        + (1 if water.get("alert") else 0)
        + (1 if oil.get("alert") else 0)
    )
    logger.info(
        "Thermal analysis: water=%s oil=%s brake=%s pressure=%s bias=%s | %d recs",
        water.get("status", "—"), oil.get("status", "—"),
        "ok" if brake.get("available") else "—",
        "ok" if pres.get("available") else "—",
        f"{bias.get('current_pct','—')}%" if bias.get("available") else "—",
        n_recs,
    )

    return {
        "available":    True,
        "water_temp":   water,
        "oil_temp":     oil,
        "brake_temps":  brake,
        "tyre_pressure": pres,
        "brake_bias":   bias,
        "n_recommendations": n_recs,
    }


def analizar_termica_comparativa(df_a: pd.DataFrame, df_b: pd.DataFrame,
                                  label_a: str = "A", label_b: str = "B") -> dict:
    """
    Two-lap comparative thermal snapshot. Used in compare-session-laps endpoint.
    """
    result = analizar_termica([df_a, df_b], pd.DataFrame())
    if not result.get("available"):
        return {"available": False}
    result["label_a"] = label_a
    result["label_b"] = label_b
    return result
