"""
Glue between the unified corner map (``corner_map.build_corner_map``) and the analysis endpoints.

* ``mode()`` / ``use_map()``: the CORNER_DETECTION switch. ``map`` (default) = every module takes its
  corners from the unified map; ``legacy`` = the previous detectors, untouched (to compare and to roll back).
* ``session_corner_map`` / ``pair_corner_map``: build the map ONCE per session (or per pair of laps) and
  reuse it between endpoints through ``session_cache.corner_map_cache`` (key: purpose + file SHA-256 /
  ``file_id`` + venue + lap length + options).
* ``public_map``: the additive ``corner_map`` object of the API responses.
* ``scale_to_lap`` / ``apexes_frame``: adapt the map to the frames the compare pipeline works with.

Every function returns None (or leaves the caller on the old path) when the switch is ``legacy``, when the
map cannot be built or when it has no corners: a failed map never breaks an analysis.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from src.analytics import circuits as C
from src.analytics.corner_map import DEFAULTS, build_corner_map
from src.io import session_cache as sc

logger = logging.getLogger(__name__)

ENV_VAR = "CORNER_DETECTION"
MODES = ("map", "legacy")
MAX_MAP_LAPS = 30           # the fastest N flying laps feed the map (bounds the cost of a 60-lap race)
LENGTH_TOL = 0.04           # laps whose length differs more than this from the usual length are partial / other layout
PUBLIC_PARAMS = ("min_share", "relaxed_share", "cluster_tol_min_m", "cluster_tol_frac", "match_pad_m",
                 "unbacked_min_support", "group_gap_m", "group_max_span_m", "prior_laps", "min_confidence")


def mode() -> str:
    """'map' (default) or 'legacy', read at call time from CORNER_DETECTION."""
    v = (os.getenv(ENV_VAR) or "map").strip().lower()
    return v if v in MODES else "map"


def use_map() -> bool:
    return mode() == "map"


def file_key(*paths: str) -> str:
    """SHA-256 over the content of one or more files (cache key when no ``file_id`` is available)."""
    digests = []
    for p in paths:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        digests.append(h.hexdigest())
    # one file: its plain SHA-256 (== the ``file_id`` of POST /api/files); several: a hash of the hashes
    return digests[0] if len(digests) == 1 else hashlib.sha256(":".join(digests).encode()).hexdigest()


def pair_key_sha(sha_a: str, sha_b: str) -> str:
    """Cache key of a pair of laps from their SHA-256 (same key in every two-file endpoint)."""
    return f"{sha_a}:{sha_b}"


def pair_key(path_a: str, path_b: str) -> str:
    return pair_key_sha(file_key(path_a), file_key(path_b))


def _options_digest(options: Optional[dict]) -> str:
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return hashlib.sha1(json.dumps(merged, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _lap_len(df) -> Optional[float]:
    return C.lap_length_of(df)


# ── Which laps feed the map ─────────────────────────────────────────────────────────
def select_map_laps(dfs: list, df_laps: Optional[pd.DataFrame] = None) -> list:
    """
    Clean flying laps of a session: no pit / out / outlier laps (``is_pit_lap``), with a lap time, a length
    within 4 % of the most common lap length (the longer one on a tie), at most the ``MAX_MAP_LAPS`` fastest. The selection depends only on the
    laps, so analyze-session, stint, optimal-lap and compare-session-laps pick the same ones.
    """
    if df_laps is None:
        from src.analytics.stint import extraer_metricas_por_vuelta
        df_laps = extraer_metricas_por_vuelta(dfs)
    rows = []
    for i, d in enumerate(dfs):
        if i >= len(df_laps):
            break
        r = df_laps.iloc[i]
        t = r.get("lap_time_s")
        if bool(r.get("is_pit_lap", False)) or t is None or not np.isfinite(t):
            continue
        rows.append((float(t), i))
    if not rows:                       # nothing flying: use every lap with a usable length
        rows = [(float(i), i) for i in range(len(dfs))]
    lens = {i: _lap_len(dfs[i]) for _, i in rows}
    # Reference length: the most populated length cluster (ties: the longer one, a partial lap is always
    # shorter than a full one). A median would fail on short stints (out lap + 2 full laps + a partial lap:
    # no lap within 4 % of it) and "the fastest lap" would pick a short partial segment.
    ref = None
    best = (0, 0.0)
    for _t0, i0 in sorted(rows):
        if not lens[i0]:
            continue
        n_in = sum(1 for _, j in rows if lens[j] and abs(lens[j] - lens[i0]) / lens[i0] <= LENGTH_TOL)
        if (n_in, lens[i0]) > best:
            best, ref = (n_in, lens[i0]), lens[i0]
    keep = [(t, i) for t, i in rows
            if ref is None or (lens[i] and abs(lens[i] - ref) / ref <= LENGTH_TOL)]
    keep = sorted(keep)[:MAX_MAP_LAPS]
    return [dfs[i] for _, i in sorted(keep, key=lambda p: p[1])]


# ── Build + cache ───────────────────────────────────────────────────────────────────
def _usable(cmap: Optional[dict]) -> Optional[dict]:
    return cmap if cmap and cmap.get("corners") else None


def _cached(kind: str, key: Optional[str], venue, laps: list, options: Optional[dict]) -> Optional[dict]:
    if not laps:
        return None
    lengths = [x for x in (_lap_len(d) for d in laps) if x]
    L = C.median_lap_length(lengths)

    def build():
        return build_corner_map(laps, venue, L, options)

    try:
        if not key:
            return _usable(build())
        k = (kind, key, C.normalize_venue(venue), round(L or 0.0), _options_digest(options))
        return _usable(sc.corner_map_cache.get_or_build(k, build))
    except Exception as exc:  # noqa: BLE001 - the map is an improvement, never a reason to fail
        logger.warning("corner map (%s): %s", kind, exc, exc_info=True)
        return None


def session_corner_map(dfs: list, venue, key: Optional[str], df_laps: Optional[pd.DataFrame] = None,
                       options: Optional[dict] = None) -> Optional[dict]:
    """Corner map of a whole session (all its clean flying laps). None in legacy mode / on failure."""
    if not use_map():
        return None
    return _cached("session", key, venue, select_map_laps(dfs, df_laps), options)


def pair_corner_map(df_a: pd.DataFrame, df_b: pd.DataFrame, venue, key: Optional[str],
                    options: Optional[dict] = None) -> Optional[dict]:
    """Corner map of the two compared laps (relaxed consensus, template when the circuit is recognised)."""
    if not use_map():
        return None
    return _cached("pair", key, venue, [df_a, df_b], options)


# ── API object ───────────────────────────────────────────────────────────────────────
def public_map(cmap: Optional[dict]) -> Optional[dict]:
    """The additive ``corner_map`` object of the responses (no heavy series: ~10 small dicts)."""
    if not cmap:
        return None
    s = cmap["summary"]
    return {
        "mode": "map",
        "circuit": s.get("circuit"),
        "method": s.get("method"),
        "params": {k: s["params"].get(k) for k in PUBLIC_PARAMS if k in s.get("params", {})},
        "n_laps": s.get("n_laps"),
        "lap_length_m": s.get("lap_length_m"),
        "n_corners": s.get("n_corners"),
        "n_named": s.get("n_named"),
        "n_discarded": s.get("n_discarded"),
        "warnings": list(s.get("warnings") or []),
        "corners": copy.deepcopy(cmap["corners"]),
    }


def attach(result: dict, cmap: Optional[dict]) -> dict:
    """Add ``result['corner_map']`` when there is a map (no key in legacy mode)."""
    pm = public_map(cmap)
    if pm is not None:
        result["corner_map"] = pm
    return result


# ── Adapting the map to frames ───────────────────────────────────────────────────────
def scale_to_lap(cmap: dict, lap_length_m: Optional[float]) -> dict:
    """Copy of the map with ``start_m`` / ``end_m`` / ``apex_distance_m`` scaled from the map's reference
    length to the length of the lap whose frame will be analysed (positions are lap fractions)."""
    L = (cmap.get("summary") or {}).get("lap_length_m")
    if not lap_length_m or not L or abs(lap_length_m / L - 1.0) < 1e-9:
        return cmap
    f = float(lap_length_m) / float(L)
    out = dict(cmap)
    corners = []
    for c in cmap["corners"]:
        c2 = dict(c)
        for k in ("start_m", "end_m", "apex_distance_m"):
            c2[k] = round(float(c[k]) * f, 1)
        corners.append(c2)
    out["corners"] = corners
    return out


def apexes_frame(cmap: dict, df_geo: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    The ``apexes`` table of the compare responses, built from the map: one row per corner, same columns as
    ``geometry.detectar_apexes_perfectos`` (Distance, Curvature, Speed, Throttle, Brake, Elevation) plus the
    map fields (corner_number, corner_name, kind, direction, min_radius_m, start_m, end_m, confidence,
    flat_out_share, is_complex). Speed / pedals / elevation / curvature come from the lap geometry frame.
    """
    rows = []
    geo_ok = isinstance(df_geo, pd.DataFrame) and "Distance" in df_geo.columns and len(df_geo) > 2
    gd = df_geo["Distance"].to_numpy(dtype=float) if geo_ok else None
    for c in cmap["corners"]:
        d = float(c["apex_distance_m"])
        row = {"Distance": d}
        kappa = None
        if geo_ok:
            if "Curvature" in df_geo.columns:
                m = (gd >= d - 25.0) & (gd <= d + 25.0)
                if m.any():
                    kappa = float(df_geo["Curvature"].to_numpy(dtype=float)[m].max())
            for col in ("Speed", "Throttle", "Brake", "Elevation"):
                if col in df_geo.columns:
                    row[col] = float(np.interp(d, gd, df_geo[col].to_numpy(dtype=float)))
        if not kappa:
            r = c.get("min_radius_m")
            kappa = 1.0 / r if r else 0.02
        row["Curvature"] = float(kappa)
        if "Speed" not in row and (c.get("evidence") or {}).get("speed_min_kmh") is not None:
            row["Speed"] = float(c["evidence"]["speed_min_kmh"])
        row.update({
            "corner_number": int(c["number"]), "corner_name": c.get("name"), "kind": c.get("kind"),
            "direction": c.get("direction"), "min_radius_m": c.get("min_radius_m"),
            "start_m": c.get("start_m"), "end_m": c.get("end_m"), "confidence": c.get("confidence"),
            "flat_out_share": c.get("flat_out_share"), "is_complex": bool(c.get("is_complex")),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def has_map(result: dict) -> bool:
    cm = result.get("corner_map") if isinstance(result, dict) else None
    return isinstance(cm, dict) and bool(cm.get("corners"))
