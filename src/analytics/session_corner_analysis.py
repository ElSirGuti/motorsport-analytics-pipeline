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


def _describe_corner(num: int, loss: float, brake: float,
                     apex: float, throttle: float, std: float,
                     lang: str = "es") -> str:
    parts = []
    if brake > 8:
        parts.append(t("sess_brake_late", lang=lang, brake=f"{brake:.0f}"))
    elif brake < -8:
        parts.append(t("sess_brake_early", lang=lang, brake=f"{brake:.0f}"))
    if apex < -4:
        parts.append(t("sess_apex_slow", lang=lang, apex=f"{apex:.1f}"))
    elif apex > 4:
        parts.append(t("sess_apex_fast", lang=lang, apex=f"{apex:.1f}"))
    if throttle > 8:
        parts.append(t("sess_throttle_late", lang=lang, throttle=f"{throttle:.0f}"))
    if std > 0.08:
        parts.append(t("sess_inconsistent", lang=lang, std=f"{std:.3f}"))
    if not parts:
        parts.append(t("sess_similar", lang=lang))
    return t("sess_curve_format", lang=lang, num=num, parts=", ".join(parts))


def get_corner_observations(dfs: list, df_laps) -> dict:
    """
    Extract per-lap, per-corner raw observations without aggregating.
    Returns {corner_idx: [{time_loss, brake_delta, apex_delta, thtl_delta}]}
    Exposed so the RL module can reuse alignments already computed here.
    """
    from src.processing.alignment import align_pair
    from src.telemetry.lap_comparator import _estimate_corner_time_loss
    from src.telemetry.metrics import segment_corners

    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]
    if len(flying) < 2:
        return {}

    ref_idx = int(flying["lap_time_s"].idxmin())
    ref_df  = dfs[ref_idx]
    obs: dict = defaultdict(list)

    for idx in flying.index:
        if idx == ref_idx:
            continue
        try:
            al_a, al_b = align_pair(ref_df, dfs[idx])
            corners_a  = segment_corners(al_a)
            corners_b  = segment_corners(al_b)
            n = min(len(corners_a), len(corners_b))
            for i in range(n):
                ca, cb = corners_a[i], corners_b[i]
                tl = _estimate_corner_time_loss(al_a, al_b, ca, cb)
                obs[i + 1].append({
                    "time_loss":    float(tl),
                    "brake_delta":  float(cb["braking_point"]["distance"] - ca["braking_point"]["distance"]),
                    "apex_delta":   float(cb["apex"]["speed"] - ca["apex"]["speed"]),
                    "thtl_delta":   float(cb["full_throttle"]["distance"] - ca["full_throttle"]["distance"]),
                })
        except Exception as exc:
            logger.debug("get_corner_observations: idx=%d: %s", idx, exc)

    return dict(obs)


def analizar_curvas_sesion(
    dfs: list, df_laps, lang: str = "es",
    precomputed_obs: dict | None = None,
) -> dict:
    """
    Compare each non-pit flying lap against the fastest (reference) lap.

    Args:
        dfs:              Per-lap DataFrames.
        df_laps:          Lap metrics DataFrame.
        lang:             Language code for description strings.
        precomputed_obs:  If provided (from get_corner_observations), skip re-aligning.
    """
    flying_mask = ~df_laps["is_pit_lap"] & df_laps["lap_time_s"].notna()
    flying = df_laps[flying_mask]

    if len(flying) < 2:
        logger.info("session_corner_analysis: <2 vueltas volantes — omitido")
        return {"available": False}

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

    # ── Use pre-computed or compute fresh ────────────────────────────────────
    if precomputed_obs:
        # Translate from {corner_idx: [{time_loss, brake_delta, apex_delta, thtl_delta}]}
        # to the internal format expected below
        corner_data: dict = defaultdict(list)
        for cnum, laps in precomputed_obs.items():
            for lap in laps:
                corner_data[cnum].append({
                    "time_loss":      lap["time_loss"],
                    "brake_delta":    lap["brake_delta"],
                    "apex_delta":     lap["apex_delta"],
                    "throttle_delta": lap["thtl_delta"],
                })
    else:
        from src.processing.alignment import align_pair
        from src.telemetry.lap_comparator import _estimate_corner_time_loss
        from src.telemetry.metrics import segment_corners

        ref_df = dfs[ref_idx]
        corner_data = defaultdict(list)

        for idx in flying.index:
            if idx == ref_idx:
                continue
            try:
                aligned_a, aligned_b = align_pair(ref_df, dfs[idx])
                corners_a = segment_corners(aligned_a)
                corners_b = segment_corners(aligned_b)
                n = min(len(corners_a), len(corners_b))
                for i in range(n):
                    ca, cb = corners_a[i], corners_b[i]
                    tl = _estimate_corner_time_loss(aligned_a, aligned_b, ca, cb)
                    corner_data[i + 1].append({
                        "time_loss":      float(tl),
                        "brake_delta":    float(cb["braking_point"]["distance"] - ca["braking_point"]["distance"]),
                        "apex_delta":     float(cb["apex"]["speed"] - ca["apex"]["speed"]),
                        "throttle_delta": float(cb["full_throttle"]["distance"] - ca["full_throttle"]["distance"]),
                    })
            except Exception as exc:
                logger.debug("session_corner_analysis: idx=%d falló: %s", idx, exc)

    if not corner_data:
        logger.info("session_corner_analysis: sin datos de curvas — omitido")
        return {"available": False}

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
        mean_brake    = float(np.mean(brakes))
        mean_apex     = float(np.mean(apexes))
        mean_throttle = float(np.mean(throttles))

        corners_agg.append({
            "corner_number":          corner_num,
            "time_loss_seconds":      round(mean_loss, 3),
            "std_loss_seconds":       round(std_loss, 3),
            "braking_delta_meters":   round(mean_brake, 1),
            "apex_speed_delta_kmh":   round(mean_apex, 1),
            "throttle_delta_meters":  round(mean_throttle, 1),
            "n_laps":                 len(laps),
            "consistency":            t("consistency_inconsistent", lang=lang) if std_loss > 0.08 else t("consistency_consistent", lang=lang),
            "description": _describe_corner(
                corner_num, mean_loss, mean_brake, mean_apex, mean_throttle, std_loss, lang=lang
            ),
        })

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
