"""
Data-quality assessment for an uploaded telemetry file (or lap pair / stint).

Answers, once and up front, "what is wrong with this data and what does it cost me?"
instead of letting the user discover it panel by panel:

  a) source / format  (sim, car, circuit, sample rate, duration, samples)
  b) channels         (present / missing / constant / synthesized / sparse / partial)
  c) laps             (detected, valid, pit, outliers, partial segments dropped)
  d) analysis modules (ok | degraded | unavailable, with the concrete reason)
  e) global score 0-100 with breakdown, level (good|fair|poor) and a prioritised
     list of "what would improve the analysis".

Design notes
  * It never recomputes analyses: when the endpoint already ran a module, its own
    ``available`` / ``reason`` / ``low_confidence`` flags are reused (``results``).
    Without ``results`` the module status is derived from channels and lap counts.
  * Cost is negligible: column statistics use a capped, evenly strided sample.
  * Pure function, never raises for odd input (see ``safe_assess``).
  * Human-readable strings come from ``src/locales/extra/data_quality.<lang>.json``
    (keys ``dq_*``); every item also carries a stable machine code.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.i18n import LanguageContext, _

logger = logging.getLogger(__name__)

MIN_VALID_LAPS = 5            # same threshold as the stint trend (stint.MIN_LAPS_FOR_TREND)
_MAX_SAMPLE = 60_000          # rows sampled per channel for statistics
_SPARSE_FRAC = 0.25           # >25 % NaN -> sparse channel
_CONST_EPS = 1e-9

# Channel statuses that still deliver (partially) usable data.
_USABLE = {"ok", "synthesized", "sparse", "partial"}
_CREDIT = {"ok": 1.0, "synthesized": 0.6, "partial": 0.5, "sparse": 0.5,
           "constant": 0.15, "inactive": 0.0, "missing": 0.0}
_MODULE_CREDIT = {"ok": 1.0, "degraded": 0.5, "unavailable": 0.0}
_CORNERS = ("FL", "FR", "RL", "RR")


def _corner_slots(fmt: str) -> list:
    return [[fmt.format(c=c)] for c in _CORNERS]


# key, importance (1-3), slots (each slot = alternative column names), allow_constant
_GROUPS: list = [
    {"key": "speed", "imp": 3, "slots": [["Speed"]]},
    {"key": "brake", "imp": 3, "slots": [["Brake"]]},
    {"key": "throttle", "imp": 3, "slots": [["Throttle"]]},
    {"key": "distance", "imp": 3, "slots": [["Distance"]], "special": "distance"},
    {"key": "lap_counter", "imp": 1, "allow_constant": True,
     "slots": [["Session Lap Count", "SessionLapCount", "Lap", "LapNumber", "Lap Number",
                "LapCount", "session_lap_count", "LapTime"]]},
    {"key": "gear", "imp": 1, "slots": [["Gear"]]},
    {"key": "rpm", "imp": 1, "slots": [["RPM", "Engine RPM"]]},
    {"key": "steer", "imp": 2, "slots": [["SteerAngle"]]},
    {"key": "lat_g", "imp": 2, "slots": [["LateralG"]]},
    {"key": "long_g", "imp": 2, "slots": [["LongitudinalG"]]},
    {"key": "yaw", "imp": 2, "slots": [["YawRate"]]},
    {"key": "position", "imp": 2, "slots": [["CarCoordX"], ["CarCoordY"]]},
    {"key": "tyre_temp", "imp": 2,
     "slots": [[f"TyreTemp{z}{c}" for z in ("Middle", "Core", "Inner", "Outer")] for c in _CORNERS]},
    {"key": "tyre_press_hot", "imp": 2, "slots": _corner_slots("TyrePress{c}")},
    {"key": "tyre_press_cold", "imp": 2, "allow_constant": True,
     "slots": _corner_slots("TyrePressCold{c}")},
    {"key": "susp", "imp": 2, "slots": _corner_slots("SuspTravel{c}")},
    {"key": "brake_temp", "imp": 2, "slots": _corner_slots("BrakeTemp{c}")},
    {"key": "water", "imp": 1, "slots": [["WaterTemp"]]},
    {"key": "oil", "imp": 1, "slots": [["OilTemp"]]},
    {"key": "brake_bias", "imp": 1, "allow_constant": True, "slots": [["BrakeBias"]]},
    {"key": "fuel", "imp": 2,
     "slots": [["Fuel", "FuelLevel", "Fuel Level", "fuel_level", "FuelMass", "Fuel Mass"]]},
    {"key": "tyre_wear", "imp": 2, "slots": [], "special": "wear"},
    {"key": "in_pit", "imp": 1, "allow_constant": True, "slots": [["In Pit", "InPit", "in_pit"]]},
    {"key": "ambient", "imp": 1, "allow_constant": True, "slots": [["AirTemp", "RoadTemp"]]},
]

_MODULES_ALL = ["geometry", "time_delta", "gg", "dynamics", "slip", "suspension",
                "tyre_thermal", "tyre_wear", "brakes", "fuel_stint", "thermal",
                "setup", "racing_line", "optimal_lap"]
_MODULES_COMPARE = [m for m in _MODULES_ALL if m not in ("tyre_wear", "fuel_stint", "racing_line")]

_UNITS = {"brake_temp": "°C", "tyre_temp": "°C", "water": "°C", "oil": "°C"}


# ── Small helpers ─────────────────────────────────────────────────────────────

def _t(code: str, **kw) -> str:
    return _(f"dq_{code}", **kw)


def _num(x: Any) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _fmt_val(v: float) -> str:
    return f"{v:.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:.2f}"


def _as_dfs(df_or_laps: Any) -> list:
    if df_or_laps is None:
        return []
    if isinstance(df_or_laps, pd.DataFrame):
        return [df_or_laps] if len(df_or_laps) else []
    if isinstance(df_or_laps, dict):
        df_or_laps = list(df_or_laps.values())
    return [d for d in df_or_laps if isinstance(d, pd.DataFrame) and len(d)]


def _series(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if col not in df.columns:
        return None
    obj = df[col]
    if isinstance(obj, pd.DataFrame):          # duplicated column name
        obj = obj.iloc[:, 0]
    return obj


class _Stats:
    """Lazy, cached per-column statistics over a strided sample of every lap frame."""

    def __init__(self, dfs: list):
        self.dfs = dfs
        self._cache: dict = {}

    def get(self, col: str) -> Optional[dict]:
        if col in self._cache:
            return self._cache[col]
        n = nan = fin_n = 0
        mn, mx, total = math.inf, -math.inf, 0.0
        found = False
        for df in self.dfs:
            s = _series(df, col)
            if s is None:
                continue
            found = True
            step = max(1, len(s) // _MAX_SAMPLE)
            arr = pd.to_numeric(s.iloc[::step], errors="coerce").to_numpy(dtype=float)
            fin = np.isfinite(arr)
            n += arr.size
            nan += int((~fin).sum())
            if fin.any():
                a = arr[fin]
                mn, mx = min(mn, float(a.min())), max(mx, float(a.max()))
                total += float(a.sum())
                fin_n += a.size
        out = None
        if found:
            out = {"n": n, "nan_frac": (nan / n) if n else 1.0, "valid_n": fin_n,
                   "min": mn if fin_n else None, "max": mx if fin_n else None,
                   "mean": (total / fin_n) if fin_n else None}
        self._cache[col] = out
        return out


def _classify(st: dict, allow_constant: bool) -> str:
    if st["valid_n"] == 0:
        return "sparse"
    if (st["max"] - st["min"]) <= _CONST_EPS and not allow_constant:
        return "constant"
    if st["nan_frac"] > _SPARSE_FRAC:
        return "sparse"
    return "ok"


# ── (a) Source / timing ───────────────────────────────────────────────────────

def _timing(dfs: list) -> dict:
    """Sample rate / duration from the best time clock (same logic the loader uses)."""
    try:
        from src.io.loaders import _best_time_step
    except Exception:                                   # pragma: no cover
        return {"clock": None, "hz": None, "duration_s": None}
    clock, hzs, dur = None, [], 0.0
    ok_any = False
    for df in dfs:
        try:
            col, dt = _best_time_step(df)
        except Exception:
            col, dt = None, None
        if col is None or dt is None:
            continue
        ok_any = True
        clock = clock or col
        med = float(dt[dt > 0].median()) if (dt > 0).any() else 0.0
        if med > 0:
            hzs.append(1.0 / med)
        dur += float(dt.sum())
    return {"clock": clock,
            "hz": round(float(np.median(hzs)), 1) if hzs else None,
            "duration_s": round(dur, 1) if ok_any else None}


def _detect_sim(columns: set, meta: dict) -> str:
    if any(c.startswith("AID ") for c in columns) or {"Car Pos Norm", "Session Time Left"} & columns:
        return "assetto_corsa"
    if {"LapDistPct", "IsOnTrack", "PlayerCarIdx", "LFtempCM"} & columns:
        return "iracing"
    if meta.get("vehicle") or meta.get("venue") or meta.get("driver"):
        return "motec"
    return "generic"


def _source_info(dfs: list, meta: dict, timing: dict, mode: str) -> dict:
    cols: set = set()
    for d in dfs[:1]:
        cols |= {str(c) for c in d.columns}
    sim = _detect_sim(cols, meta)
    labels = {"assetto_corsa": "Assetto Corsa (ACTI / MoTeC)", "iracing": "iRacing",
              "motec": "MoTeC", "generic": _t("sim_generic")}
    return {
        "sim": sim,
        "sim_label": labels[sim],
        "car": meta.get("car") or meta.get("vehicle"),
        "circuit": meta.get("circuit") or meta.get("venue"),
        "driver": meta.get("driver"),
        "filename": meta.get("filename"),
        "mode": mode,
        "sample_rate_hz": timing["hz"],
        "duration_s": timing["duration_s"],
        "time_clock": timing["clock"],
        "n_samples": int(sum(len(d) for d in dfs)),
        "n_channels": int(len(dfs[0].columns)) if dfs else 0,
        "n_files": len(dfs),
    }


# ── (c) Laps ──────────────────────────────────────────────────────────────────

_LAP_COLS = ["Session Lap Count", "SessionLapCount", "Lap", "LapNumber", "Lap Number",
             "LapCount", "session_lap_count"]


def _lap_groups(df: pd.DataFrame) -> Optional[pd.core.groupby.DataFrameGroupBy]:
    col = next((c for c in _LAP_COLS if c in df.columns), None)
    if col is None:
        return None
    try:
        key = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)
        return df.groupby(key)
    except Exception:
        return None


def _length_repeatability(dfs: list, results: dict) -> tuple:
    """(pct, n_laps): lap-to-lap spread of the integrated lap length (std / median, %)."""
    lengths: list = []
    if len(dfs) == 1:
        g = _lap_groups(dfs[0])
        if g is not None and "Distance" in dfs[0].columns:
            d = pd.to_numeric(dfs[0]["Distance"], errors="coerce")
            sub = d.groupby(g.ngroup()).agg(["min", "max", "size"])
            lengths = [float(r["max"] - r["min"]) for _, r in sub.iterrows() if r["size"] >= 10]
    else:
        for df in dfs:
            if "Distance" in df.columns:
                d = pd.to_numeric(df["Distance"], errors="coerce").dropna()
                if len(d):
                    lengths.append(float(d.max() - d.min()))
    if len(lengths) < 3:
        rows = (results or {}).get("laps")
        if isinstance(rows, list):
            lengths = [float(r["lap_distance"]) for r in rows
                       if isinstance(r, dict) and _num(r.get("lap_distance"))]
    lengths = [x for x in lengths if x > 50]
    if len(lengths) < 3:
        return None, len(lengths)
    med = float(np.median(lengths))
    kept = [x for x in lengths if 0.9 * med <= x <= 1.1 * med]   # drop partial / pit laps
    if len(kept) < 3:
        return None, len(kept)
    return round(float(np.std(kept, ddof=1) / med * 100.0), 2), len(kept)


def _laps_info(dfs: list, results: dict, mode: str, meta: dict) -> dict:
    rows = results.get("laps") if isinstance(results, dict) else None
    rows = rows if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
    info = {"detected": 0, "valid": 0, "pit": 0, "outliers": 0, "partial_discarded": 0,
            "segmentation": "unknown", "min_recommended": MIN_VALID_LAPS, "known": True}

    if mode == "compare":
        compared = int(meta.get("n_laps_compared") or 2)
        info.update(detected=int(meta.get("n_laps_detected") or compared), valid=compared,
                    segmentation="files" if len(dfs) >= 2 else "lap_counter", compared=compared)
        info["sufficient"] = compared >= 2
        return info

    if rows and "lap_time_s" in rows[0]:                       # stint format
        info["detected"] = len(rows)
        info["outliers"] = sum(1 for r in rows if r.get("is_outlier"))
        info["pit"] = sum(1 for r in rows if r.get("is_pit_lap") and not r.get("is_outlier"))
        info["valid"] = sum(1 for r in rows if not r.get("is_pit_lap") and not r.get("is_outlier")
                            and _num(r.get("lap_time_s")))
    elif rows and "lap_time" in rows[0]:                       # analyze-session format
        info["detected"] = len(rows)
        info["pit"] = sum(1 for r in rows if r.get("is_pit_lap"))
        info["valid"] = info["detected"] - info["pit"]
    else:                                                      # no lap results: best effort
        info["detected"] = len(dfs) if len(dfs) > 1 else 0
        info["valid"] = info["detected"]
        info["known"] = False

    if len(dfs) == 1:
        g = _lap_groups(dfs[0])
        if g is not None:
            info["segmentation"] = "lap_counter"
            raw_n = int((g.size() >= 10).sum())
            if not rows:
                info["detected"] = info["valid"] = raw_n
            info["partial_discarded"] = max(0, raw_n - info["detected"])
        elif "Distance" in dfs[0].columns:
            info["segmentation"] = "distance_reset"
    elif len(dfs) > 1:
        info["segmentation"] = "files"
    info["sufficient"] = info["valid"] >= MIN_VALID_LAPS
    return info


# ── (b) Channels ──────────────────────────────────────────────────────────────

def _distance_entry(stats: _Stats, dfs: list, timing: dict, results: dict) -> dict:
    synth = any(bool(d.attrs.get("distance_synthetic")) for d in dfs)
    present = any("Distance" in d.columns for d in dfs)
    e = {"status": "missing", "channels": [], "present": 0, "total": 1, "params": {}}
    if not present:
        return e
    e.update(present=1, channels=["Distance"])
    if not synth:
        e["status"] = "ok"
        return e
    pct, n = _length_repeatability(dfs, results)
    e["status"] = "synthesized"
    e["synthetic"] = True
    e["method"] = "speed_integration"
    e["clock"] = timing["clock"]
    e["precision_pct"] = pct
    e["precision_laps"] = n
    e["params"] = {"clock": timing["clock"], "hz": timing["hz"], "pct": pct, "n": n}
    if timing["clock"] and pct is not None:
        e["detail_code"] = "synth_clock"
    elif timing["clock"]:
        e["detail_code"] = "synth_clock_noprec"
    else:
        e["detail_code"] = "synth_noclock"
    return e


def _wear_entry(dfs: list) -> dict:
    from src.analytics.tyre_degradation import detect_wear_tracking
    try:
        w = detect_wear_tracking(dfs)
    except Exception:
        w = {"active": None, "evidence": ""}
    ev = str(w.get("evidence") or "")
    if w["active"] is False:
        return {"status": "inactive", "present": 1, "total": 1, "channels": [],
                "detail_code": "wear_inactive", "params": {"evidence": ev}, "evidence": ev}
    if w["active"] is None:
        return {"status": "missing", "present": 0, "total": 1, "channels": [],
                "detail_code": "wear_unknown", "params": {}}
    return {"status": "ok", "present": 1, "total": 1, "channels": [], "params": {}}


def _slot_pick(stats: _Stats, alts: list, allow_constant: bool):
    best = None
    for c in alts:
        st = stats.get(c)
        if st is None:
            continue
        cls = _classify(st, allow_constant)
        if best is None:
            best = (c, cls, st)
        if cls == "ok":
            return c, cls, st
    return best


def _evaluate_channels(stats: _Stats, dfs: list, timing: dict, results: dict) -> list:
    out: list = []
    amb_vals = [v for v in (_mean(stats, "AirTemp"), _mean(stats, "RoadTemp")) if v is not None]
    for g in _GROUPS:
        key = g["key"]
        e: dict = {"key": key, "label": _t(f"ch_{key}"), "importance": g["imp"],
                   "status": "missing", "detail_code": None, "detail": None, "params": {},
                   "channels": [], "present": 0, "total": max(1, len(g["slots"]))}
        special = g.get("special")
        if special == "distance":
            e.update(_distance_entry(stats, dfs, timing, results))
        elif special == "wear":
            e.update(_wear_entry(dfs))
        else:
            picks = [_slot_pick(stats, alts, g.get("allow_constant", False)) for alts in g["slots"]]
            present = [p for p in picks if p is not None]
            e["present"] = len(present)
            e["channels"] = [p[0] for p in present]
            classes = [p[1] for p in present]
            total = len(g["slots"])
            if not present:
                e["status"] = "missing"
            elif all(c == "constant" for c in classes):
                e["status"] = "constant"
                v = present[0][2]["min"]
                e["params"] = {"value": f"{_fmt_val(v)} {_UNITS.get(key, '')}".strip()}
                e["constant_value"] = v
                if key == "brake_temp" and any(abs(v - a) <= 3.0 for a in amb_vals):
                    e["detail_code"] = "constant_ambient"
                else:
                    e["detail_code"] = "constant"
            elif len(present) < total:
                e["status"] = "partial"
                e["detail_code"] = "partial"
                e["params"] = {"n": len(present), "total": total,
                               "present": ", ".join(p[0] for p in present)}
            elif any(c == "constant" for c in classes):
                e["status"] = "partial"
                e["detail_code"] = "partial_const"
                e["params"] = {"n": sum(1 for c in classes if c == "constant"), "total": total}
            elif any(c == "sparse" for c in classes):
                e["status"] = "sparse"
                worst = max(p[2]["nan_frac"] for p in present)
                e["detail_code"] = "sparse"
                e["params"] = {"pct": round(worst * 100)}
            else:
                e["status"] = "ok"
            if e["status"] == "missing":
                e["detail_code"] = "missing"
        if e["status"] == "missing" and e.get("detail_code") is None:
            e["detail_code"] = "missing"
        if e.get("detail_code"):
            e["detail"] = _detail_text(e)
        out.append(e)
    return out


def _mean(stats: _Stats, col: str) -> Optional[float]:
    st = stats.get(col)
    return st["mean"] if st else None


def _detail_text(e: dict) -> str:
    code, p = e["detail_code"], dict(e.get("params") or {})
    if code.startswith("synth"):
        p["prec"] = _prec_txt(e.get("precision_pct"))
        p["clock"] = p.get("clock") or "-"
        p["hz"] = p.get("hz") if p.get("hz") is not None else "?"
    return _t(f"cd_{code}", **p)


def _prec_txt(pct: Optional[float]) -> str:
    return _t("prec_known", pct=pct) if pct is not None else _t("prec_unknown")


# ── (d) Module matrix ─────────────────────────────────────────────────────────

class _Ctx:
    def __init__(self, cs: dict, laps: dict, results: dict, mode: str):
        self.cs, self.laps, self.results, self.mode = cs, laps, results, mode
        d = cs.get("distance", {})
        self.dist_synth = d.get("status") == "synthesized"
        self.prec = _prec_txt(d.get("precision_pct")) if self.dist_synth else ""

    def st(self, key: str) -> str:
        return self.cs.get(key, {}).get("status", "missing")

    def usable(self, key: str) -> bool:
        return self.st(key) in _USABLE

    def full(self, key: str) -> bool:
        return self.st(key) in ("ok", "synthesized")


def _res(results: dict, *keys: str) -> Optional[dict]:
    for k in keys:
        v = results.get(k)
        if isinstance(v, dict) and "available" in v:
            return v
    return None


def _mod(status: str, code: Optional[str], limited_by: Optional[list] = None, **params) -> dict:
    return {"status": status, "reason_code": code, "params": params,
            "limited_by": limited_by or []}


_OK = lambda: _mod("ok", None)  # noqa: E731


def _missing_names(ctx: _Ctx, keys: list) -> str:
    return ", ".join(ctx.cs[k]["label"] for k in keys if not ctx.usable(k))


def _rule_geometry(c: _Ctx) -> dict:
    if c.usable("position"):
        return _OK()
    if c.usable("yaw") or c.usable("steer"):
        return _mod("degraded", "geometry_no_coords", ["position"])
    return _mod("unavailable", "geometry_none", ["position", "yaw", "steer"])


def _rule_time_delta(c: _Ctx) -> dict:
    n = c.laps["valid"]
    if c.mode != "compare" and n < 2:
        return _mod("unavailable", "delta_few_laps", ["laps"], n=n)
    if c.dist_synth:
        return _mod("degraded", "delta_synth", ["distance"], prec=c.prec)
    if not c.usable("distance"):
        return _mod("unavailable", "delta_no_distance", ["distance"])
    return _OK()


def _rule_gg(c: _Ctx) -> dict:
    lat, lon = c.usable("lat_g"), c.usable("long_g")
    if lat and lon:
        return _OK()
    if not lat and not lon:
        if c.usable("position") or c.mode == "compare":
            return _mod("degraded", "gg_estimated", ["lat_g", "long_g"])
        return _mod("unavailable", "gg_missing", ["lat_g", "long_g"])
    miss = _missing_names(c, ["lat_g", "long_g"])
    return _mod("degraded", "gg_partial", ["lat_g" if not lat else "long_g"], missing=miss)


def _rule_dynamics(c: _Ctx) -> dict:
    need = ["steer", "lat_g"]
    if not all(c.usable(k) for k in need):
        return _mod("unavailable", "dyn_missing", [k for k in need if not c.usable(k)],
                    missing=_missing_names(c, need))
    if not c.usable("yaw"):
        return _mod("degraded", "dyn_no_yaw", ["yaw"])
    return _OK()


def _rule_slip(c: _Ctx) -> dict:
    need = ["lat_g", "yaw"]
    if not all(c.usable(k) for k in need):
        return _mod("unavailable", "slip_missing", [k for k in need if not c.usable(k)],
                    missing=_missing_names(c, need))
    if not c.usable("steer"):
        return _mod("degraded", "slip_no_steer", ["steer"])
    return _OK()


def _rule_suspension(c: _Ctx) -> dict:
    s = c.st("susp")
    if s in ("ok", "sparse"):
        return _OK()
    if s == "partial":
        return _mod("degraded", "susp_partial", ["susp"], n=c.cs["susp"]["present"])
    return _mod("unavailable", "susp_missing" if s == "missing" else "susp_invalid", ["susp"])


def _rule_tyre_thermal(c: _Ctx) -> dict:
    s = c.st("tyre_temp")
    if s in ("ok", "sparse"):
        return _OK()
    if s == "partial":
        return _mod("degraded", "tyre_temp_partial", ["tyre_temp"], n=c.cs["tyre_temp"]["present"])
    return _mod("unavailable", "tyre_temp_missing" if s == "missing" else "tyre_temp_constant",
                ["tyre_temp"])


def _rule_tyre_wear(c: _Ctx) -> dict:
    w, n = c.st("tyre_wear"), c.laps["valid"]
    if w == "inactive":
        return _mod("unavailable", "tyre_wear_inactive", ["tyre_wear"],
                    evidence=c.cs["tyre_wear"].get("evidence", ""))
    if n < MIN_VALID_LAPS:
        return _mod("unavailable", "tyre_wear_few_laps", ["laps"], n=n, min=MIN_VALID_LAPS)
    if w == "missing":
        return _mod("degraded", "tyre_wear_unknown", ["tyre_wear"])
    return _OK()


def _rule_brakes(c: _Ctx) -> dict:
    if not c.usable("long_g"):
        return _mod("unavailable", "brake_no_long_g", ["long_g"])
    t = c.st("brake_temp")
    if t == "constant":
        v = c.cs["brake_temp"]["params"].get("value", "?")
        return _mod("degraded", "brake_temp_constant", ["brake_temp"], value=v)
    if t in ("missing", "partial"):
        return _mod("degraded", "brake_temp_missing", ["brake_temp"])
    return _OK()


def _rule_fuel(c: _Ctx) -> dict:
    n, f = c.laps["valid"], c.st("fuel")
    if n < 3:
        return _mod("unavailable", "stint_few_laps", ["laps"], n=n)
    if f in ("missing", "constant"):
        return _mod("degraded", "fuel_missing" if f == "missing" else "fuel_constant", ["fuel"])
    if n < MIN_VALID_LAPS:
        return _mod("degraded", "fuel_few_laps", ["laps"], n=n, min=MIN_VALID_LAPS)
    return _OK()


def _thermal_components(c: _Ctx) -> list:
    """[(comp_key, ok, reason, limited_by)] from channels, overridden by module results."""
    comps = []
    for key, ch in (("water", "water"), ("oil", "oil")):
        s = c.st(ch)
        comps.append((key, s in _USABLE, None if s in _USABLE else _t("cr_missing"), ch))
    s = c.st("brake_temp")
    if s in ("ok", "sparse", "partial"):
        comps.append(("brake_temps", True, None, "brake_temp"))
    elif s == "constant":
        comps.append(("brake_temps", False,
                      _t("cr_constant", value=c.cs["brake_temp"]["params"].get("value", "?")),
                      "brake_temp"))
    else:
        comps.append(("brake_temps", False, _t("cr_missing"), "brake_temp"))
    hot, cold = c.usable("tyre_press_hot"), c.usable("tyre_press_cold")
    if hot and cold:
        comps.append(("tyre_pressure", True, None, None))
    elif hot:
        comps.append(("tyre_pressure", False, _t("cr_no_cold"), "tyre_press_cold"))
    else:
        comps.append(("tyre_pressure", False, _t("cr_missing"), "tyre_press_hot"))
    comps.append(("brake_bias", c.usable("brake_bias"),
                  None if c.usable("brake_bias") else _t("cr_missing"), "brake_bias"))

    th = c.results.get("thermal_analysis")
    if isinstance(th, dict) and "available" in th:
        by_key = {k: (ok, rs, lb) for k, ok, rs, lb in comps}
        merged = []
        for sub in ("water", "oil", "brake_temps", "tyre_pressure", "brake_bias"):
            name = {"water": "water_temp", "oil": "oil_temp"}.get(sub, sub)
            d = th.get(name)
            ok, rs, lb = by_key[sub]
            if isinstance(d, dict) and "available" in d:
                ok = bool(d["available"])
                if not ok:
                    rs = d.get("reason") or rs or _t("cr_missing")
                else:
                    rs = None
            elif not th.get("available"):
                ok = False
            merged.append((sub, ok, rs, lb))
        comps = merged
    return comps


def _rule_thermal(c: _Ctx) -> dict:
    comps = _thermal_components(c)
    bad = [x for x in comps if not x[1]]
    items = [f"{_t('comp_' + k)}: {rs}" for k, ok, rs, _lb in bad]
    lim = [lb for _k, _ok, _rs, lb in bad if lb]
    if len(bad) == len(comps):
        m = _mod("unavailable", "thermal_none", lim)
    elif bad:
        m = _mod("degraded", "thermal_partial", lim,
                 missing=", ".join(_t("comp_" + k) for k, *_ in bad))
    else:
        m = _OK()
    m["details"] = items
    if isinstance(c.results.get("thermal_analysis"), dict):
        m["source"] = "module"
    return m


_SETUP_INPUTS = ["tyre_thermal", "brakes", "suspension", "slip", "dynamics", "geometry"]


def _rule_setup(c: _Ctx, mods: dict) -> dict:
    if c.mode != "compare":
        base = [mods[k]["status"] for k in ("geometry", "dynamics", "tyre_thermal", "thermal") if k in mods]
        if base and all(s == "unavailable" for s in base):
            return _mod("unavailable", "setup_depends", ["lat_g"])
    st = [mods[k]["status"] for k in _SETUP_INPUTS if k in mods]
    n_ok = sum(1 for s in st if s != "unavailable")
    if n_ok == 0:
        return _mod("unavailable", "setup_depends", [])
    if n_ok < len(st) - 1:
        lim: list = []
        for k in _SETUP_INPUTS:
            if mods.get(k, {}).get("status") == "unavailable":
                lim += mods[k]["limited_by"]
        return _mod("degraded", "setup_few", lim, n=n_ok, total=len(st))
    return _OK()


def _rule_racing_line(c: _Ctx) -> dict:
    n = c.laps["valid"]
    if n < 2:
        return _mod("unavailable", "rl_few_laps_min", ["laps"], n=n)
    if n < MIN_VALID_LAPS:
        return _mod("degraded", "rl_few_laps", ["laps"], n=n, min=MIN_VALID_LAPS)
    return _OK()


def _rule_optimal(c: _Ctx) -> dict:
    n = c.laps["valid"]
    if n < 2:
        return _mod("unavailable", "optimal_few_laps", ["laps"], n=n, min=2)
    if c.dist_synth:
        return _mod("degraded", "optimal_synth", ["distance"], prec=c.prec)
    return _OK()


def _hook(c: _Ctx, name: str):
    """(available|None, reason|None, low_confidence) from the module's own result."""
    r, mode = c.results, c.mode
    d = None
    if name == "geometry":
        d = _res(r, "curvas_sesion")
        if d is None and isinstance(r.get("apexes"), list):
            return len(r["apexes"]) > 0, None, False
    elif name == "gg":
        if isinstance(r.get("gg_diagram"), list):
            return len(r["gg_diagram"]) > 0, None, False
    elif name == "dynamics":
        ts = r.get("telemetria_sesion")
        if isinstance(ts, dict) and "available" in ts:
            return bool(ts.get("available") and ts.get("balance")), None, False
    elif name == "slip":
        d = _res(r, "slip_angle", "slip_analysis")
    elif name == "suspension":
        d = _res(r, "suspension")
    elif name == "tyre_thermal":
        d = _res(r, "tyre_analysis")
    elif name == "tyre_wear":
        d = _res(r, "degradacion_neumatico", "tyre_degradation")
    elif name == "brakes":
        d = _res(r, "brake_analysis")
    elif name == "fuel_stint":
        d = _res(r, "combustible")
    elif name == "setup":
        d = _res(r, "setup_sesion", "setup_advisor")
    elif name == "racing_line":
        d = _res(r, "racing_line_rl", "racing_line")
    elif name == "optimal_lap":
        d = _res(r, "optimal_lap", "vuelta_optima", "potential_lap", "optimal_lap_result")
    if d is None:
        return None, None, False
    return (bool(d.get("available")), d.get("reason") or None,
            bool(d.get("low_confidence")) or d.get("confidence") == "low")


def _overlay(c: _Ctx, name: str, m: dict) -> dict:
    avail, reason, low = _hook(c, name)
    if avail is None:
        m.setdefault("source", "channels")
        return m
    m["source"] = "module"
    if avail is False:
        if m["status"] != "unavailable":
            was_degraded = m["status"] == "degraded"
            m["status"] = "unavailable"
            if reason:
                m["reason_code"], m["params"], m["reason_text"] = "module", {}, reason
            elif not was_degraded:
                m["reason_code"], m["params"] = "module_unavailable", {}
        elif reason and m["reason_code"] in ("module_unavailable",):
            m["reason_text"] = reason
        elif reason and not m["limited_by"]:
            m["reason_code"], m["params"], m["reason_text"] = "module", {}, reason
    else:
        if m["status"] == "unavailable":
            m["status"] = "degraded"                    # module did produce output anyway
        if low:
            if m["status"] == "ok":
                m["status"] = "degraded"
                m["reason_code"], m["params"] = "low_confidence", {}
            if reason:
                m["reason_code"], m["params"], m["reason_text"] = "module", {}, reason
    return m


_RULES = {
    "geometry": _rule_geometry, "time_delta": _rule_time_delta, "gg": _rule_gg,
    "dynamics": _rule_dynamics, "slip": _rule_slip, "suspension": _rule_suspension,
    "tyre_thermal": _rule_tyre_thermal, "tyre_wear": _rule_tyre_wear, "brakes": _rule_brakes,
    "fuel_stint": _rule_fuel, "thermal": _rule_thermal, "racing_line": _rule_racing_line,
    "optimal_lap": _rule_optimal,
}


def _evaluate_modules(c: _Ctx) -> list:
    names = _MODULES_COMPARE if c.mode == "compare" else _MODULES_ALL
    mods: dict = {}
    for name in names:
        if name == "setup":
            continue
        mods[name] = _overlay(c, name, _RULES[name](c))
    if "setup" in names:
        mods["setup"] = _overlay(c, "setup", _rule_setup(c, mods))
    out = []
    for name in names:
        m = mods[name]
        text = m.pop("reason_text", None)
        if text is None and m["reason_code"]:
            try:
                text = _t(f"r_{m['reason_code']}", **m["params"])
            except Exception:
                text = m["reason_code"]
        m.update({"key": name, "label": _t(f"mod_{name}"), "reason": text})
        out.append(m)
    return out


# ── (e) Score & improvements ──────────────────────────────────────────────────

def _laps_score(laps: dict, mode: str) -> int:
    n = laps["valid"]
    if mode == "compare":
        return 100 if n >= 2 else 20
    for thr, sc in ((8, 100), (5, 80), (3, 55), (2, 35), (1, 15)):
        if n >= thr:
            return sc
    return 0


def _improvements(channels: list, modules: list, laps: dict, mode: str) -> list:
    items: list = []
    for ch in channels:
        s = ch["status"]
        if s == "ok" or (s == "missing" and ch["key"] in ("speed", "brake", "throttle")):
            continue
        unlocks = [m["key"] for m in modules
                   if m["status"] != "ok" and ch["key"] in m["limited_by"]]
        if not unlocks and ch["importance"] < 2 and s != "synthesized":
            continue
        score = len(unlocks) * 2 + ch["importance"] + (1 if s in ("constant", "inactive") else 0)
        prio = "high" if (len(unlocks) >= 2 or (unlocks and ch["importance"] >= 3)) \
            else "medium" if unlocks else "low"
        items.append({
            "id": f"fix_{ch['key']}", "channel": ch["key"], "priority": prio, "score": score,
            "title": _t(f"fixt_{s if s in ('missing','constant','synthesized','partial','sparse','inactive') else 'missing'}",
                        channel=ch["label"]),
            "detail": _t(f"fix_{ch['key']}") if _has_key(f"dq_fix_{ch['key']}") else _t("fix_generic", channel=ch["label"]),
            "unlocks": unlocks,
        })
    if mode != "compare" and laps["valid"] < MIN_VALID_LAPS:
        unlocks = [m["key"] for m in modules if m["status"] != "ok" and "laps" in m["limited_by"]]
        items.append({"id": "fix_more_laps", "channel": None, "priority": "high" if unlocks else "medium",
                      "score": len(unlocks) * 2 + 3, "title": _t("fixt_more_laps"),
                      "detail": _t("fix_more_laps", n=laps["valid"], min=MIN_VALID_LAPS),
                      "unlocks": unlocks})
    items.sort(key=lambda i: (-i["score"], i["id"]))
    for i in items:
        i.pop("score")
    return items


def _has_key(key: str) -> bool:
    from src.i18n import get_locale
    return key in get_locale()


def _level(score: int) -> str:
    return "good" if score >= 75 else "fair" if score >= 50 else "poor"


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


# ── Public API ────────────────────────────────────────────────────────────────

def assess_data_quality(df_or_laps: Any, metadata: Optional[dict] = None,
                        results: Optional[dict] = None, lang: Optional[str] = None) -> dict:
    """
    Build the serialisable ``data_quality`` object.

    df_or_laps: the loaded session DataFrame, or a list of per-lap / per-file DataFrames.
    metadata:   optional {filename, car/vehicle, circuit/venue, driver, mode, n_laps_detected,
                n_laps_compared}. ``mode`` is 'session' | 'stint' | 'compare'; inferred if absent.
    results:    the endpoint's response dict so far; module ``available``/``reason`` flags
                found there are reused instead of being recomputed.
    lang:       'es' | 'en' (defaults to the current request language).
    """
    if lang:
        with LanguageContext(lang):
            return _assess(df_or_laps, metadata or {}, results or {}, lang)
    from src.i18n import get_language
    return _assess(df_or_laps, metadata or {}, results or {}, get_language())


def _assess(df_or_laps: Any, meta: dict, results: dict, lang: str) -> dict:
    dfs = _as_dfs(df_or_laps)
    if not dfs:
        return {"available": False, "reason": _t("no_data"), "lang": lang}

    mode = meta.get("mode")
    if mode not in ("session", "stint", "compare"):
        mode = "session" if (isinstance(results.get("laps"), list) or len(dfs) != 2) else "compare"

    stats = _Stats(dfs)
    timing = _timing(dfs)
    laps = _laps_info(dfs, results, mode, meta)
    channels = _evaluate_channels(stats, dfs, timing, results)
    cs = {c["key"]: c for c in channels}
    ctx = _Ctx(cs, laps, results, mode)
    modules = _evaluate_modules(ctx)
    improvements = _improvements(channels, modules, laps, mode)

    wsum = sum(c["importance"] for c in channels)
    ch_score = 100.0 * sum(c["importance"] * _CREDIT.get(c["status"], 0.0) for c in channels) / wsum
    mod_score = 100.0 * sum(_MODULE_CREDIT[m["status"]] for m in modules) / max(1, len(modules))
    lap_score = float(_laps_score(laps, mode))
    score = int(round(0.4 * ch_score + 0.2 * lap_score + 0.4 * mod_score))
    score = max(0, min(100, score))

    n_ok = sum(1 for c in channels if c["status"] == "ok")
    n_missing = sum(1 for c in channels if c["status"] in ("missing",))
    n_warn = len(channels) - n_ok - n_missing

    dq = {
        "available": True,
        "version": 1,
        "lang": lang,
        "score": score,
        "level": _level(score),
        "breakdown": {
            "channels": {"score": int(round(ch_score)), "weight": 0.4},
            "laps": {"score": int(round(lap_score)), "weight": 0.2},
            "modules": {"score": int(round(mod_score)), "weight": 0.4},
        },
        "source": _source_info(dfs, meta, timing, mode),
        "channels": channels,
        "channel_summary": {"ok": n_ok, "warning": n_warn, "missing": n_missing, "total": len(channels)},
        "laps": laps,
        "modules": modules,
        "module_summary": {s: sum(1 for m in modules if m["status"] == s)
                           for s in ("ok", "degraded", "unavailable")},
        "improvements": improvements,
    }
    return _clean(dq)


def build_meta(path: Optional[str] = None, filename: Optional[str] = None,
               mode: Optional[str] = None, **extra: Any) -> dict:
    """Metadata dict for ``assess_data_quality``: MoTeC header (driver/vehicle/venue) + context."""
    meta: dict = {}
    if path:
        try:
            from src.io.loaders import read_motec_metadata
            meta.update({k: v for k, v in read_motec_metadata(path).items() if v})
        except Exception:                                       # pragma: no cover
            pass
    if filename:
        meta["filename"] = filename
    if mode:
        meta["mode"] = mode
    meta.update({k: v for k, v in extra.items() if v is not None})
    return meta


def safe_assess(df_or_laps: Any, metadata: Optional[dict] = None, results: Optional[dict] = None,
                lang: Optional[str] = None) -> Optional[dict]:
    """assess_data_quality that can never break an endpoint (returns None on failure)."""
    try:
        return assess_data_quality(df_or_laps, metadata, results, lang)
    except Exception as exc:                                    # pragma: no cover
        logger.warning("data_quality: no se pudo evaluar la calidad de datos: %s", exc, exc_info=True)
        return None
