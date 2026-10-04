"""
Unified corner map: ONE ordered list of corners per circuit, built from several laps.

Why: the project had two families of detectors that disagree (speed minima vs. track curvature)
and a segmenter that needs braking + apex + throttle. A corner a car takes flat out has no speed
minimum, so some bends were never found. See docs/CORNER_DETECTION.md for the full rationale,
the parameters and the measured results.

Pipeline (every threshold is a key of ``DEFAULTS`` and can be overridden with ``options``):

  1. per-lap candidates with the existing detectors (speed minima, track-curvature peaks of the
     telemetry coordinates, braking zones) fused when closer than ``merge_detectors_m``;
  2. CONSENSUS across laps: candidates grouped by lap position (``cluster_tol_m`` / fraction),
     kept when they appear in >= ``min_share`` of the laps (relaxed with < 3 laps, lower confidence);
  3. TRACK TEMPLATE (only when the circuit is recognised and its measured length fits): bends of
     the game's racing line (``circuits.get_track_geometry``) with radius < ``template_max_radius_m``
     and the tabulated corners (``circuits.json``) are candidates too. A template corner is refined
     with the nearest telemetry evidence; without evidence it is KEPT as 'flat_out'/'kink'
     at its geometric position instead of being dropped;
  4. telemetry candidates with no template/table backing are low confidence or discarded;
  5. chicanes / compound corners (apexes closer than ``group_gap_m``) become ONE corner with
     ``sub_apexes`` (never merging two separately tabulated corners);
  6. names with ``circuits.assign_names`` (one to one, in order). A tabulated corner nobody
     found is instantiated as a virtual corner (``kind`` 'flat_out' or its own ``kind``).

The function is deterministic, uses only versioned JSON (never the installed game) and
takes well under a second for a typical session file.
"""
from __future__ import annotations

import logging
import statistics
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from src.analytics import circuits as C
from src.analytics.geometry import detectar_apexes_perfectos, procesar_geometria_pista_perfecta
from src.telemetry.metrics import BRAKE_THRESHOLD_PCT, detect_apex_points

logger = logging.getLogger(__name__)

KINDS = ("braking", "lift", "flat_out", "kink")

DEFAULTS: dict = {
    # -- candidates -------------------------------------------------------------------------
    "merge_detectors_m": 60.0,       # detections of different detectors in one lap closer than this are one event
    "brake_zone_search_m": 150.0,    # a braking zone with no speed/curvature event within this after it is a candidate itself
    # -- consensus --------------------------------------------------------------------------
    "cluster_tol_frac": 0.012,       # cluster half-width, as a fraction of the lap ...
    "cluster_tol_min_m": 60.0,       # ... but never below this many metres
    "min_share": 0.6,                # share of the laps a candidate must appear in
    "relaxed_share": 0.5,            # same, with fewer than 3 laps (any single lap is enough with 2 laps)
    "relaxed_below_laps": 3,
    # -- template ---------------------------------------------------------------------------
    "use_geometry": True,            # use the track geometry template when available
    "use_table": True,               # use tabulated corners (circuits.json) as template / virtual corners
    "template_max_radius_m": 400.0,  # geometric bends sharper than this are candidates
    "table_atom_tol_m": 150.0,       # an atom this close (and within the circuit matching tolerance) to a tabulated corner belongs to it
    "match_pad_m": 90.0,             # telemetry cluster within this of a template corner supports it
    "unbacked_min_support": 0.4,     # telemetry-only corner on a known circuit needs this telemetry support
    "prior_laps": 4.0,               # the template position counts as this many laps of evidence (shrinkage; 0 = pure telemetry)
    "kink_max_radius_m": 200.0,      # evidence-less, unnamed template bends sharper than this stay as 'kink'
    # -- grouping ---------------------------------------------------------------------------
    "group_gap_m": 120.0,            # apexes closer than this form one compound corner ...
    "group_max_span_m": 200.0,       # ... but a compound corner never spans more than this (no chaining of a whole sector)
    # -- evidence ---------------------------------------------------------------------------
    "speed_drop_min_kmh": 3.0,       # speed minimum counts if speed recovers at least this much on both sides
    "brake_present_pct": 8.0,        # braking counts above this brake pressure (0-100)
    "throttle_lift_pct": 85.0,       # throttle below this near the apex = lift
    "window_before_m": 200.0,        # evidence window before the apex ...
    "window_after_m": 150.0,         # ... and after it (both cut at the midpoint to the neighbour corner)
    "kink_radius_m": 200.0,          # flat-out + unnamed + radius at least this = 'kink'
    "braking_share": 0.5,            # corner is 'braking' if braked in at least this share of laps
    "min_confidence": 0.3,           # corners below this are discarded (listed in result['discarded'])
}

_MIN_LAP_M = 500.0
# Channels any step reads (geometry.py also synthesises coordinates from yaw / GPS). Session frames can have 150+
# columns: working on this subset keeps the map well under a second for a 20-lap file.
_KEEP = ("Distance", "Speed", "Brake", "Throttle", "CarCoordX", "CarCoordY", "CarCoordZ", "YawNorth",
         "Gyro Yaw Angle", "Yaw", "YawRate", "SteerAngle", "SteeringWheelAngle", "Lat", "Lon", "GPSlat", "GPSlon",
         "GPS Lat", "GPS Lon", "gps_lat", "gps_lon")


# ── Input handling ─────────────────────────────────────────────────────────────────

def _num(df: pd.DataFrame, col: str) -> Optional[np.ndarray]:
    if col not in df.columns:
        return None
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)


def _prepare_lap(df: pd.DataFrame, warnings: list, idx: int) -> Optional[dict]:
    """Normalise one lap: distance from 0, 1 m grids of speed / brake (0-100) / throttle (0-100)."""
    if not isinstance(df, pd.DataFrame) or "Distance" not in df.columns or "Speed" not in df.columns:
        warnings.append(f"lap {idx}: needs Distance and Speed columns; ignored")
        return None
    d = _num(df, "Distance")
    sp = _num(df, "Speed")
    ok = np.isfinite(d) & np.isfinite(sp)
    if ok.sum() < 20:
        warnings.append(f"lap {idx}: too few valid samples; ignored")
        return None
    sub = df[[c for c in _KEEP if c in df.columns]].loc[ok].copy()
    sub = sub.assign(Distance=d[ok], Speed=sp[ok])
    sub = sub.drop_duplicates(subset=["Distance"]).sort_values("Distance").reset_index(drop=True)
    d0 = float(sub["Distance"].iloc[0])
    sub["Distance"] = sub["Distance"] - d0
    length = float(sub["Distance"].iloc[-1])
    if length < _MIN_LAP_M:
        warnings.append(f"lap {idx}: only {length:.0f} m long; ignored")
        return None
    dd = sub["Distance"].to_numpy(dtype=float)
    grid = np.arange(0.0, np.floor(length) + 1.0, 1.0)
    speed = np.interp(grid, dd, sub["Speed"].to_numpy(dtype=float))

    def chan(col: str) -> Optional[np.ndarray]:
        v = _num(sub, col)
        if v is None or not np.isfinite(v).any():
            return None
        v = np.where(np.isfinite(v), v, 0.0)
        g = np.interp(grid, dd, v)
        return g * 100.0 if np.nanmax(g) <= 1.05 else g

    return {"df": sub, "length": length, "grid": grid, "speed": speed,
            "brake": chan("Brake"), "throttle": chan("Throttle")}


def _signed_curvature(lap: dict) -> Optional[np.ndarray]:
    """Sign of the turn per metre (+1 left / -1 right) from CarCoordX/Y, or None without coordinates."""
    df = lap["df"]
    if "CarCoordX" not in df.columns or "CarCoordY" not in df.columns:
        return None
    x, y = _num(df, "CarCoordX"), _num(df, "CarCoordY")
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 50:
        return None
    d = df["Distance"].to_numpy(dtype=float)[ok]
    grid = lap["grid"]
    xs = np.interp(grid, d, x[ok])
    ys = np.interp(grid, d, y[ok])
    from scipy.signal import savgol_filter
    if len(grid) < 90:
        return None
    xs = savgol_filter(xs, 75, 2)
    ys = savgol_filter(ys, 75, 2)
    dx, dy = np.gradient(xs), np.gradient(ys)
    ddx, ddy = np.gradient(dx), np.gradient(dy)
    return dx * ddy - dy * ddx   # sign only is used


# ── Step 1: per-lap candidates ────────────────────────────────────────────────────────

def _brake_zones(brake: np.ndarray) -> list:
    """[(start_m, end_m, peak_pct)] of braking zones (same threshold/hysteresis as metrics.detect_braking_points)."""
    zones, start = [], None
    rel = BRAKE_THRESHOLD_PCT * 0.5
    for i in range(1, len(brake)):
        if start is None and brake[i] >= BRAKE_THRESHOLD_PCT and brake[i - 1] < BRAKE_THRESHOLD_PCT:
            start = i
        elif start is not None and brake[i] < rel:
            zones.append((float(start), float(i), float(np.max(brake[start:i]))))
            start = None
    if start is not None:
        zones.append((float(start), float(len(brake) - 1), float(np.max(brake[start:]))))
    return zones


def _lap_candidates(lap: dict, opts: dict) -> list:
    """Events of one lap: [{'pos': m, 'src': set}] fused across detectors."""
    raw: list = []
    grid = lap["grid"]
    try:
        for a in detect_apex_points(pd.DataFrame({"Distance": grid, "Speed": lap["speed"]})):
            raw.append((float(a["distance"]), "speed"))
    except Exception as exc:  # noqa: BLE001 - one broken detector must not abort the map
        logger.debug("corner_map: speed detector failed: %s", exc)
    try:
        g = procesar_geometria_pista_perfecta(lap["df"])
        if "Curvature" in g.columns and float(g["Curvature"].max()) > 0:
            for _, r in detectar_apexes_perfectos(g).iterrows():
                raw.append((float(r["Distance"]), "geometry"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("corner_map: geometry detector failed: %s", exc)
    if lap["brake"] is not None:
        for s, e, _pk in _brake_zones(lap["brake"]):
            near = any(s - 30.0 <= p <= e + opts["brake_zone_search_m"] for p, _ in raw)
            if not near:
                raw.append((e, "brake"))
    raw.sort()
    events: list = []
    for p, src in raw:
        if events and p - events[-1]["pts"][-1] <= opts["merge_detectors_m"]:
            events[-1]["pts"].append(p)
            events[-1]["src"].add(src)
        else:
            events.append({"pts": [p], "src": {src}})
    return [{"pos": float(np.median(e["pts"])), "src": e["src"]} for e in events]


# ── Step 2: consensus ───────────────────────────────────────────────────────────────

def _cluster(per_lap: list, lengths: list, L: float, opts: dict) -> list:
    """Cluster events of all laps by lap fraction. Each lap contributes at most one event per cluster."""
    tol = max(opts["cluster_tol_min_m"], opts["cluster_tol_frac"] * L)
    pts = []
    for li, (events, ln) in enumerate(zip(per_lap, lengths)):
        for e in events:
            pts.append((e["pos"] / ln * L, li, e["src"]))
    pts.sort(key=lambda p: p[0])
    clusters: list = []
    for p, li, src in pts:
        if clusters and abs(p - float(np.median([q[0] for q in clusters[-1]]))) <= tol:
            clusters[-1].append((p, li, src))
        else:
            clusters.append([(p, li, src)])
    n = len(per_lap)
    out = []
    for cl in clusters:
        med = float(np.median([q[0] for q in cl]))
        best: dict = {}
        for p, li, src in cl:   # one event per lap: the closest to the cluster median
            if li not in best or abs(p - med) < abs(best[li][0] - med):
                best[li] = (p, src)
        poss = [v[0] for v in best.values()]
        srcs = set().union(*[v[1] for v in best.values()])
        out.append({"pos": float(np.median(poss)), "laps": sorted(best), "share": len(best) / n, "src": srcs,
                    "n_src": len(srcs)})
    return out


# ── Step 3: template ────────────────────────────────────────────────────────────────

def _build_template(circuit: dict, L: float, opts: dict) -> list:
    """Template corners: [{'lo','hi','pos','atoms':[...], 'owner': table corner|None, 'src': set}] sorted by position."""
    atoms: list = []
    if opts["use_geometry"]:
        geo = C.get_track_geometry(circuit["id"])
        if geo:
            seen = set()
            for g in geo["corners"]:
                for a in g.get("sub_apexes") or []:
                    key = round(float(a["fraction"]), 5)
                    if key in seen:
                        continue
                    seen.add(key)
                    r = float(a["radius_m"])
                    if r < opts["template_max_radius_m"]:
                        atoms.append({"pos": float(a["fraction"]) * L, "radius": r,
                                      "direction": a.get("direction"), "owner": None})
    table = sorted(circuit.get("corners") or [], key=lambda k: k["apex_fraction"]) if opts["use_table"] else []
    tol = min(opts["table_atom_tol_m"], C.apex_tolerance_m(L, circuit))
    # one-to-one ownership atom <-> tabulated corner (nearest first)
    pairs = sorted(((abs(a["pos"] - k["apex_fraction"] * L), ai, ki)
                    for ai, a in enumerate(atoms) for ki, k in enumerate(table)
                    if abs(a["pos"] - k["apex_fraction"] * L) <= tol), key=lambda t: t[0])
    used_a, used_k = set(), set()
    for _gap, ai, ki in pairs:
        if ai in used_a or ki in used_k:
            continue
        used_a.add(ai)
        used_k.add(ki)
        atoms[ai]["owner"] = ki
    # group atoms: gap < group_gap_m, never joining atoms owned by different tabulated corners
    atoms.sort(key=lambda a: a["pos"])
    groups: list = []
    for a in atoms:
        if groups:
            last = groups[-1]
            owners = {x["owner"] for x in last if x["owner"] is not None}
            if a["pos"] - last[-1]["pos"] < opts["group_gap_m"] and a["pos"] - last[0]["pos"] <= opts["group_max_span_m"] and not (
                    a["owner"] is not None and owners and a["owner"] not in owners):
                last.append(a)
                continue
        groups.append([a])
    template = []
    for grp in groups:
        owners = [x["owner"] for x in grp if x["owner"] is not None]
        main = min(grp, key=lambda x: x["radius"])
        # tabulated corner owned: position follows the atom of the owner when several atoms
        template.append({"lo": grp[0]["pos"], "hi": grp[-1]["pos"], "pos": main["pos"], "atoms": grp,
                         "owner": owners[0] if owners else None, "src": {"track_geometry"}})
    for ki, k in enumerate(table):
        if ki in used_k:
            continue
        p = k["apex_fraction"] * L
        template.append({"lo": p, "hi": p, "pos": p, "atoms": [], "owner": ki, "src": {"table"}})
    for t in template:
        if t["owner"] is not None:
            t["src"].add("table")
    template.sort(key=lambda t: t["pos"])
    return template


# ── Evidence ───────────────────────────────────────────────────────────────────────

def _lap_evidence(lap: dict, p_ref: float, L: float, lo_ref: float, hi_ref: float, opts: dict,
                  kappa: Optional[np.ndarray]) -> dict:
    """Telemetry evidence of one corner in one lap (positions scaled from the reference length)."""
    k = lap["length"] / L
    p, lo, hi = p_ref * k, lo_ref * k, hi_ref * k
    n = len(lap["grid"])
    a, b = int(max(0, np.floor(lo))), int(min(n - 1, np.ceil(hi)))
    out = {"speed_min": None, "speed_present": False, "drop": 0.0, "speed_at_min_pos": None,
           "brake_peak": None, "brake_present": False, "throttle_min": None, "lift": False}
    if b - a < 8:
        return out
    s = lap["speed"][a:b + 1]
    i = int(np.argmin(s))
    out["speed_min"] = float(s[i])
    drop = min(float(np.max(s[:i + 1])), float(np.max(s[i:]))) - float(s[i])
    out["drop"] = drop
    interior = 3 <= i <= len(s) - 4
    if drop >= opts["speed_drop_min_kmh"] and interior:
        out["speed_present"] = True
        out["speed_at_min_pos"] = (a + i) / k
    if lap["brake"] is not None:
        bb = lap["brake"][a:int(min(n - 1, np.ceil(p + 20)))+1]
        pk = float(np.max(bb)) if len(bb) else 0.0
        out["brake_peak"] = pk
        out["brake_present"] = pk >= opts["brake_present_pct"]
    if lap["throttle"] is not None:
        tt = lap["throttle"][int(max(0, p - 80)):int(min(n, p + 40))]
        if len(tt):
            out["throttle_min"] = float(np.min(tt))
            out["lift"] = out["throttle_min"] <= opts["throttle_lift_pct"]
    if kappa is not None:
        kk = np.abs(kappa[a:b + 1])
        out["_kmax"] = float(np.max(kk)) if len(kk) else 0.0
    return out


def _direction(kappa: Optional[np.ndarray], lap_len: float, L: float, pos: float) -> Optional[str]:
    if kappa is None:
        return None
    i = int(round(pos * lap_len / L))
    seg = kappa[max(0, i - 15): i + 16]
    if not len(seg):
        return None
    m = float(np.median(seg))
    if m == 0:
        return None
    return "left" if m > 0 else "right"


# ── Main ───────────────────────────────────────────────────────────────────────────

def build_corner_map(laps, venue=None, lap_length_m: Optional[float] = None, options: Optional[dict] = None) -> dict:
    """
    Build the unified corner map.

    Args:
        laps: DataFrame of one lap, or a list of DataFrames (clean laps; raw or aligned) with
              Distance and Speed and, when present, Brake, Throttle, CarCoordX/CarCoordY.
        venue: telemetry venue text (circuits.find_circuit). None = unknown circuit, no names.
        lap_length_m: lap length for the reference scale (default: median measured length).
        options: overrides of ``DEFAULTS`` (see the module docstring).

    Returns {'corners': [...], 'discarded': [...], 'summary': {...}}. See docs/CORNER_DETECTION.md.
    """
    opts = dict(DEFAULTS)
    if options:
        unknown = set(options) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown options: {sorted(unknown)}")
        opts.update(options)
    warnings: list = []
    if isinstance(laps, pd.DataFrame):
        laps = [laps]
    prepared = [p for p in (_prepare_lap(l, warnings, i) for i, l in enumerate(laps or [])) if p is not None]
    n_laps = len(prepared)
    method = "consensus+template"
    if not n_laps:
        warnings.append("no usable laps")
        return {"corners": [], "discarded": [], "summary": _summary([], [], None, opts, "none", warnings, 0, None)}

    lengths = [p["length"] for p in prepared]
    L = float(lap_length_m) if lap_length_m and lap_length_m > 0 else float(np.median(lengths))
    info = C.recognize(venue, L) if venue else None
    circuit = None
    if info and info["recognized"]:
        if info["matched"]:
            circuit = C.get_circuit(info["id"])
        else:
            warnings.append(f"venue {info['id']} known but measured length {L:.0f} m does not fit "
                            f"({info['length_m']:.0f} m): no template, no names")
    elif venue:
        warnings.append("unknown circuit: telemetry consensus only, no names")
    else:
        warnings.append("no venue given: telemetry consensus only, no names")
    if n_laps < opts["relaxed_below_laps"]:
        warnings.append(f"only {n_laps} lap(s): relaxed consensus, lower confidence")
    # per-lap telemetry events + signed curvature
    per_lap = [_lap_candidates(p, opts) for p in prepared]
    kappas = [_signed_curvature(p) for p in prepared]
    clusters = _cluster(per_lap, lengths, L, opts)
    need = opts["relaxed_share"] if n_laps < opts["relaxed_below_laps"] else opts["min_share"]
    template = _build_template(circuit, L, opts) if circuit else []
    if circuit and not template:
        method = "consensus"
    if not circuit:
        method = "consensus"
    rel = 1.0 if n_laps >= 3 else (0.8 if n_laps == 2 else 0.6)

    def support(cl: dict) -> float:
        return min(0.9, cl["share"] * rel * (0.55 + 0.15 * cl["n_src"]))

    # -- merge telemetry clusters and template
    items: list = []
    absorbed = set()
    pad = opts["match_pad_m"]
    for t in template:
        mine = []
        for ci, cl in enumerate(clusters):
            if t["lo"] - pad <= cl["pos"] <= t["hi"] + pad:
                mine.append(ci)
        items.append({"t": t, "cl": [clusters[i] for i in mine]})
        absorbed.update(mine)
    free = [cl for ci, cl in enumerate(clusters) if ci not in absorbed]
    # telemetry-only clusters: kept if consensus holds (known circuit: and enough support)
    free_ok = [cl for cl in free if cl["share"] >= need - 1e-9]
    discarded: list = []
    for cl in free:
        if cl not in free_ok:
            discarded.append({"apex_distance_m": round(cl["pos"], 1), "fraction": round(cl["pos"] / L, 4),
                              "reason": "no consensus", "share": round(cl["share"], 3),
                              "sources": sorted(cl["src"])})
    groups: list = []
    for cl in sorted(free_ok, key=lambda c: c["pos"]):
        if groups and cl["pos"] - groups[-1][-1]["pos"] < opts["group_gap_m"]                 and cl["pos"] - groups[-1][0]["pos"] <= opts["group_max_span_m"]:
            groups[-1].append(cl)
        else:
            groups.append([cl])
    for g in groups:
        top = max(g, key=support)
        sup = support(top)
        if template and sup < opts["unbacked_min_support"]:
            discarded.append({"apex_distance_m": round(top["pos"], 1), "fraction": round(top["pos"] / L, 4),
                              "reason": "no track/table backing", "share": round(top["share"], 3),
                              "sources": sorted(top["src"])})
            continue
        items.append({"t": None, "cl": g})

    corners: list = []
    for it in items:
        t, cls = it["t"], it["cl"]
        # keep telemetry clusters with consensus (template-backed ones need only the relaxed share of 1 lap in 3)
        good = [c for c in cls if c["share"] >= need - 1e-9]
        if t is not None:
            if good:
                top = max(good, key=lambda c: (round(c["share"], 2), -abs(c["pos"] - t["pos"])))
                # shrink the telemetry position towards the template: n laps of evidence vs `prior_laps` of prior
                n_eff = len(top["laps"])
                alpha = n_eff / (n_eff + opts["prior_laps"]) if opts["prior_laps"] > 0 else 1.0
                pos = t["pos"] + alpha * (top["pos"] - t["pos"])
            else:
                top, pos = None, t["pos"]
            lo = min([t["lo"]] + [c["pos"] for c in good])
            hi = max([t["hi"]] + [c["pos"] for c in good])
            subs = [{"fraction": a["pos"] / L, "distance_m": a["pos"], "radius_m": a["radius"],
                     "direction": a["direction"]} for a in t["atoms"]]
            radius = min([a["radius"] for a in t["atoms"]], default=None)
            sources = set(t["src"]) | set().union(*[c["src"] for c in good]) if good else set(t["src"])
            tel_support = support(top) if top else 0.0
            w = [tel_support, 0.6 if "track_geometry" in t["src"] else 0.0, 0.5 if "table" in t["src"] else 0.0]
            conf = 1.0 - float(np.prod([1.0 - x for x in w]))
            owner = t["owner"]
        else:
            top = max(cls, key=support)
            pos = top["pos"]
            lo, hi = cls[0]["pos"], cls[-1]["pos"]
            subs = [{"fraction": c["pos"] / L, "distance_m": c["pos"], "radius_m": None, "direction": None}
                    for c in cls]
            radius = None
            sources = set().union(*[c["src"] for c in cls])
            conf = support(top) * (0.5 if template else 1.0)
            owner = None
        corners.append({"pos": pos, "lo": lo, "hi": hi, "subs": subs, "radius": radius, "src": sources,
                        "conf": conf, "cluster": top, "template": t, "owner": owner,
                        "all_cl": cls if t is None else good})
    corners.sort(key=lambda c: c["pos"])

    # -- evidence, kind, direction per corner
    positions = [c["pos"] for c in corners]
    result: list = []
    for j, c in enumerate(corners):
        prev_mid = (positions[j - 1] + c["pos"]) / 2.0 if j else -1e9
        next_mid = (positions[j + 1] + c["pos"]) / 2.0 if j + 1 < len(corners) else 1e9
        lo_w = max(c["lo"] - opts["window_before_m"], prev_mid, 0.0)
        hi_w = min(c["hi"] + opts["window_after_m"], next_mid, L)
        evs = [_lap_evidence(p, c["pos"], L, lo_w, hi_w, opts, kp) for p, kp in zip(prepared, kappas)]
        n = len(evs)
        sp = [e for e in evs if e["speed_present"]]
        br = [e for e in evs if e["brake_present"]]
        lf = [e for e in evs if e["lift"]]
        found = sum(1 for e in evs if e["speed_present"] or e["brake_present"] or e["lift"])
        flat_share = 1.0 - found / n
        speed_share, brake_share = len(sp) / n, len(br) / n
        smin = [e["speed_min"] for e in evs if e["speed_min"] is not None]
        bpk = [e["brake_peak"] for e in evs if e["brake_peak"] is not None]
        tmin = [e["throttle_min"] for e in evs if e["throttle_min"] is not None]
        kmax = [e["_kmax"] for e in evs if e.get("_kmax")]
        radius = c["radius"]
        if radius is None and kmax:
            radius = float(1.0 / max(statistics.median(kmax), 1e-4))
        if brake_share >= opts["braking_share"]:
            kind = "braking"
        elif speed_share >= 0.5 or len(lf) / n >= 0.5:
            kind = "lift"
        else:
            kind = "flat_out"
            if c["owner"] is None and (radius is None or radius >= opts["kink_radius_m"]):
                kind = "kink"
        # direction: template atom, else telemetry coordinates
        direction = None
        if c["template"] is not None and c["template"]["atoms"]:
            main = min(c["template"]["atoms"], key=lambda a: a["radius"])
            direction = main["direction"]
        if direction is None:
            votes = [d for d in (_direction(kp, p["length"], L, c["pos"]) for p, kp in zip(prepared, kappas)) if d]
            if votes:
                direction = max(set(votes), key=votes.count)
        sources = set(c["src"])
        if brake_share >= 0.5:
            sources.add("brake")
        if speed_share >= 0.5:
            sources.add("speed")
        tel_conf = c["conf"]
        # evidence-less template corner: confidence already carries only template/table weights
        ev = {"laps_found": found, "laps_total": n,
              "detection_share": round(c["cluster"]["share"], 3) if c["cluster"] else 0.0,
              "speed_min_kmh": round(float(statistics.median(smin)), 1) if smin else None,
              "speed_min_share": round(speed_share, 3),
              "speed_drop_kmh": round(float(statistics.median([e["drop"] for e in evs])), 1),
              "brake_peak_pct": round(float(statistics.median(bpk)), 1) if bpk else None,
              "brake_share": round(brake_share, 3),
              "throttle_min_pct": round(float(statistics.median(tmin)), 1) if tmin else None}
        subs = c["subs"]
        if len(subs) > 1:
            is_complex = True
        else:
            is_complex = False
        result.append({"_c": c, "pos": c["pos"], "lo": c["lo"], "hi": c["hi"], "kind": kind, "direction": direction,
                       "radius": radius, "sources": sources, "conf": tel_conf, "evidence": ev,
                       "flat": flat_share, "subs": subs, "complex": is_complex, "evs": evs})

    # -- naming (one to one, in order); tabulated corners nobody matched become virtual corners
    final = _finalise(result, circuit, L, opts, discarded, prepared)
    summary = _summary(final, discarded, info if circuit or info else None, opts, method, warnings, n_laps, L)
    return {"corners": final, "discarded": discarded, "summary": summary}


def _finalise(result: list, circuit: Optional[dict], L: float, opts: dict, discarded: list, prepared: list) -> list:
    kept = []
    for r in result:
        if r["conf"] < opts["min_confidence"] and r["_c"]["owner"] is None:
            discarded.append({"apex_distance_m": round(r["pos"], 1), "fraction": round(r["pos"] / L, 4),
                              "reason": "low confidence", "share": r["evidence"]["detection_share"],
                              "sources": sorted(r["sources"])})
            continue
        # evidence-less, unnamed template corner: a kink only counts if the bend is sharp enough
        c = r["_c"]
        if (c["template"] is not None and c["owner"] is None and not c["all_cl"]
                and r["flat"] >= 0.999 and (r["radius"] is None or r["radius"] >= opts["kink_max_radius_m"])):
            discarded.append({"apex_distance_m": round(r["pos"], 1), "fraction": round(r["pos"] / L, 4),
                              "reason": "flat-out bend above kink radius", "share": 0.0,
                              "sources": sorted(r["sources"])})
            continue
        kept.append(r)
    kept.sort(key=lambda r: r["pos"])
    names: dict = {}
    if circuit:
        names = C.assign_names(circuit, [(i, r["pos"]) for i, r in enumerate(kept)], L)
    out = []
    for i, r in enumerate(kept):
        nm = names.get(i)
        kind = r["kind"]
        out.append(_corner_dict(i + 1, r, nm["name"] if nm else None, nm["order"] if nm else None, kind, L, kept, i))
    return out


def _corner_dict(number: int, r: dict, name: Optional[str], order: Optional[int], kind: str, L: float,
                 kept: list, i: int) -> dict:
    pos = r["pos"]
    prev_end = (kept[i - 1]["pos"] + pos) / 2.0 if i else 0.0
    next_start = (kept[i + 1]["pos"] + pos) / 2.0 if i + 1 < len(kept) else L
    start = max(prev_end, min(r["lo"], pos) - (60.0 if kind == "braking" else 30.0))
    end = min(next_start, max(r["hi"], pos) + 40.0)
    subs = [{"fraction": round(float(s["fraction"]), 5), "distance_m": round(float(s["distance_m"]), 1),
             "radius_m": None if s["radius_m"] is None else round(float(s["radius_m"]), 1),
             "direction": s["direction"]} for s in r["subs"]]
    return {
        "number": number, "name": name, "table_order": order,
        "fraction": round(pos / L, 5), "apex_distance_m": round(float(pos), 1),
        "start_m": round(float(start), 1), "end_m": round(float(end), 1),
        "kind": kind, "direction": r["direction"],
        "min_radius_m": None if r["radius"] is None else round(float(r["radius"]), 1),
        "sources": sorted(r["sources"]), "confidence": round(float(min(1.0, r["conf"])), 3),
        "evidence": r["evidence"], "is_complex": bool(r["complex"]), "sub_apexes": subs,
        "flat_out_share": round(float(r["flat"]), 3),
    }


def _summary(corners: list, discarded: list, info: Optional[dict], opts: dict, method: str, warnings: list,
             n_laps: int, L: Optional[float]) -> dict:
    circuit = None
    if info and info.get("recognized"):
        circuit = {k: info.get(k) for k in ("id", "name", "short_name", "length_m", "matched", "confidence")}
    return {"n_corners": len(corners), "n_named": sum(1 for c in corners if c.get("name")),
            "n_discarded": len(discarded), "n_laps": n_laps,
            "lap_length_m": None if L is None else round(float(L), 1),
            "circuit": circuit, "method": method, "params": dict(opts), "warnings": warnings}
