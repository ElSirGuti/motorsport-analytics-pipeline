"""
Setup changes inside a session: the same logbook analysed in laps ranges, one per setup.

The user changed the setup at some lap (the garage was used mid-session): ``splits`` are the 1-based laps
where a new setup STARTS. Each range gets its own pace statistics and its own Setup Advisor run (corners,
telemetry, degradation of THAT range only), so the recommendations are not an average of two cars.
The comparison between consecutive ranges is informative only: fuel burn, track evolution and tyre wear
also move the pace between two parts of a session.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_LAPS_PER_SEGMENT = 3      # fewer valid laps than this: pace only, no advisor run


class SegmentError(ValueError):
    """Invalid split laps (``code`` is the i18n suffix ``seg_err_<code>``)."""

    def __init__(self, code: str, **kw):
        super().__init__(code)
        self.code, self.kw = code, kw


def parse_splits(raw, n_laps: int) -> List[int]:
    """'12, 25' / '[12, 25]' / [12, 25] -> sorted unique laps in 2..n_laps. Raises SegmentError."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        txt = raw.strip().strip("[]")
        items = [p for p in txt.replace(";", ",").split(",") if p.strip()]
    else:
        items = list(raw)
    try:
        laps = sorted({int(float(str(x).strip())) for x in items})
    except ValueError:
        raise SegmentError("not_numeric")
    for lap in laps:
        if lap < 2 or lap > n_laps:
            raise SegmentError("out_of_range", lap=lap, n=n_laps)
    if len(laps) > 8:
        raise SegmentError("too_many")
    return laps


def ranges(splits: List[int], n_laps: int) -> List[tuple]:
    """[(from_lap, to_lap)] 1-based inclusive."""
    starts = [1] + list(splits)
    ends = [s - 1 for s in splits] + [n_laps]
    return list(zip(starts, ends))


def _pace(df_laps: pd.DataFrame) -> dict:
    """Pace of the racing laps of a range (pit laps and laps with an incident left out)."""
    d = df_laps
    mask = d["lap_time_s"].notna()
    if "is_pit_lap" in d.columns:
        mask &= ~d["is_pit_lap"].fillna(False).astype(bool)
    clean = mask.copy()
    if "is_incident_lap" in d.columns:
        clean &= ~d["is_incident_lap"].fillna(False).astype(bool)
    times = d.loc[clean, "lap_time_s"].astype(float)
    if times.empty:
        times = d.loc[mask, "lap_time_s"].astype(float)
    if times.empty:
        return {"n_laps": int(len(d)), "n_valid": 0}
    # a lap far slower than the rest (mistake, traffic, out-lap) is not pace: median is robust, mean is not
    return {"n_laps": int(len(d)), "n_valid": int(len(times)), "best_s": round(float(times.min()), 3),
            "median_s": round(float(times.median()), 3), "mean_s": round(float(times.mean()), 3),
            "std_s": round(float(times.std(ddof=1)), 3) if len(times) > 1 else None,
            "n_incident_laps": int(d["is_incident_lap"].fillna(False).astype(bool).sum())
            if "is_incident_lap" in d.columns else 0}


def analyze_segments(dfs: list, df_laps: pd.DataFrame, splits: List[int], lang: str = "en",
                     cmap: Optional[dict] = None) -> dict:
    """Pace + Setup Advisor per range. ``dfs`` / ``df_laps`` are the session's per-lap frames and metrics."""
    from src.analytics.session_corner_analysis import analizar_curvas_sesion, get_corner_observations
    from src.analytics.session_telemetry_analysis import analizar_telemetria_sesion
    from src.analytics.setup_advisor import analizar_setup_sesion
    from src.analytics.stint import analizar_degradacion_stint
    from src.analytics.tyre_degradation import detect_wear_tracking

    out = []
    prev = None
    for k, (a, b) in enumerate(ranges(splits, len(dfs))):
        sub_dfs = dfs[a - 1:b]
        sub_laps = df_laps.iloc[a - 1:b].reset_index(drop=True)
        pace = _pace(sub_laps)
        seg = {"index": k, "from_lap": a, "to_lap": b, "n_laps": b - a + 1, "pace": pace,
               "setup_advisor": {"available": False}, "advisor_reason": None}
        if pace.get("n_valid", 0) >= MIN_LAPS_PER_SEGMENT:
            try:
                obs = get_corner_observations(sub_dfs, sub_laps, corner_map=cmap)
                curvas = analizar_curvas_sesion(sub_dfs, sub_laps, lang=lang, precomputed_obs=obs, corner_map=cmap)
                tele = analizar_telemetria_sesion(sub_dfs, sub_laps)
                try:
                    deg = analizar_degradacion_stint(sub_laps)
                except Exception:       # a short range cannot fit a trend: the advisor works without it
                    deg = {"available": False}
                if curvas.get("available") or tele.get("available"):
                    seg["setup_advisor"] = analizar_setup_sesion(
                        curvas, deg, tele, lang=lang, wear_active=detect_wear_tracking(sub_dfs)["active"])
                else:
                    seg["advisor_reason"] = "no_data"
            except Exception as exc:    # one broken range must not hide the others
                logger.warning("setup segment %d-%d: %s", a, b, exc)
                seg["advisor_reason"] = "error"
        else:
            seg["advisor_reason"] = "few_laps"
        if prev is not None and prev["pace"].get("median_s") is not None and pace.get("median_s") is not None:
            seg["vs_previous"] = {
                "median_delta_s": round(pace["median_s"] - prev["pace"]["median_s"], 3),
                "best_delta_s": round(pace["best_s"] - prev["pace"]["best_s"], 3),
                "std_delta_s": (round(pace["std_s"] - prev["pace"]["std_s"], 3)
                                if pace.get("std_s") is not None and prev["pace"].get("std_s") is not None else None),
            }
        prev = seg
        out.append(seg)
    return {"segments": out, "splits": splits, "n_laps": len(dfs)}
