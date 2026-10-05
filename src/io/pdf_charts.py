"""
Matplotlib charts for the PDF report.

Sober, print-oriented style: white background, graphite axes, one blue accent
(matching the app's "pit wall" identity but darkened for contrast on paper),
semantic red/green only for loss/gain. Every chart returns PNG bytes plus its pixel
size (see ``Chart``) or ``None`` when the needed data is absent — the layout code
decides what to omit, so a missing channel never produces an empty frame.

All user-visible strings go through ``src.i18n._`` (keys ``pdf_*``), and decimal
separators follow the active language (comma in Spanish).
"""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter, ScalarFormatter  # noqa: E402

from src.i18n import _ as t, get_language  # noqa: E402

logger = logging.getLogger(__name__)

# ── Palette (print-safe versions of the app's tokens) ────────────────────────
ACCENT = "#1F6FD1"      # blue accent (lap A / primary series)
SERIES_B = "#D9822B"    # amber (lap B / secondary series), colour-blind safe against blue
BAD = "#C2414B"         # loss
OK = "#1F8F5F"          # gain
WARN = "#C98A12"
INK = "#1B2430"         # graphite text / axes
INK_2 = "#4A5563"
INK_3 = "#7B8696"
GRID = "#E3E7EC"
BAND = "#EEF2F7"

DPI = 200

_STATUS_KEYS = {"fria": "pdf_tyre_fria", "suboptima": "pdf_tyre_suboptima", "optima": "pdf_tyre_optima",
                "caliente": "pdf_tyre_caliente", "sobrecalentada": "pdf_tyre_sobrecalentada"}


@dataclass
class Chart:
    png: bytes
    width_px: int
    height_px: int


# ── Number formatting helpers (shared with the layout module) ────────────────

def decimal_comma() -> bool:
    return get_language() == "es"


def num_str(v: float, decimals: int = 1, signed: bool = False) -> str:
    """Locale-aware number string; '' is never returned (callers check finiteness)."""
    s = f"{v:+.{decimals}f}" if signed else f"{v:.{decimals}f}"
    if s.replace("+", "").replace("-", "").strip("0.") == "" and s.startswith("-"):
        s = s[1:]  # avoid "-0.0"
    return s.replace(".", ",") if decimal_comma() else s


class _LocaleFormatter(ScalarFormatter):
    def __init__(self, comma: bool):
        super().__init__(useOffset=False, useMathText=False)
        self._comma = comma

    def __call__(self, x, pos=None):
        s = super().__call__(x, pos)
        return s.replace(".", ",") if self._comma else s


def _style_ax(ax, xlabel: str = "", ylabel: str = "", grid_axis: str = "both") -> None:
    ax.set_facecolor("white")
    ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#9AA5B4")
        ax.spines[spine].set_linewidth(0.7)
    ax.tick_params(labelsize=7, colors=INK_2, length=3, width=0.6)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7.5, color=INK_2)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7.5, color=INK_2)
    comma = decimal_comma()
    ax.xaxis.set_major_formatter(_LocaleFormatter(comma))
    ax.yaxis.set_major_formatter(_LocaleFormatter(comma))


def _legend(ax, **kw):
    kw.setdefault("fontsize", 7)
    kw.setdefault("frameon", True)
    kw.setdefault("framealpha", 0.95)
    kw.setdefault("edgecolor", GRID)
    leg = ax.legend(**kw)
    if leg:
        for txt in leg.get_texts():
            txt.set_color(INK)
    return leg


def _new_fig(w_cm: float, h_cm: float, nrows: int = 1, ncols: int = 1, **kw):
    fig, axes = plt.subplots(nrows, ncols, figsize=(w_cm / 2.54, h_cm / 2.54),
                             layout="constrained", **kw)
    fig.patch.set_facecolor("white")
    return fig, axes


def _finish(fig) -> Chart:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor="white", edgecolor="none")
    w_in, h_in = fig.get_size_inches()
    plt.close(fig)
    return Chart(buf.getvalue(), int(round(w_in * DPI)), int(round(h_in * DPI)))


def _safe(fn):
    """Charts must never break the whole report."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("%s failed: %s", fn.__name__, exc, exc_info=False)
            plt.close("all")
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


def _arr(seq) -> np.ndarray:
    return np.asarray([np.nan if v is None else v for v in (seq or [])], dtype=float)


def _has(seq, n: int = 2) -> bool:
    a = _arr(seq)
    return a.size >= n and np.isfinite(a).sum() >= n


def fmt_laptime(seconds: float, decimals: int = 3) -> str:
    """m:ss.mmm (decimal comma in Spanish)."""
    if seconds is None or not math.isfinite(seconds):
        return "—"
    m = int(seconds // 60)
    s = seconds - 60 * m
    width = 2 if decimals == 0 else 3 + decimals
    txt = f"{m}:{s:0{width}.{decimals}f}"
    return txt.replace(".", ",") if decimal_comma() else txt


# ── Session charts ────────────────────────────────────────────────────────────

@_safe
def chart_lap_times(laps: Sequence[dict], trend: Optional[dict] = None,
                    montecarlo: Optional[dict] = None,
                    w: float = 17.4, h: float = 6.4) -> Optional[Chart]:
    """
    laps: dicts with n (lap number), time (s), kind in {'clean','best','pit','outlier'}.
    trend: degradacion dict (trend_laps/trend_times/projected_*/low_confidence).
    montecarlo: p10/p90 band over future_laps.
    """
    pts = [p for p in laps if p.get("time") and math.isfinite(p["time"])]
    clean = [p for p in pts if p["kind"] in ("clean", "best")]
    if len(clean) < 2:
        return None
    ct = np.array([p["time"] for p in clean])
    span = max(float(ct.max() - ct.min()), 1.0)
    lo = float(ct.min()) - 0.12 * span - 0.2
    hi = float(ct.max()) + 0.22 * span + 0.2

    fig, ax = _new_fig(w, h)
    # reference line at best lap
    best = min(clean, key=lambda p: p["time"])
    ax.axhline(best["time"], color=INK_3, lw=0.7, ls=":", zorder=1)

    ax.plot([p["n"] for p in clean], ct, color=ACCENT, lw=1.1, zorder=3,
            marker="o", ms=3.4, mfc=ACCENT, mec="white", mew=0.5, label=t("pdf_chart_clean_laps"))

    # trend and projection
    low_conf = bool(trend and trend.get("low_confidence"))
    if trend and _has(trend.get("trend_laps")) and _has(trend.get("trend_times")):
        ax.plot(trend["trend_laps"], trend["trend_times"], color=INK, lw=1.0, ls="--", zorder=2,
                label=t("pdf_chart_trend"))
    proj_col = INK_3 if low_conf else "#3F8BE6"
    if montecarlo and montecarlo.get("available") and _has(montecarlo.get("future_laps")):
        fl = _arr(montecarlo["future_laps"])
        p10, p90 = _arr(montecarlo.get("p10")), _arr(montecarlo.get("p90"))
        if p10.size == fl.size and p90.size == fl.size:
            ax.fill_between(fl, p10, p90, color=proj_col, alpha=0.14, lw=0, zorder=1,
                            label=t("pdf_chart_band_low") if low_conf else t("pdf_chart_band"))
        p50 = _arr(montecarlo.get("p50"))
        if p50.size == fl.size:
            ax.plot(fl, p50, color=proj_col, lw=1.1, ls="--", zorder=2,
                    label=t("pdf_chart_projection_low") if low_conf else t("pdf_chart_projection"))
            if p90.size and np.isfinite(p90).any():
                hi = max(hi, min(float(np.nanmax(p90)) + 0.06 * span, hi + 0.6 * span))
    # best lap highlight
    ax.scatter([best["n"]], [best["time"]], s=46, color=OK, zorder=5, edgecolor="white",
               linewidths=0.8, label=t("pdf_chart_best_lap", time=fmt_laptime(best["time"])))

    # pit / outlier laps (hollow grey; clamped to the top edge when off-scale)
    off = [p for p in pts if p["kind"] in ("pit", "outlier")]
    if off:
        xs, ys, clipped = [], [], []
        for p in off:
            xs.append(p["n"])
            ys.append(min(max(p["time"], lo + 0.04 * (hi - lo)), hi))
            clipped.append(p["time"] > hi or p["time"] < lo)
        ys = [y - (0.025 * (hi - lo) if (c and y >= hi) else 0) for y, c in zip(ys, clipped)]
        ax.scatter(xs, ys, s=22, facecolors="white", edgecolors=INK_3, linewidths=0.9, zorder=4,
                   label=t("pdf_chart_excluded_laps"), clip_on=False)
        for x, y, c, p in zip(xs, ys, clipped, off):
            if c:
                ax.annotate(fmt_laptime(p["time"], 0), (x, y),
                            xytext=(0, -9), textcoords="offset points", ha="center",
                            fontsize=5.5, color=INK_3, annotation_clip=False)
    ax.set_ylim(lo, hi)
    all_n = [p["n"] for p in pts]
    if montecarlo and montecarlo.get("available") and _has(montecarlo.get("future_laps")):
        all_n += list(map(float, montecarlo["future_laps"]))
    ax.set_xlim(min(all_n) - 0.6, max(all_n) + 0.6)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=14))
    _style_ax(ax, xlabel=t("pdf_chart_lap_number"), ylabel=t("pdf_chart_lap_time"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: fmt_laptime(v, 1)))
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, fontsize=7, frameon=False)
    return _finish(fig)


@_safe
def chart_corner_bars(corners: Sequence[dict], ylabel: str,
                      w: float = 17.4, h: float = 5.6) -> Optional[Chart]:
    """corners: dicts with n, loss (s), sigma (optional), flat (optional: flat-out corner of the unified
    corner map, drawn hatched). Drawn strictly in corner order."""
    rows = [c for c in corners if c.get("loss") is not None and math.isfinite(c["loss"])]
    if not rows:
        return None
    rows = sorted(rows, key=lambda c: c["n"])
    fig, ax = _new_fig(w, h)
    x = np.arange(len(rows))
    vals = np.array([c["loss"] for c in rows])
    cols = [BAD if v > 0.02 else OK if v < -0.02 else INK_3 for v in vals]
    bars = ax.bar(x, vals, color=cols, width=0.62, zorder=3, edgecolor="white", linewidth=0.5)
    flat = [bool(c.get("flat")) for c in rows]
    for b, is_flat in zip(bars, flat):
        if is_flat:
            b.set_hatch("////")
    sig = np.array([c.get("sigma") if c.get("sigma") is not None else np.nan for c in rows], dtype=float)
    if np.isfinite(sig).any():
        ax.errorbar(x, vals, yerr=np.where(np.isfinite(sig), sig, 0), fmt="none",
                    ecolor=INK_2, elinewidth=0.8, capsize=2.2, capthick=0.8, zorder=4)
    ax.axhline(0, color=INK_2, lw=0.8, zorder=2)
    span = float(np.nanmax(np.abs(vals))) or 0.1
    off = 0.03 * span + 0.004
    for xi, v, s in zip(x, vals, sig):
        top = abs(s) if np.isfinite(s) else 0
        if v >= 0:
            ax.text(xi, v + top + off, num_str(v, 3, True), ha="center", va="bottom",
                    fontsize=6.3, color=INK)
        else:
            ax.text(xi, v - top - off, num_str(v, 3, True), ha="center", va="top",
                    fontsize=6.3, color=INK)
    ax.set_xticks(x)
    ax.margins(y=0.2)
    _style_ax(ax, xlabel=t("pdf_chart_corner_number"), ylabel=ylabel, grid_axis="y")
    ax.set_xticklabels([str(c["n"]) for c in rows])
    handles = [mpatches.Patch(color=BAD, label=t("pdf_chart_loss")),
               mpatches.Patch(color=OK, label=t("pdf_chart_gain"))]
    if np.isfinite(sig).any():
        handles.append(plt.Line2D([0], [0], color=INK_2, lw=0.9, marker="_", ms=5,
                                  label=t("pdf_chart_sigma")))
    if any(flat):
        handles.append(mpatches.Patch(facecolor="white", edgecolor=INK_2, hatch="////", label=t("pdf_kind_flat_out")))
    fig.legend(handles=handles, loc="outside lower center", ncol=len(handles), fontsize=7, frameon=False)
    return _finish(fig)


# ── Lap-comparison charts ────────────────────────────────────────────────────

@_safe
def chart_speed(sc: dict, la: str, lb: str, w: float = 17.4, h: float = 6.0) -> Optional[Chart]:
    dist, sa, sb = sc.get("distance"), sc.get("speed_a"), sc.get("speed_b")
    if not _has(dist) or not _has(sa):
        return None
    fig, ax = _new_fig(w, h)
    ax.plot(dist, sa, color=ACCENT, lw=1.1, label=la)
    if _has(sb):
        ax.plot(dist, sb, color=SERIES_B, lw=1.1, ls="--", label=lb)
    _style_ax(ax, t("pdf_chart_distance"), t("pdf_chart_speed"))
    ax.margins(x=0.005)
    _legend(ax, loc="lower right", ncol=2)
    return _finish(fig)


@_safe
def chart_delta(td: dict, lb: str, w: float = 17.4, h: float = 4.4) -> Optional[Chart]:
    dist, delta = td.get("distance"), td.get("delta")
    if not _has(dist) or not _has(delta):
        return None
    d = _arr(delta)
    x = _arr(dist)
    fig, ax = _new_fig(w, h)
    ax.plot(x, d, color=INK, lw=0.9)
    ax.fill_between(x, d, 0, where=d > 0, alpha=0.22, color=BAD, lw=0, label=t("pdf_chart_b_loses", lap=lb))
    ax.fill_between(x, d, 0, where=d < 0, alpha=0.22, color=OK, lw=0, label=t("pdf_chart_b_gains", lap=lb))
    ax.axhline(0, color=INK_3, lw=0.7, ls="--")
    _style_ax(ax, t("pdf_chart_distance"), t("pdf_chart_cum_delta"))
    ax.margins(x=0.005)
    _legend(ax, loc="upper left", ncol=2)
    return _finish(fig)


@_safe
def chart_brake_throttle(bc: dict, tc: dict, la: str, lb: str,
                         w: float = 17.4, h: float = 8.6) -> Optional[Chart]:
    d_b = bc.get("distance") or []
    d_t = tc.get("distance") or d_b
    b_a, b_b = bc.get("brake_a"), bc.get("brake_b")
    t_a, t_b = tc.get("throttle_a"), tc.get("throttle_b")
    if not (_has(b_a) or _has(t_a)):
        return None
    fig, (ax1, ax2) = _new_fig(w, h, 2, 1, sharex=True)
    if _has(b_a):
        ax1.plot(d_b, b_a, color=ACCENT, lw=1.0, label=la)
        if _has(b_b):
            ax1.plot(d_b, b_b, color=SERIES_B, lw=1.0, ls="--", label=lb)
    _style_ax(ax1, "", t("pdf_chart_brake"))
    ax1.set_ylim(-3, 103)
    _legend(ax1, loc="upper right", ncol=2)
    if _has(t_a):
        ax2.plot(d_t, t_a, color=ACCENT, lw=1.0, label=la)
        if _has(t_b):
            ax2.plot(d_t, t_b, color=SERIES_B, lw=1.0, ls="--", label=lb)
    _style_ax(ax2, t("pdf_chart_distance"), t("pdf_chart_throttle"))
    ax2.set_ylim(-3, 103)
    ax2.margins(x=0.005)
    return _finish(fig)


def _gg_points(gg) -> tuple[list, list]:
    """Accepts {'fast': [...], 'slow': [...]} (current API) or a flat labelled list (legacy)."""
    a, b = [], []
    if isinstance(gg, dict):
        a = [(p["lat"], p["lon"]) for p in gg.get("fast", []) if "lat" in p and "lon" in p]
        b = [(p["lat"], p["lon"]) for p in gg.get("slow", []) if "lat" in p and "lon" in p]
    elif isinstance(gg, list):
        for p in gg:
            if "lat" not in p or "lon" not in p:
                continue
            lbl = str(p.get("label", "")).lower()
            (b if "slow" in lbl else a).append((p["lat"], p["lon"]))
    return a, b


@_safe
def chart_gg(gg, la: str, lb: str, w: float = 9.0, h: float = 8.6) -> Optional[Chart]:
    a, b = _gg_points(gg)
    if not a and not b:
        return None
    fig, ax = _new_fig(w, h)
    if b:
        xb, yb = zip(*b)
        ax.scatter(xb, yb, s=2.2, c=SERIES_B, alpha=0.35, linewidths=0, label=lb, rasterized=True)
    if a:
        xa, ya = zip(*a)
        ax.scatter(xa, ya, s=2.2, c=ACCENT, alpha=0.4, linewidths=0, label=la, rasterized=True)
    ax.axhline(0, color="#B8C0CC", lw=0.6)
    ax.axvline(0, color="#B8C0CC", lw=0.6)
    _style_ax(ax, t("pdf_chart_g_lat"), t("pdf_chart_g_lon"))
    ax.set_aspect("equal", adjustable="datalim")
    _legend(ax, loc="lower right", markerscale=4)
    return _finish(fig)


@_safe
def chart_tyre_bars(tyre: dict, la: str, lb: str, w: float = 17.4, h: float = 5.0) -> Optional[Chart]:
    positions = ["FL", "FR", "RL", "RR"]
    pos_labels = {"FL": t("pdf_pos_fl"), "FR": t("pdf_pos_fr"), "RL": t("pdf_pos_rl"), "RR": t("pdf_pos_rr")}
    status_col = {"fria": "#6F9BE0", "suboptima": "#8DBFD6", "optima": OK,
                  "caliente": "#E0A030", "sobrecalentada": BAD}
    order = ["fria", "suboptima", "optima", "caliente", "sobrecalentada"]
    ca = {c["corner"]: c for c in (tyre.get("lap_a") or {}).get("corners", [])}
    cb = {c["corner"]: c for c in (tyre.get("lap_b") or {}).get("corners", [])}
    pos = [p for p in positions if p in ca or p in cb]
    if not pos:
        return None
    fig, (ax1, ax2) = _new_fig(w, h, 1, 2, sharex=True)
    top = 0.0
    for ax, cm, label in ((ax1, ca, la), (ax2, cb, lb)):
        temps = [(cm.get(p) or {}).get("surface_mean") or 0 for p in pos]
        cols = [status_col.get((cm.get(p) or {}).get("window_status", ""), "#B8C0CC") for p in pos]
        y = list(range(len(pos)))
        ax.barh(y, temps, color=cols, edgecolor="white", height=0.55, zorder=3)
        ax.set_title(label, fontsize=8, color=INK, pad=3, loc="left")
        _style_ax(ax, t("pdf_chart_temp"), "", grid_axis="x")
        ax.set_yticks(y)
        ax.set_yticklabels([pos_labels[p] for p in pos], fontsize=7)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        for i, v in enumerate(temps):
            if v > 0:
                ax.text(v + 0.8, i, f"{num_str(v, 0)}°", va="center", fontsize=6.5, color=INK)
                top = max(top, v)
    for ax in (ax1, ax2):
        ax.set_xlim(0, top * 1.12 if top else 100)
    patches = [mpatches.Patch(color=status_col[s], label=t(_STATUS_KEYS[s])) for s in order]
    fig.legend(handles=patches, fontsize=6.5, loc="outside lower center", ncol=5, frameon=False)
    return _finish(fig)


@_safe
def chart_brake_fade(brake: dict, la: str, lb: str, w: float = 17.4, h: float = 5.6) -> Optional[Chart]:
    pdist = brake.get("per_distance") or {}
    dist, ea, eb = pdist.get("distance"), pdist.get("efficiency_a"), pdist.get("efficiency_b")
    if not _has(dist) or not _has(ea):
        return None
    fig, ax = _new_fig(w, h)
    ax.plot(dist, ea, color=ACCENT, lw=1.0, label=la)
    if _has(eb):
        ax.plot(dist, eb, color=SERIES_B, lw=1.0, ls="--", label=lb)
    for z in brake.get("fade_zones_a", []) or []:
        ax.axvspan(z.get("start", 0), z.get("end", 0), alpha=0.14, color=ACCENT, lw=0)
    for z in brake.get("fade_zones_b", []) or []:
        ax.axvspan(z.get("start", 0), z.get("end", 0), alpha=0.14, color=SERIES_B, lw=0)
    _style_ax(ax, t("pdf_chart_distance"), t("pdf_chart_brake_eff"))
    ax.margins(x=0.005)
    _legend(ax, loc="upper right", ncol=2)
    return _finish(fig)


@_safe
def chart_nervousness(inputs: dict, la: str, lb: str, w: float = 17.4, h: float = 5.2) -> Optional[Chart]:
    pdist = inputs.get("per_distance") or {}
    dist, na, nb = pdist.get("distance"), pdist.get("nervousness_a"), pdist.get("nervousness_b")
    if not _has(dist) or not _has(na):
        return None
    fig, ax = _new_fig(w, h)
    ax.plot(dist, na, color=ACCENT, lw=0.9, label=la, alpha=0.9)
    if _has(nb):
        ax.plot(dist, nb, color=SERIES_B, lw=0.9, ls="--", label=lb, alpha=0.9)
    ax.axhline(0.5, color=INK_3, lw=0.7, ls=":", label=t("pdf_chart_mid_threshold"))
    _style_ax(ax, t("pdf_chart_distance"), t("pdf_chart_nervousness"))
    ax.set_ylim(-0.02, 1.05)
    ax.margins(x=0.005)
    _legend(ax, loc="upper right", ncol=3)
    return _finish(fig)


@_safe
def chart_suspension(susp: dict, la: str, lb: str, w: float = 17.4, h: float = 8.6) -> Optional[Chart]:
    pa, pb = susp.get("per_distance_a") or {}, susp.get("per_distance_b") or {}
    da, db = pa.get("distance"), pb.get("distance")
    if not _has(da) and not _has(db):
        return None
    fig, (ax1, ax2) = _new_fig(w, h, 2, 1)
    if _has(da) and _has(pa.get("roll_f")):
        ax1.plot(da, pa["roll_f"], color=ACCENT, lw=1.0, label=f"{la} – {t('pdf_chart_front')}")
        if _has(pa.get("roll_r")):
            ax1.plot(da, pa["roll_r"], color=ACCENT, lw=0.8, ls=":", label=f"{la} – {t('pdf_chart_rear')}")
    if _has(db) and _has(pb.get("roll_f")):
        ax1.plot(db, pb["roll_f"], color=SERIES_B, lw=1.0, ls="--", label=f"{lb} – {t('pdf_chart_front')}")
        if _has(pb.get("roll_r")):
            ax1.plot(db, pb["roll_r"], color=SERIES_B, lw=0.8, ls="-.", label=f"{lb} – {t('pdf_chart_rear')}")
    _style_ax(ax1, "", t("pdf_chart_roll"))
    _legend(ax1, loc="upper right", ncol=2, fontsize=6.5)
    if _has(da) and _has(pa.get("pitch")):
        ax2.plot(da, pa["pitch"], color=ACCENT, lw=1.0, label=la)
    if _has(db) and _has(pb.get("pitch")):
        ax2.plot(db, pb["pitch"], color=SERIES_B, lw=1.0, ls="--", label=lb)
    _style_ax(ax2, t("pdf_chart_distance"), t("pdf_chart_pitch"))
    _legend(ax2, loc="upper right", ncol=2)
    return _finish(fig)


@_safe
def chart_slip(slip: dict, la: str, lb: str, w: float = 17.4, h: float = 8.6) -> Optional[Chart]:
    pa, pb = slip.get("per_distance_a") or {}, slip.get("per_distance_b") or {}
    da, db = pa.get("distance"), pb.get("distance")
    if not _has(da) and not _has(db):
        return None
    fig, (ax1, ax2) = _new_fig(w, h, 2, 1)
    if _has(da) and _has(pa.get("beta")):
        ax1.plot(da, pa["beta"], color=ACCENT, lw=0.9, label=la)
    if _has(db) and _has(pb.get("beta")):
        ax1.plot(db, pb["beta"], color=SERIES_B, lw=0.9, ls="--", label=lb)
    ax1.axhline(0, color=INK_3, lw=0.6)
    _style_ax(ax1, "", t("pdf_chart_beta"))
    _legend(ax1, loc="upper right", ncol=2)
    if _has(pa.get("balance")) or _has(pb.get("balance")):
        if _has(da) and _has(pa.get("balance")):
            ax2.plot(da, pa["balance"], color=ACCENT, lw=0.9, label=la)
        if _has(db) and _has(pb.get("balance")):
            ax2.plot(db, pb["balance"], color=SERIES_B, lw=0.9, ls="--", label=lb)
        ax2.axhline(0, color=INK_3, lw=0.6)
        ax2.axhline(2, color=WARN, lw=0.8, ls=":", label=t("pdf_chart_us_threshold"))
        ax2.axhline(-2, color=BAD, lw=0.8, ls=":", label=t("pdf_chart_os_threshold"))
        _style_ax(ax2, t("pdf_chart_distance"), t("pdf_chart_balance"))
        _legend(ax2, loc="upper right", ncol=4, fontsize=6.5)
    else:
        if _has(da) and _has(pa.get("alpha_f")):
            ax2.plot(da, pa["alpha_f"], color=ACCENT, lw=0.9, label=f"αF {la}")
            if _has(pa.get("alpha_r")):
                ax2.plot(da, pa["alpha_r"], color=ACCENT, lw=0.8, ls=":", label=f"αR {la}")
        ax2.axhline(0, color=INK_3, lw=0.6)
        _style_ax(ax2, t("pdf_chart_distance"), t("pdf_chart_tyre_slip"))
        _legend(ax2, loc="upper right", ncol=2, fontsize=6.5)
    return _finish(fig)
