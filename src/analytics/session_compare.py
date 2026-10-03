"""Comparacion de dos sesiones guardadas (mismo circuito y coche).

Funciones puras sobre los payloads ``{session, stint, extras}``; sin acceso a BD.
Convencion: todos los deltas son B - A (negativo = B mas rapido / pierde menos).
"""
from __future__ import annotations

import statistics
from typing import Any, Optional

from src.i18n import _l

APEX_MATCH_TOLERANCE_M = 60.0
PACE_EPS_S = 0.005          # por debajo de esto se considera "igual"
CORNER_EPS_S = 0.01


def norm_key(value: Optional[str]) -> str:
    return " ".join((value or "").casefold().split())


def compatibility(a: dict, b: dict) -> dict:
    """Compatibilidad por circuito y coche. Un dato ausente se considera desconocido."""
    issues: list[str] = []
    warnings: list[str] = []
    for field in ("venue", "vehicle"):
        va, vb = norm_key(a.get(field)), norm_key(b.get(field))
        if va and vb and va != vb:
            issues.append(field)
        elif not va or not vb:
            warnings.append(field)
    return {"compatible": not issues, "mismatch": issues, "unknown": warnings}


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _dicts(v: Any) -> list[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _lap_no(raw: Any, fallback: int) -> int:
    n = _num(raw)
    return int(n) if n is not None else fallback


def racing_laps(payload: dict) -> list[dict]:
    """[{lap, time}] de vueltas validas (sin pit/outliers). Prefiere el stint. Tolera payloads vacios o raros."""
    out: list[dict] = []
    stint = _d(_d(payload).get("stint"))
    for lap in _dicts(stint.get("laps")):
        t = _num(lap.get("lap_time_s"))
        if t and t > 0 and not lap.get("is_pit_lap"):
            out.append({"lap": _lap_no(lap.get("lap_number"), len(out) + 1), "time": t})
    if out:
        return out
    sess = _d(_d(payload).get("session"))
    for lap in _dicts(sess.get("laps")):
        t = _num(lap.get("lap_time"))
        if t and t > 0 and not lap.get("is_pit_lap"):
            out.append({"lap": _lap_no(lap.get("lap_number"), len(out) + 1), "time": t})
    return out


def pace_stats(laps: list[dict]) -> dict:
    times = [l["time"] for l in laps]
    if not times:
        return {"n": 0, "best": None, "mean": None, "median": None, "std": None}
    return {
        "n": len(times),
        "best": min(times),
        "mean": statistics.fmean(times),
        "median": statistics.median(times),
        "std": statistics.stdev(times) if len(times) > 1 else None,
    }


def _delta(a: Optional[float], b: Optional[float], nd: int = 3) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(b - a, nd)


def _corner_distance(c: dict) -> Optional[float]:
    for k in ("apex_distance_m", "apex_distance", "distance_m"):
        v = _num(c.get(k))
        if v is not None:
            return v
    return None


def match_corners(ca: list[dict], cb: list[dict]) -> tuple[list[tuple[dict, dict]], str]:
    """Empareja curvas por distancia de apice (si ambas la traen) o por numero de curva."""
    if ca and cb and all(_corner_distance(c) is not None for c in ca + cb):
        pairs: list[tuple[dict, dict]] = []
        free = list(cb)
        for a in sorted(ca, key=_corner_distance):
            if not free:
                break
            best = min(free, key=lambda c: abs(_corner_distance(c) - _corner_distance(a)))
            if abs(_corner_distance(best) - _corner_distance(a)) <= APEX_MATCH_TOLERANCE_M:
                pairs.append((a, best))
                free.remove(best)
        return pairs, "apex_distance"
    by_num = {c.get("corner_number"): c for c in cb}
    return [(a, by_num[a.get("corner_number")]) for a in ca if a.get("corner_number") in by_num], "corner_number"


def compare_corners(pa: dict, pb: dict, different_circuit: bool = False) -> dict:
    def corners(p):
        cs = _d(_d(_d(p).get("stint")).get("curvas_sesion"))
        return [c for c in _dicts(cs.get("corners")) if _num(c.get("time_loss_seconds")) is not None]

    ca, cb = corners(pa), corners(pb)
    if not ca or not cb:
        return {"available": False, "items": [], "matched_by": None}
    if different_circuit:      # corner N of one track is not corner N of another: do not pair them
        return {"available": False, "items": [], "matched_by": None, "reason": "different_circuit"}
    pairs, how = match_corners(ca, cb)
    items = []
    for a, b in pairs:
        la, lb = float(a["time_loss_seconds"]), float(b["time_loss_seconds"])
        items.append({
            "corner": a.get("corner_number"),
            "corner_b": b.get("corner_number"),
            "apex_distance_m": _corner_distance(a),
            "loss_a": round(la, 3),
            "loss_b": round(lb, 3),
            "delta": round(lb - la, 3),
        })
    items.sort(key=lambda i: (i["corner"] is None, str(type(i["corner"]).__name__), i["corner"] if i["corner"] is not None else 0))
    return {"available": bool(items), "items": items, "matched_by": how}


def _degradation(p: dict) -> Optional[float]:
    d = _d(_d(_d(p).get("stint")).get("degradacion"))
    return _num(d.get("tasa_s_per_lap")) if d.get("available") else None


def _fuel(p: dict) -> Optional[float]:
    f = _d(_d(_d(p).get("stint")).get("combustible"))
    return _num(f.get("consumo_medio_l")) if f.get("available") else None


def _fmt_s(x: float) -> str:
    return f"{abs(x):.3f}"


def _faster_text(lang: str, key_a: str, key_b: str, key_eq: str, delta: Optional[float], **kw) -> Optional[str]:
    if delta is None:
        return None
    if abs(delta) < PACE_EPS_S:
        return _l(lang, key_eq, **kw)
    return _l(lang, key_b if delta < 0 else key_a, d=_fmt_s(delta), **kw)


def build_summary(lang: str, kpis: dict, corners: dict, deg: dict, fuel: dict) -> list[str]:
    lines: list[str] = []
    t = _faster_text(lang, "lib_cmp_best_slower", "lib_cmp_best_faster", "lib_cmp_best_equal", kpis["best"]["delta"])
    if t:
        lines.append(t)
    t = _faster_text(lang, "lib_cmp_mean_slower", "lib_cmp_mean_faster", "lib_cmp_mean_equal", kpis["mean"]["delta"])
    if t:
        lines.append(t)
    sd = kpis["std"]["delta"]
    if sd is not None and abs(sd) >= PACE_EPS_S:
        lines.append(_l(lang, "lib_cmp_std_less" if sd < 0 else "lib_cmp_std_more", d=_fmt_s(sd)))
    if corners.get("available"):
        items = corners["items"]
        gain = min(items, key=lambda i: i["delta"])
        loss = max(items, key=lambda i: i["delta"])
        if gain["delta"] <= -CORNER_EPS_S:
            lines.append(_l(lang, "lib_cmp_corner_gain", n=gain["corner"], d=_fmt_s(gain["delta"])))
        if loss["delta"] >= CORNER_EPS_S:
            lines.append(_l(lang, "lib_cmp_corner_loss", n=loss["corner"], d=_fmt_s(loss["delta"])))
    if deg["delta"] is not None and abs(deg["delta"]) >= 0.01:
        lines.append(_l(lang, "lib_cmp_deg_more" if deg["delta"] > 0 else "lib_cmp_deg_less", d=f"{abs(deg['delta']):.3f}"))
    if fuel["delta"] is not None and abs(fuel["delta"]) >= 0.01:
        lines.append(_l(lang, "lib_cmp_fuel_more" if fuel["delta"] > 0 else "lib_cmp_fuel_less", d=f"{abs(fuel['delta']):.2f}"))
    if not lines:
        lines.append(_l(lang, "lib_cmp_no_data"))
    return lines


def compare_sessions(pa: dict, pb: dict, lang: str = "es", venue_a: Optional[str] = None,
                     venue_b: Optional[str] = None) -> dict:
    la, lb = racing_laps(pa), racing_laps(pb)
    sa, sb = pace_stats(la), pace_stats(lb)
    kpis = {
        k: {"a": sa[k], "b": sb[k], "delta": _delta(sa[k], sb[k])}
        for k in ("best", "mean", "median", "std")
    }
    kpis["laps"] = {"a": sa["n"], "b": sb["n"], "delta": sb["n"] - sa["n"]}

    different_circuit = norm_key(venue_a) != norm_key(venue_b) and bool(norm_key(venue_a) and norm_key(venue_b))
    corners = compare_corners(pa, pb, different_circuit)
    da, db_ = _degradation(pa), _degradation(pb)
    fa, fb = _fuel(pa), _fuel(pb)
    deg = {"a": da, "b": db_, "delta": _delta(da, db_, 4)}
    fuel = {"a": fa, "b": fb, "delta": _delta(fa, fb)}

    # Vuelta a vuelta: se enumeran las vueltas validas en orden (A y B pueden tener huecos distintos).
    n = max(len(la), len(lb))
    series = [
        {"index": i + 1,
         "lap_a": la[i]["lap"] if i < len(la) else None, "a": la[i]["time"] if i < len(la) else None,
         "lap_b": lb[i]["lap"] if i < len(lb) else None, "b": lb[i]["time"] if i < len(lb) else None}
        for i in range(n)
    ]

    return {
        "kpis": kpis,
        "corners": corners,
        "degradation": deg,
        "fuel": fuel,
        "series": {"laps": series},
        "summary": build_summary(lang, kpis, corners, deg, fuel),
    }
