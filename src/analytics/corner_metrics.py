"""
Per-lap metrics of every corner of the unified corner map, measured INSIDE the map windows.

Before the unified map each module detected its own corners (segmenter + ``pair_corners`` in session
mode, geometry apexes in compare mode) and measured braking point / apex / throttle on whatever it
found. With the map the corners are given (``start_m`` .. ``end_m``, ``apex_distance_m``, ``kind``) and
here only the measurements are taken, so every module reports the same corners with the same
numbering. See docs/CORNER_DETECTION.md, section "Integration".

Conventions (all distances in the reference scale of the map, i.e. metres of the median lap length):

* ``time_s``      time spent inside the corner window (trapezoid of 1 / v); the loss of a lap is the
                  difference against the reference lap, positive = slower. Windows are disjoint (the
                  map cuts them at the midpoint to the neighbours), so the losses of all corners never
                  add up to more than the lap delta.
* ``brake``       start of the main braking zone before the apex (None without a braking zone or when
                  braking began before the search range: censored).
* ``vmin``        minimum speed inside the window (km/h).
* ``full_throttle`` first point after the apex with full throttle.
* corners with kind ``flat_out`` / ``kink`` have no braking point, apex or throttle application to
  measure: only ``time_s`` is returned (the other values are None).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

FLAT_KINDS = ("flat_out", "kink")
BRAKE_THR_PCT = 3.0            # same threshold as metrics.detect_braking_points
FULL_THROTTLE_PCT = 98.0       # same threshold as metrics.detect_full_throttle_points
BRAKE_LOOKBACK_M = 300.0       # braking zone search range before the apex (as metrics.BRAKE_MAX_WINDOW_M)
THROTTLE_LOOKAHEAD_M = 300.0   # full-throttle search range after the apex
V_MIN_MS = 1.0                 # speed floor (m/s) so a stopped car does not blow up 1/v


def is_flat(corner: dict) -> bool:
    """True for corners without braking point / apex / throttle application (kind flat_out or kink)."""
    return corner.get("kind") in FLAT_KINDS


def first_onset(values: np.ndarray, idx: np.ndarray, thr: float) -> Optional[int]:
    """Start of the main braking zone: walk back from the peak sample while the pedal stays above ``thr``.

    ``idx`` are the positions (indices into ``values``) of the search range. Returns the index into
    ``values`` or None when there is no braking or it began before the range (censored)."""
    if len(idx) < 2:
        return None
    vals = values[idx]
    j = int(np.argmax(vals))
    if vals[j] <= thr:
        return None
    while j > 0 and vals[j - 1] > thr:
        j -= 1
    if j == 0 and vals[0] > thr:
        return None
    return int(idx[j])


def neighbours(corners: list) -> list:
    """[(prev_apex_m or None, next_apex_m or None)] for every corner of the (ordered) map."""
    ap = [float(c["apex_distance_m"]) for c in corners]
    return [(ap[i - 1] if i else None, ap[i + 1] if i + 1 < len(ap) else None) for i in range(len(ap))]


def _xs(x0: float, x1: float) -> np.ndarray:
    return np.arange(np.floor(x0), np.floor(x1) + 1.0)


def window_time(speed_kmh: np.ndarray, xs: np.ndarray) -> float:
    """Seconds spent over the positions ``xs`` (1 m apart) at the speeds ``speed_kmh``."""
    if len(xs) < 2:
        return 0.0
    inv = 1.0 / np.maximum(speed_kmh / 3.6, V_MIN_MS)
    return float(np.sum((inv[:-1] + inv[1:]) * 0.5 * np.diff(xs)))


def lap_corner_metrics(lap: dict, corner: dict, L: float, prev_apex: Optional[float],
                       next_apex: Optional[float]) -> dict:
    """
    Measurements of ONE lap in ONE corner.

    ``lap`` is a prepared lap (``corner_map._prepare_lap``: 1 m grid ``grid`` with ``speed``, ``brake``,
    ``throttle`` and ``length``). Positions of the map are scaled to the lap with ``length / L``.
    """
    k = lap["length"] / L
    grid = lap["grid"]
    xs = _xs(corner["start_m"], corner["end_m"])
    v = np.interp(xs * k, grid, lap["speed"])
    out = {"time_s": window_time(v, xs), "vmin": None, "brake": None, "full_throttle": None}
    if is_flat(corner):
        return out
    out["vmin"] = float(v.min()) if len(v) else None
    apex = float(corner["apex_distance_m"])
    if lap.get("brake") is not None:
        lo = max(prev_apex if prev_apex is not None else 0.0, apex - BRAKE_LOOKBACK_M)
        xb = _xs(lo, apex)
        if len(xb) >= 2:
            b = np.interp(xb * k, grid, lap["brake"])
            i = first_onset(b, np.arange(len(b)), BRAKE_THR_PCT)
            out["brake"] = float(xb[i]) if i is not None else None
    if lap.get("throttle") is not None:
        hi = min(apex + THROTTLE_LOOKAHEAD_M, next_apex if next_apex is not None else L, L)
        xt = _xs(apex, hi)
        if len(xt) >= 2:
            th = np.interp(xt * k, grid, lap["throttle"])
            hit = np.nonzero(th >= FULL_THROTTLE_PCT)[0]
            out["full_throttle"] = float(xt[hit[0]]) if len(hit) else None
    return out


def lap_metrics(lap: dict, corners: list, L: float) -> list:
    """``lap_corner_metrics`` for every corner of the map (same order)."""
    nb = neighbours(corners)
    return [lap_corner_metrics(lap, c, L, p, n) for c, (p, n) in zip(corners, nb)]


def delta_vs_reference(ref: dict, lap: dict) -> dict:
    """Deltas of a lap against the reference lap in one corner (conventions of the session analysis):

    time_loss    seconds, positive = the lap is slower than the reference;
    brake_delta  metres, positive = the lap brakes LATER (further along) than the reference;
    apex_delta   km/h, positive = the lap is faster at the apex;
    thtl_delta   metres, positive = the lap reaches full throttle LATER.
    A delta that cannot be measured in either lap is None."""
    def diff(a, b):
        return None if a is None or b is None else float(a - b)
    return {
        "time_loss": float(lap["time_s"] - ref["time_s"]),
        "brake_delta": diff(lap["brake"], ref["brake"]),
        "apex_delta": diff(lap["vmin"], ref["vmin"]),
        "thtl_delta": diff(lap["full_throttle"], ref["full_throttle"]),
    }
