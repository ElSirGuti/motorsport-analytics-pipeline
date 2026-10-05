"""
Session-level corner analysis.

Compares each flying lap against the reference (fastest) lap and aggregates
per-corner time losses, braking / apex / throttle deltas across the whole session.
The output shape mirrors the 2-lap `corners` array so CornerAnalysisPanel can
be reused unchanged in the frontend.
"""
import logging
from collections import defaultdict

import numpy as np
from src.i18n import _ as t

logger = logging.getLogger(__name__)


# Plausibility limits for per-lap deltas vs the reference lap. Beyond these the pairing is
# almost certainly wrong (braking zone of another corner / previous straight), so the
# value is "not measurable" and is excluded rather than displayed.
MAX_PLAUSIBLE_BRAKE_DELTA_M = 150.0
MAX_PLAUSIBLE_APEX_DELTA_KMH = 40.0
MAX_PLAUSIBLE_THROTTLE_DELTA_M = 250.0


def _plausible(values: list, limit: float) -> list:
    return [v for v in values if v is not None and np.isfinite(v) and abs(v) <= limit]


def _describe_corner(num: int, loss: float, brake,
                     apex, throttle, std: float,
                     lang: str = "es", name: str | None = None) -> str:
    """brake/apex/throttle may be None when not measurable: they are then omitted.
    `name` (e.g. "Tamburello") is used when the circuit is known."""
    return describe_with_name(num, _corner_parts(brake, apex, throttle, std, lang), name, lang)


def describe_with_name(num: int, parts: str, name: str | None, lang: str = "es") -> str:
    if name:
        return t("sess_curve_format_named", lang=lang, num=num, name=name, parts=parts)
    return t("sess_curve_format", lang=lang, num=num, parts=parts)


def _corner_parts(brake, apex, throttle, std: float, lang: str = "es") -> str:
    parts = []
    if brake is not None and brake > 8:
        parts.append(t("sess_brake_late", lang=lang, brake=f"{brake:.0f}"))
    elif brake is not None and brake < -8:
        parts.append(t("sess_brake_early", lang=lang, brake=f"{brake:.0f}"))
    if apex is not None and apex < -4:
        parts.append(t("sess_apex_slow", lang=lang, apex=f"{apex:.1f}"))
    elif apex is not None and apex > 4:
        parts.append(t("sess_apex_fast", lang=lang, apex=f"{apex:.1f}"))
    if throttle is not None and throttle > 8:
        parts.append(t("sess_throttle_late", lang=lang, throttle=f"{throttle:.0f}"))
    if std > 0.08:
        parts.append(t("sess_inconsistent", lang=lang, std=f"{std:.3f}"))
    if not parts:
        parts.append(t("sess_similar", lang=lang))
    return ", ".join(parts)


def _observations_from_map(dfs: list, df_laps, corner_map: dict) -> dict:
    """
    Per-lap observations measured inside the windows of the unified corner map (no detection, no
    ``pair_corners``). Same shape as the legacy observations, keyed by the map's corner NUMBER, plus
    ``kind``; a delta that cannot be measured is None (always so for flat_out / kink corners, which keep
    their time loss). See src/analytics/corner_metrics.py.
    """
    from src.analytics import corner_metrics as cm
    from src.analytics.corner_map import _prepare_lap

    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]
    if len(flying) < 2:
        return {}
    corners = corner_map["corners"]
    L = float(corner_map["summary"]["lap_length_m"])
    ref_idx = int(flying["lap_time_s"].idxmin())

    def _metrics(i):
        lap = _prepare_lap(dfs[i], [], i)
        if lap is None or abs(lap["length"] / L - 1.0) > 0.04:
            return None      # partial lap / other layout: its corners are not at the map's fractions
        return cm.lap_metrics(lap, corners, L)

    ref = _metrics(ref_idx)
    if ref is None:
        return {}
    obs: dict = defaultdict(list)
    for idx in flying.index:
        if idx == ref_idx:
            continue
        try:
            cur = _metrics(idx)
            if cur is None:
                continue
            for c, mr, ml in zip(corners, ref, cur):
                d = cm.delta_vs_reference(mr, ml)
                d.update({"ref_apex_distance": float(c["apex_distance_m"]), "kind": c.get("kind")})
                obs[c["number"]].append(d)
        except Exception as exc:
            logger.debug("get_corner_observations(map): idx=%d: %s", idx, exc)
    return dict(obs)


def get_corner_observations(dfs: list, df_laps, corner_map: dict | None = None) -> dict:
    """
    Extract per-lap, per-corner raw observations without aggregating.
    Returns {corner_idx: [{time_loss, brake_delta, apex_delta, thtl_delta}]}
    Exposed so the RL module can reuse alignments already computed here.

    With ``corner_map`` (unified corner map, CORNER_DETECTION=map) the corners are the map's and the
    metrics are measured in its windows; without it the previous detectors are used (legacy).
    """
    if corner_map and corner_map.get("corners"):
        return _observations_from_map(dfs, df_laps, corner_map)
    from src.processing.alignment import align_pair, align_by_distance
    from src.telemetry.lap_comparator import _estimate_corner_time_loss
    from src.telemetry.metrics import segment_corners, pair_corners

    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]
    if len(flying) < 2:
        return {}

    ref_idx = int(flying["lap_time_s"].idxmin())
    # Corner detection / time-loss only read these four channels. Interpolating the other
    # ~165 columns of every lap onto the 1 m grid was ~80 % of this function's time.
    _cols = ("Distance", "Speed", "Brake", "Throttle")

    def _slim(d):
        return d[[c for c in _cols if c in d.columns]]

    ref_df  = _slim(dfs[ref_idx])
    obs: dict = defaultdict(list)

    # The reference lap is the same in every pair: interpolate it once, not N-1 times.
    try:
        ref_aligned = align_by_distance(ref_df)
    except Exception:
        ref_aligned = None

    for idx in flying.index:
        if idx == ref_idx:
            continue
        try:
            al_a, al_b = align_pair(ref_df, _slim(dfs[idx]), pre_a=ref_aligned)
            corners_a  = segment_corners(al_a)
            corners_b  = segment_corners(al_b)
            for i, ca, cb in pair_corners(corners_a, corners_b):
                tl = _estimate_corner_time_loss(al_a, al_b, ca, cb)
                obs[i + 1].append({
                    "time_loss":    float(tl),
                    "brake_delta":  float(cb["braking_point"]["distance"] - ca["braking_point"]["distance"]),
                    "apex_delta":   float(cb["apex"]["speed"] - ca["apex"]["speed"]),
                    "thtl_delta":   float(cb["full_throttle"]["distance"] - ca["full_throttle"]["distance"]),
                    # apex position on the reference lap (m): lets callers name the corner
                    "ref_apex_distance": float(ca["apex"]["distance"]),
                })
        except Exception as exc:
            logger.debug("get_corner_observations: idx=%d: %s", idx, exc)

    return dict(obs)


def _map_fields(mc: dict, loss: float, std: float, lang: str, base: dict) -> dict:
    """Fields the unified corner map adds to a session corner (additive: nothing is renamed or removed)."""
    from src.analytics.corner_metrics import is_flat
    extra = {
        "number": mc["number"], "name": mc.get("name"), "corner_name": mc.get("name"),
        "kind": mc.get("kind"), "direction": mc.get("direction"),
        "min_radius_m": mc.get("min_radius_m"), "flat_out_share": mc.get("flat_out_share"),
        "confidence": mc.get("confidence"), "is_complex": bool(mc.get("is_complex")),
        "start_m": mc.get("start_m"), "end_m": mc.get("end_m"),
        "apex_distance": round(float(mc["apex_distance_m"]), 1),
    }
    parts = base["description_parts"]
    if is_flat(mc):
        # nothing to optimise in braking / apex / throttle: only the time lost inside the window is real
        extra.update({"braking_available": False, "apex_available": False, "throttle_available": False,
                      "braking_delta_meters": 0.0, "apex_speed_delta_kmh": 0.0, "throttle_delta_meters": 0.0})
        parts = t("sess_flat_out", lang=lang, loss=f"{loss:+.3f}")
        if std > 0.08:
            parts += ", " + t("sess_inconsistent", lang=lang, std=f"{std:.3f}")
        extra["description_parts"] = parts
    extra["description"] = describe_with_name(mc["number"], parts, mc.get("name"), lang)
    return extra


def analizar_curvas_sesion(
    dfs: list, df_laps, lang: str = "es",
    precomputed_obs: dict | None = None,
    corner_map: dict | None = None,
) -> dict:
    """
    Compare each non-pit flying lap against the fastest (reference) lap.

    Args:
        dfs:              Per-lap DataFrames.
        df_laps:          Lap metrics DataFrame.
        lang:             Language code for description strings.
        precomputed_obs:  If provided (from get_corner_observations), skip re-aligning.
        corner_map:       Unified corner map. With it every corner carries the map's number, name,
                          kind, direction, radius and confidence, and flat_out / kink corners report
                          their time loss but no braking / apex / throttle (``*_available`` False).
    """
    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]

    if len(flying) < 2:
        logger.info("session_corner_analysis: <2 vueltas volantes — omitido")
        return {"available": False, "reason": t("unavail_few_flying_laps_2")}

    ref_idx = int(flying["lap_time_s"].idxmin())
    ref_lap_num = (
        int(df_laps.loc[ref_idx, "lap_number"])
        if "lap_number" in df_laps.columns
        else ref_idx + 1
    )
    ref_time_str = (
        df_laps.loc[ref_idx, "lap_time_str"]
        if "lap_time_str" in df_laps.columns
        else "?"
    )
    logger.info(
        "session_corner_analysis: referencia=vuelta_%d (%s), comparando %d vueltas",
        ref_lap_num, ref_time_str, len(flying) - 1,
    )

    # ── Use pre-computed or compute fresh (single implementation: get_corner_observations)
    if precomputed_obs is None:
        precomputed_obs = get_corner_observations(dfs, df_laps, corner_map=corner_map)
    map_by_num = {c["number"]: c for c in (corner_map or {}).get("corners", [])}
    corner_data: dict = defaultdict(list)
    for cnum, laps in precomputed_obs.items():
        for lap in laps:
            corner_data[cnum].append({
                "time_loss":      lap["time_loss"],
                "brake_delta":    lap["brake_delta"],
                "apex_delta":     lap["apex_delta"],
                "throttle_delta": lap["thtl_delta"],
                "ref_apex_distance": lap.get("ref_apex_distance"),
            })

    if not corner_data:
        logger.info("session_corner_analysis: sin datos de curvas — omitido")
        return {"available": False,
                "reason": "no corners could be matched between laps (need Brake/Speed/Throttle channels with braking zones)"}

    # ── Aggregate ─────────────────────────────────────────────────────────────
    corners_agg = []
    for corner_num in sorted(corner_data.keys()):
        laps = corner_data[corner_num]
        losses    = [d["time_loss"]      for d in laps]
        brakes    = [d["brake_delta"]    for d in laps]
        apexes    = [d["apex_delta"]     for d in laps]
        throttles = [d["throttle_delta"] for d in laps]

        mean_loss     = float(np.mean(losses))
        std_loss      = float(np.std(losses))
        ok_b = _plausible(brakes,    MAX_PLAUSIBLE_BRAKE_DELTA_M)
        ok_a = _plausible(apexes,    MAX_PLAUSIBLE_APEX_DELTA_KMH)
        ok_t = _plausible(throttles, MAX_PLAUSIBLE_THROTTLE_DELTA_M)
        # Measurable only if the majority of laps gave a plausible value.
        mean_brake    = float(np.mean(ok_b)) if ok_b and len(ok_b) * 2 >= len(brakes)    else None
        mean_apex     = float(np.mean(ok_a)) if ok_a and len(ok_a) * 2 >= len(apexes)    else None
        mean_throttle = float(np.mean(ok_t)) if ok_t and len(ok_t) * 2 >= len(throttles) else None

        _apex_ds = [d["ref_apex_distance"] for d in laps if d.get("ref_apex_distance") is not None]
        corners_agg.append({
            "corner_number":          corner_num,
            # apex position on the reference lap (m); None if unknown. corner_name is
            # filled in by src.analytics.circuits when the circuit is recognised.
            "apex_distance":          round(float(np.median(_apex_ds)), 1) if _apex_ds else None,
            "corner_name":            None,
            "time_loss_seconds":      round(mean_loss, 3),
            "std_loss_seconds":       round(std_loss, 3),
            # Not-measurable deltas are reported as 0.0 (keeps numeric consumers safe)
            # with the matching *_available flag set to False.
            "braking_delta_meters":   round(mean_brake, 1) if mean_brake is not None else 0.0,
            "apex_speed_delta_kmh":   round(mean_apex, 1) if mean_apex is not None else 0.0,
            "throttle_delta_meters":  round(mean_throttle, 1) if mean_throttle is not None else 0.0,
            "braking_available":      mean_brake is not None,
            "apex_available":         mean_apex is not None,
            "throttle_available":     mean_throttle is not None,
            "n_laps":                 len(laps),
            "consistency":            t("consistency_inconsistent", lang=lang) if std_loss > 0.08 else t("consistency_consistent", lang=lang),
            "description": _describe_corner(
                corner_num, mean_loss, mean_brake, mean_apex, mean_throttle, std_loss, lang=lang
            ),
            # text without the "Corner N" prefix, so the circuit module can re-title it
            "description_parts": _corner_parts(mean_brake, mean_apex, mean_throttle, std_loss, lang),
        })
        mc = map_by_num.get(corner_num)
        if mc is not None:
            corners_agg[-1].update(_map_fields(mc, mean_loss, std_loss, lang, corners_agg[-1]))

    total_loss = sum(max(0.0, c["time_loss_seconds"]) for c in corners_agg)

    logger.info(
        "session_corner_analysis: %d curvas, pérdida_acumulada=%.3fs, vueltas_comparadas=%d",
        len(corners_agg), total_loss, len(flying) - 1,
    )
    return {
        "available":       True,
        "corners":         corners_agg,
        "total_loss":      round(total_loss, 3),
        "reference_lap":   ref_lap_num,
        "n_laps_compared": len(flying) - 1,
    }
