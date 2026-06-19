"""
PDF report generator for lap comparison results.

Embeds matplotlib charts (speed, delta, brake/throttle, GG diagram, tyre temps,
brake fade, driver nervousness, suspension roll/pitch, body sideslip β) plus
reportlab table sections. Chart sections are skipped gracefully when data is absent.
"""

import io
import logging
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from src.i18n import _ as t

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

# ── Layout ────────────────────────────────────────────────────────────────────
_PAGE_W_CM    = 17.0
_CHART_H      = 6.5
_CHART_H_TALL = 8.5
_CHART_H_2SUB = 9.5
_GG_W_CM      = 9.0
_GG_H_CM      = 9.0

# ── Chart colours (print-friendly) ───────────────────────────────────────────
_COL_A = "#0077BB"   # Lap A — blue
_COL_B = "#CC2200"   # Lap B — red

# ── reportlab palette ─────────────────────────────────────────────────────────
_ACCENT = colors.HexColor("#00D4FF")
_DARK   = colors.HexColor("#0A0E1A")
_MID    = colors.HexColor("#1A1F35")
_WHITE  = colors.white
_RED    = colors.HexColor("#CC2200")
_GREEN  = colors.HexColor("#006622")


# ── Styles & table style ──────────────────────────────────────────────────────

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("rp_title", parent=base["Title"],
            fontSize=22, leading=26, textColor=_DARK, spaceAfter=4, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("rp_subtitle", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#555577"), spaceAfter=12, alignment=TA_CENTER),
        "h2": ParagraphStyle("rp_h2", parent=base["Heading2"],
            fontSize=11, leading=14, textColor=_ACCENT, spaceBefore=14, spaceAfter=4),
        "body": ParagraphStyle("rp_body", parent=base["Normal"],
            fontSize=9, leading=13, textColor=_DARK),
        "explain": ParagraphStyle("rp_explain", parent=base["Normal"],
            fontSize=8, leading=12, textColor=colors.HexColor("#444455"),
            spaceBefore=4, spaceAfter=6, leftIndent=8, rightIndent=8),
        "warn": ParagraphStyle("rp_warn", parent=base["Normal"],
            fontSize=9, leading=12, textColor=colors.HexColor("#CC4400")),
        "caption": ParagraphStyle("rp_caption", parent=base["Normal"],
            fontSize=7, leading=10, textColor=colors.HexColor("#888899")),
    }


def _tbl_style(header_bg=_MID) -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  _ACCENT),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#F7F9FC"), _WHITE]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCDD")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])


# ── Matplotlib helpers ────────────────────────────────────────────────────────

def _style_ax(ax, xlabel: str = "Distancia (m)", ylabel: str = "") -> None:
    ax.set_facecolor("white")
    ax.grid(True, color="#EEEEEE", linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(labelsize=7, colors="#333333")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8, color="#444444")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8, color="#444444")


def _to_image(fig, w_cm: float, h_cm: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=w_cm * cm, height=h_cm * cm)


# ── Chart functions ───────────────────────────────────────────────────────────

def _chart_speed(result: dict, la: str, lb: str,
                 w: float = _PAGE_W_CM, h: float = _CHART_H) -> Optional[Image]:
    sc   = result.get("speed_comparison") or {}
    dist = sc.get("distance", [])
    sa   = sc.get("speed_a",  [])
    sb   = sc.get("speed_b",  [])
    if not dist or not sa:
        return None
    try:
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        ax.plot(dist, sa, color=_COL_A, lw=1.2, label=la)
        ax.plot(dist, sb, color=_COL_B, lw=1.2, label=lb, linestyle="--")
        _style_ax(ax, ylabel="Velocidad (km/h)")
        ax.legend(fontsize=8, framealpha=0.9)
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_speed: %s", e)
        plt.close("all")
        return None


def _chart_delta(result: dict, la: str, lb: str,
                 w: float = _PAGE_W_CM, h: float = 4.5) -> Optional[Image]:
    td    = result.get("time_delta_series") or {}
    dist  = td.get("distance", [])
    delta = td.get("delta", [])
    if not dist or not delta:
        return None
    try:
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        d = np.array(delta, dtype=float)
        ax.plot(dist, d, color="#222244", lw=1.0)
        ax.fill_between(dist, d, 0, where=(d > 0), alpha=0.25, color=_COL_B,
                        label=f"{lb} pierde tiempo")
        ax.fill_between(dist, d, 0, where=(d < 0), alpha=0.25, color=_COL_A,
                        label=f"{lb} gana tiempo")
        ax.axhline(0, color="#AAAAAA", lw=0.7, linestyle="--")
        _style_ax(ax, ylabel="Δ Tiempo acumulado (s)")
        ax.legend(fontsize=7, framealpha=0.9)
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_delta: %s", e)
        plt.close("all")
        return None


def _chart_brake_throttle(result: dict, la: str, lb: str,
                           w: float = _PAGE_W_CM, h: float = _CHART_H_2SUB) -> Optional[Image]:
    bc  = result.get("brake_comparison")    or {}
    tc  = result.get("throttle_comparison") or {}
    d_b = bc.get("distance", [])
    d_t = tc.get("distance", []) or d_b
    b_a = bc.get("brake_a",    [])
    b_b = bc.get("brake_b",    [])
    t_a = tc.get("throttle_a", [])
    t_b = tc.get("throttle_b", [])
    if not d_b and not d_t:
        return None
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(w / 2.54, h / 2.54), sharex=True)
        fig.patch.set_facecolor("white")
        if d_b and b_a:
            ax1.plot(d_b, b_a, color=_COL_A, lw=1.0, label=la)
            if b_b:
                ax1.plot(d_b, b_b, color=_COL_B, lw=1.0, linestyle="--", label=lb)
        _style_ax(ax1, xlabel="", ylabel="Freno (%)")
        ax1.set_ylim(-3, 103)
        ax1.legend(fontsize=7, framealpha=0.9)
        if d_t and t_a:
            ax2.plot(d_t, t_a, color=_COL_A, lw=1.0, label=la)
            if t_b:
                ax2.plot(d_t, t_b, color=_COL_B, lw=1.0, linestyle="--", label=lb)
        _style_ax(ax2, ylabel="Acelerador (%)")
        ax2.set_ylim(-3, 103)
        ax2.legend(fontsize=7, framealpha=0.9)
        fig.tight_layout(pad=0.5, h_pad=0.3)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_brake_throttle: %s", e)
        plt.close("all")
        return None


def _chart_gg(result: dict, la: str, lb: str,
              w: float = _GG_W_CM, h: float = _GG_H_CM) -> Optional[Image]:
    gg = result.get("gg_diagram") or []
    if not gg:
        return None
    try:
        pts_a, pts_b = [], []
        for pt in gg:
            lbl = str(pt.get("label", ""))
            if "fast" in lbl.lower() or lbl == la:
                pts_a.append((pt["lat"], pt["lon"]))
            elif "slow" in lbl.lower() or lbl == lb:
                pts_b.append((pt["lat"], pt["lon"]))
            else:
                pts_a.append((pt["lat"], pt["lon"]))
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        if pts_a:
            xa, ya = zip(*pts_a)
            ax.scatter(xa, ya, c=_COL_A, s=1.5, alpha=0.4, linewidths=0, label=la)
        if pts_b:
            xb, yb = zip(*pts_b)
            ax.scatter(xb, yb, c=_COL_B, s=1.5, alpha=0.4, linewidths=0, label=lb)
        ax.axhline(0, color="#CCCCCC", lw=0.6)
        ax.axvline(0, color="#CCCCCC", lw=0.6)
        _style_ax(ax, xlabel="G Lateral", ylabel="G Longitudinal")
        ax.set_aspect("equal", adjustable="datalim")
        ax.legend(fontsize=7, markerscale=5, framealpha=0.9)
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_gg: %s", e)
        plt.close("all")
        return None


def _chart_tyre_bars(result: dict, la: str, lb: str,
                     w: float = _PAGE_W_CM, h: float = 5.0) -> Optional[Image]:
    tyre = result.get("tyre_analysis") or {}
    if not tyre.get("available"):
        return None
    POSITIONS  = ["FL", "FR", "RL", "RR"]
    POS_LABELS = {"FL": "Del. Izq.", "FR": "Del. Der.", "RL": "Tra. Izq.", "RR": "Tra. Der."}
    STATUS_COL = {
        "fria": "#6699FF", "suboptima": "#44CCEE",
        "optima": "#33BB55", "caliente": "#FFAA00", "sobrecalentada": "#FF3333",
    }
    corners_a = {c["corner"]: c for c in tyre.get("lap_a", {}).get("corners", [])}
    corners_b = {c["corner"]: c for c in tyre.get("lap_b", {}).get("corners", [])}
    all_pos = [p for p in POSITIONS if p in corners_a or p in corners_b]
    if not all_pos:
        return None
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        for ax, cmap, label in [(ax1, corners_a, la), (ax2, corners_b, lb)]:
            temps    = [cmap.get(p, {}).get("surface_mean") or 0 for p in all_pos]
            col_list = [STATUS_COL.get(cmap.get(p, {}).get("window_status", ""), "#BBBBBB")
                        for p in all_pos]
            pos_lbl  = [POS_LABELS.get(p, p) for p in all_pos]
            y = list(range(len(all_pos)))
            ax.barh(y, temps, color=col_list, edgecolor="white", height=0.55)
            ax.set_yticks(y)
            ax.set_yticklabels(pos_lbl, fontsize=7)
            ax.set_title(label, fontsize=8, color="#333333", pad=4)
            _style_ax(ax, xlabel="Temperatura (°C)", ylabel="")
            ax.tick_params(axis="y", length=0)
            for i, t in enumerate(temps):
                if t > 0:
                    ax.text(t + 0.5, i, f"{t:.0f}°", va="center", fontsize=6, color="#333333")
        STATUS_ORDER = ["fria", "suboptima", "optima", "caliente", "sobrecalentada"]
        patches = [mpatches.Patch(color=STATUS_COL[s], label=s.capitalize())
                   for s in STATUS_ORDER]
        fig.legend(handles=patches, fontsize=6, loc="lower center", ncol=5,
                   bbox_to_anchor=(0.5, -0.04), framealpha=0.9)
        fig.tight_layout(pad=0.5, rect=[0, 0.08, 1, 1])
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_tyre_bars: %s", e)
        plt.close("all")
        return None


def _chart_brake_fade(result: dict, la: str, lb: str,
                      w: float = _PAGE_W_CM, h: float = _CHART_H) -> Optional[Image]:
    brake   = result.get("brake_analysis") or {}
    if not brake.get("available"):
        return None
    pd_data = brake.get("per_distance") or {}
    dist    = pd_data.get("distance",     [])
    eff_a   = pd_data.get("efficiency_a", [])
    eff_b   = pd_data.get("efficiency_b", [])
    if not dist or not eff_a:
        return None
    try:
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        ax.plot(dist, eff_a, color=_COL_A, lw=1.2, label=la)
        if eff_b:
            ax.plot(dist, eff_b, color=_COL_B, lw=1.2, linestyle="--", label=lb)
        for zone in brake.get("fade_zones_a", []):
            ax.axvspan(zone.get("start", 0), zone.get("end", 0), alpha=0.12, color=_COL_A)
        for zone in brake.get("fade_zones_b", []):
            ax.axvspan(zone.get("start", 0), zone.get("end", 0), alpha=0.12, color=_COL_B)
        _style_ax(ax, ylabel="Eficiencia frenos (g/%)")
        ax.legend(fontsize=8, framealpha=0.9)
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_brake_fade: %s", e)
        plt.close("all")
        return None


def _chart_nervousness(result: dict, la: str, lb: str,
                       w: float = _PAGE_W_CM, h: float = _CHART_H) -> Optional[Image]:
    inputs  = result.get("driver_inputs") or {}
    if not inputs.get("available"):
        return None
    pd_data = inputs.get("per_distance") or {}
    dist    = pd_data.get("distance",      [])
    nerv_a  = pd_data.get("nervousness_a", [])
    nerv_b  = pd_data.get("nervousness_b", [])
    if not dist or not nerv_a:
        return None
    try:
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        ax.plot(dist, nerv_a, color=_COL_A, lw=1.0, label=la, alpha=0.85)
        if nerv_b:
            ax.plot(dist, nerv_b, color=_COL_B, lw=1.0, linestyle="--", label=lb, alpha=0.85)
        ax.axhline(0.5, color="#AAAAAA", lw=0.7, linestyle=":", label="Umbral medio")
        _style_ax(ax, ylabel="Nerviosismo (0–1)")
        ax.set_ylim(-0.02, 1.05)
        ax.legend(fontsize=7, framealpha=0.9)
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_nervousness: %s", e)
        plt.close("all")
        return None


def _chart_suspension(result: dict, la: str, lb: str,
                      w: float = _PAGE_W_CM, h: float = _CHART_H_TALL) -> Optional[Image]:
    susp = result.get("suspension") or {}
    if not susp.get("available"):
        return None
    pda = susp.get("per_distance_a") or {}
    pdb = susp.get("per_distance_b") or {}
    da  = pda.get("distance", [])
    db  = pdb.get("distance", [])
    if not da and not db:
        return None
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(w / 2.54, h / 2.54), sharex=False)
        fig.patch.set_facecolor("white")
        if da and pda.get("roll_f"):
            ax1.plot(da, pda["roll_f"], color=_COL_A, lw=1.1, label=f"{la} Roll-F")
            if pda.get("roll_r"):
                ax1.plot(da, pda["roll_r"], color=_COL_A, lw=0.7, linestyle=":",
                         label=f"{la} Roll-R")
        if db and pdb.get("roll_f"):
            ax1.plot(db, pdb["roll_f"], color=_COL_B, lw=1.1, linestyle="--",
                     label=f"{lb} Roll-F")
            if pdb.get("roll_r"):
                ax1.plot(db, pdb["roll_r"], color=_COL_B, lw=0.7, linestyle="-.",
                         label=f"{lb} Roll-R")
        _style_ax(ax1, xlabel="", ylabel="Roll (mm)")
        ax1.legend(fontsize=6, ncol=2, framealpha=0.9)
        if da and pda.get("pitch"):
            ax2.plot(da, pda["pitch"], color=_COL_A, lw=1.1, label=la)
        if db and pdb.get("pitch"):
            ax2.plot(db, pdb["pitch"], color=_COL_B, lw=1.1, linestyle="--", label=lb)
        _style_ax(ax2, ylabel="Pitch (mm)")
        ax2.legend(fontsize=7, framealpha=0.9)
        fig.tight_layout(pad=0.5, h_pad=0.4)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_suspension: %s", e)
        plt.close("all")
        return None


def _chart_slip(result: dict, la: str, lb: str,
                w: float = _PAGE_W_CM, h: float = _CHART_H_TALL) -> Optional[Image]:
    slip = result.get("slip_angle") or {}
    if not slip.get("available"):
        return None
    pda = slip.get("per_distance_a") or {}
    pdb = slip.get("per_distance_b") or {}
    da  = pda.get("distance", [])
    db  = pdb.get("distance", [])
    if not da and not db:
        return None
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(w / 2.54, h / 2.54), sharex=False)
        fig.patch.set_facecolor("white")
        if da and pda.get("beta"):
            ax1.plot(da, pda["beta"], color=_COL_A, lw=1.0, label=la)
        if db and pdb.get("beta"):
            ax1.plot(db, pdb["beta"], color=_COL_B, lw=1.0, linestyle="--", label=lb)
        ax1.axhline(0, color="#AAAAAA", lw=0.6)
        _style_ax(ax1, xlabel="", ylabel="β Sideslip (°)")
        ax1.legend(fontsize=7, framealpha=0.9)

        has_bal = pda.get("balance") or pdb.get("balance")
        if has_bal:
            if da and pda.get("balance"):
                ax2.plot(da, pda["balance"], color=_COL_A, lw=1.0, label=la)
            if db and pdb.get("balance"):
                ax2.plot(db, pdb["balance"], color=_COL_B, lw=1.0, linestyle="--", label=lb)
            ax2.axhline(0,  color="#AAAAAA", lw=0.6)
            ax2.axhline(2,  color="#FFAA00", lw=0.7, linestyle=":", alpha=0.8, label="US +2°")
            ax2.axhline(-2, color="#FF6600", lw=0.7, linestyle=":", alpha=0.8, label="OS −2°")
            _style_ax(ax2, ylabel="Balance αF-αR (°)")
            ax2.legend(fontsize=6, ncol=2, framealpha=0.9)
        else:
            if da and pda.get("alpha_f"):
                ax2.plot(da, pda["alpha_f"], color=_COL_A, lw=0.9, label=f"αF {la}")
                if pda.get("alpha_r"):
                    ax2.plot(da, pda["alpha_r"], color=_COL_A, lw=0.7, linestyle=":",
                             label=f"αR {la}")
            ax2.axhline(0, color="#AAAAAA", lw=0.6)
            _style_ax(ax2, ylabel="Slip neumático (°)")
            ax2.legend(fontsize=6, framealpha=0.9)

        fig.tight_layout(pad=0.5, h_pad=0.4)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_slip: %s", e)
        plt.close("all")
        return None


def _chart_corner_losses(result: dict, la: str, lb: str,
                         w: float = _PAGE_W_CM, h: float = 5.0) -> Optional[Image]:
    corners = result.get("corners") or []
    data = [(c.get("corner_number"), c.get("time_loss_seconds") or 0)
            for c in corners if abs(c.get("time_loss_seconds") or 0) >= 0.01]
    if not data:
        return None
    try:
        nums, losses = zip(*data)
        colors_bars = ["#CC2200" if v > 0 else "#006622" for v in losses]
        fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
        fig.patch.set_facecolor("white")
        bars = ax.bar(nums, losses, color=colors_bars, edgecolor="white", linewidth=0.5,
                      width=0.6, zorder=3)
        ax.axhline(0, color="#AAAAAA", lw=0.7)
        _style_ax(ax, xlabel="Número de curva", ylabel=f"Δ tiempo (s)  [+ = {lb} pierde]")
        ax.set_xticks(list(nums))
        # Add value labels on bars
        for bar, v in zip(bars, losses):
            if abs(v) >= 0.02:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        v + (0.005 if v >= 0 else -0.008),
                        f"{v:+.3f}", ha="center", va="bottom" if v >= 0 else "top",
                        fontsize=6, color="#333333")
        fig.tight_layout(pad=0.5)
        return _to_image(fig, w, h)
    except Exception as e:
        logger.warning("chart_corner_losses: %s", e)
        plt.close("all")
        return None


# ── Key findings helper ───────────────────────────────────────────────────────

def _build_key_findings(result: dict) -> list:
    """
    Return up to 5 bullet strings summarising the most important findings.
    All bullets are plain strings; callers are responsible for rendering.
    """
    findings = []

    # 1. Best lap time
    best_lap = result.get("best_lap")
    if best_lap is None:
        # Fallback: minimum lap time from laps list
        laps = result.get("laps") or []
        times = [lap.get("lap_time") for lap in laps if lap.get("lap_time") is not None]
        if times:
            best_lap = min(times)
    if best_lap is not None:
        try:
            findings.append(f"Best lap: {float(best_lap):.3f}s")
        except (TypeError, ValueError):
            findings.append(f"Best lap: {best_lap}")

    # 2. Biggest time loss corner
    corners = result.get("corners") or []
    if corners:
        worst = max(corners, key=lambda c: c.get("time_loss_seconds") or 0, default=None)
        if worst:
            tl = worst.get("time_loss_seconds") or 0
            cn = worst.get("corner_number", "?")
            if abs(tl) >= 0.01:
                findings.append(f"Biggest time loss: corner #{cn} ({tl:+.3f}s)")

    # 3. Tyre degradation
    tyre_deg = result.get("tyre_degradation") or {}
    deg = tyre_deg.get("deg_per_lap_s") or tyre_deg.get("degradation_rate_s_per_lap")
    if deg is not None:
        try:
            findings.append(f"Tyre deg: {float(deg):.3f}s/lap")
        except (TypeError, ValueError):
            pass
    else:
        if not findings or len(findings) < 5:
            findings.append("No tyre data")

    # 4. Setup note (first high-priority recommendation)
    setup = result.get("setup_sesion") or result.get("setup_advisor") or {}
    recs = setup.get("recommendations") or []
    if recs:
        first = recs[0]
        problem = first.get("problem") or first.get("recommendation") or ""
        category = first.get("category", "")
        if problem:
            note = f"{category}: {problem}" if category else problem
            if len(note) > 80:
                note = note[:77] + "..."
            findings.append(f"Setup note: {note}")
    else:
        findings.append("No setup data")

    # 5. Track evolution (omit entirely if unavailable)
    track_evo = result.get("track_evolution") or {}
    note = track_evo.get("note")
    if note:
        findings.append(f"Track evolution: {note}")

    return findings[:5]


def _section_key_findings(result: dict, s: dict) -> list:
    """
    Renders the KEY FINDINGS executive summary block at the top of the PDF body.
    Returns an empty list when no findings are available.
    """
    findings = _build_key_findings(result)
    if not findings:
        return []

    heading_style = ParagraphStyle(
        "rp_kf_heading",
        parent=s["h2"],
        fontSize=12,
        leading=15,
        spaceBefore=6,
        spaceAfter=6,
        textColor=_DARK,
        fontName="Helvetica-Bold",
    )
    bullet_style = ParagraphStyle(
        "rp_kf_bullet",
        parent=s["body"],
        fontSize=9,
        leading=14,
        leftIndent=12,
        spaceAfter=2,
    )

    elems = []
    elems.append(Paragraph("KEY FINDINGS", heading_style))
    for finding in findings:
        elems.append(Paragraph(f"•  {finding}", bullet_style))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCDD"), spaceAfter=6))
    return elems


# ── Section builders ──────────────────────────────────────────────────────────

def _section_identity(result: dict, s: dict, lang: str = 'es') -> list:
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = []
    elems.append(Paragraph("REPORTE DE COMPARACIÓN DE VUELTAS", s["title"]))
    elems.append(Paragraph("Generado automáticamente — Motorsport Analytics Pipeline", s["subtitle"]))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=_ACCENT, spaceAfter=8))
    if meta:
        rows = [
            ["Campo", la, lb],
            ["Piloto",   meta.get("driver_a",  "—"), meta.get("driver_b",  "—")],
            ["Vehículo", meta.get("vehicle_a", "—"), meta.get("vehicle_b", "—")],
        ]
        if meta.get("venue"):
            rows.append(["Circuito", meta["venue"], ""])
        tbl = Table(rows, colWidths=[3.5*cm, 8*cm, 8*cm])
        tbl.setStyle(_tbl_style())
        elems.append(tbl)
        elems.append(Spacer(1, 0.3*cm))
    if meta.get("distance_synthetic"):
        elems.append(Paragraph(
            "⚠ ADVERTENCIA: El canal Distance fue sintetizado desde velocidad. "
            "Los deltas de frenada pueden tener ±5–15 m de error.",
            s["warn"]
        ))
        elems.append(Spacer(1, 0.2*cm))
    return elems


def _section_summary(result: dict, s: dict, lang: str = 'es') -> list:
    summary = result.get("summary", {})
    meta    = result.get("metadata", {})
    la = meta.get("label_a", "Lap A")
    lb = meta.get("label_b", "Lap B")
    elems = [Paragraph("RESUMEN GENERAL", s["h2"])]
    delta = summary.get("total_time_delta") or 0.0
    if delta > 0:
        delta_txt   = f"{lb} es <b>{delta:.3f}s MÁS LENTO</b> que {la}"
        delta_color = "#CC2200"
    elif delta < 0:
        delta_txt   = f"{lb} es <b>{abs(delta):.3f}s MÁS RÁPIDO</b> que {la}"
        delta_color = "#006622"
    else:
        delta_txt   = t("pdf_identical_times", lang=lang)
        delta_color = "#444444"
    elems.append(Paragraph(f'<font color="{delta_color}">{delta_txt}</font>', s["body"]))
    elems.append(Spacer(1, 0.15*cm))
    rows = [[t("pdf_corners_analyzed", lang=lang), t("pdf_worst_corner", lang=lang), t("pdf_worst_loss", lang=lang)]]
    rows.append([
        str(summary.get("num_corners_analyzed", "—")),
        f"#{summary.get('worst_corner', '—')}",
        f"{summary.get('worst_corner_loss', 0.0):.3f}s" if summary.get("worst_corner") else "—",
    ])
    tbl = Table(rows, colWidths=[6*cm, 5*cm, 5.5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    return elems


def _section_speed_delta(result: dict, s: dict, lang: str = 'es') -> list:
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = []

    elems.append(Paragraph("TRAZADO DE VELOCIDAD", s["h2"]))
    img = _chart_speed(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "Las trazas de velocidad muestran dónde cada piloto lleva más carga. "
            "Las caídas bruscas son zonas de frenada; una frenada más tardía (más a la derecha) "
            "indica mayor confianza. El mínimo de velocidad en cada curva (apex) determina "
            "la velocidad de salida: a mayor velocidad mínima, mejor tracción de salida.",
            s["explain"]
        ))

    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph("DELTA DE TIEMPO ACUMULADO", s["h2"]))
    img_d = _chart_delta(result, la, lb)
    if img_d:
        elems.append(img_d)
        elems.append(Paragraph(
            "El delta acumulado muestra en cada metro si el piloto B va ganando o perdiendo "
            "tiempo respecto al A. Área roja: B pierde tiempo. Área azul: B recupera tiempo. "
            "Los escalones más pronunciados señalan las curvas o frenadas donde se decide "
            "la mayor parte del tiempo de vuelta.",
            s["explain"]
        ))
    return elems


def _section_brake_throttle(result: dict, s: dict, lang: str = 'es') -> list:
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("FRENO Y ACELERADOR", s["h2"])]
    img = _chart_brake_throttle(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "Freno (gráfico superior) y acelerador (inferior) permiten comparar el estilo de "
            "pilotaje. Un piloto más agresivo muestra picos de freno más altos y anticipa el "
            "acelerador antes del apex. El solapamiento freno-gas en la salida de curva es "
            "técnica avanzada que reduce el subviraje en curvas lentas.",
            s["explain"]
        ))
    return elems


def _section_gg(result: dict, s: dict, lang: str = 'es') -> list:
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("DIAGRAMA GG — CÍRCULO DE FRICCIÓN", s["h2"])]
    img = _chart_gg(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "El diagrama GG combina fuerzas laterales (X) y longitudinales (Y) de toda la vuelta. "
            "Puntos más hacia el borde del óvalo = mayor aprovechamiento de la adherencia. "
            "Las esquinas superiores del diagrama (G lateral + G longitudinal negativo) "
            "corresponden a frenada en curva; las inferiores, a aceleración en curva. "
            "Un piloto más rápido llena más el borde exterior del óvalo.",
            s["explain"]
        ))
    return elems


def _section_tyres(result: dict, s: dict, lang: str = 'es') -> list:
    tyre = result.get("tyre_analysis", {})
    if not tyre.get("available"):
        return []
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    t_min = tyre.get("t_min", 80)
    t_max = tyre.get("t_max", 100)
    STATUS_LABEL = {
        "fria": "Fría", "suboptima": "Subóptima",
        "optima": "Óptima ✓", "caliente": "Caliente",
        "sobrecalentada": "Sobrecalentada ⚠",
    }
    elems = [Paragraph(f"TEMPERATURA DE NEUMÁTICOS (ventana óptima {t_min}–{t_max}°C)", s["h2"])]
    corners_a = {c["corner"]: c for c in tyre.get("lap_a", {}).get("corners", [])}
    corners_b = {c["corner"]: c for c in tyre.get("lap_b", {}).get("corners", [])}
    all_c = sorted(set(list(corners_a.keys()) + list(corners_b.keys())))
    header = ["Posición", f"Estado {la}", f"Sup A (°C)", f"Estado {lb}", f"Sup B (°C)"]
    rows = [header]
    for corner in all_c:
        ca = corners_a.get(corner, {})
        cb = corners_b.get(corner, {})
        rows.append([
            corner,
            STATUS_LABEL.get(ca.get("window_status", ""), ca.get("window_status", "—")),
            f"{ca.get('surface_mean', 0):.1f}" if ca.get("surface_mean") is not None else "—",
            STATUS_LABEL.get(cb.get("window_status", ""), cb.get("window_status", "—")),
            f"{cb.get('surface_mean', 0):.1f}" if cb.get("surface_mean") is not None else "—",
        ])
    tbl = Table(rows, colWidths=[1.8*cm, 4.5*cm, 2.5*cm, 4.5*cm, 2.5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    elems.append(Spacer(1, 0.25*cm))
    img = _chart_tyre_bars(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "Temperatura media de superficie por neumático. Verde (óptima) = rango ideal de trabajo. "
            "Amarillo/rojo = sobretemperatura, degradación acelerada y posible graining. "
            "Azul = neumático frío, fuera de ventana de trabajo, riesgo de falta de agarre.",
            s["explain"]
        ))
    return elems


def _section_brakes(result: dict, s: dict, lang: str = 'es') -> list:
    brake = result.get("brake_analysis", {})
    if not brake.get("available"):
        return []
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("EFICIENCIA DE FRENOS", s["h2"])]
    score_a    = brake.get("score_a",    0.0) or 0.0
    score_b    = brake.get("score_b",    0.0) or 0.0
    baseline_a = brake.get("baseline_a", 1.0) or 1.0
    baseline_b = brake.get("baseline_b", 1.0) or 1.0
    deg_a = (1 - score_a / baseline_a) * 100 if baseline_a else 0
    deg_b = (1 - score_b / baseline_b) * 100 if baseline_b else 0
    rows = [
        ["", la, lb],
        ["Score (g/%)",    f"{score_a:.4f}",    f"{score_b:.4f}"],
        ["Baseline (g/%)", f"{baseline_a:.4f}", f"{baseline_b:.4f}"],
        ["Degradación",    f"{deg_a:.1f}%",     f"{deg_b:.1f}%"],
        ["Zonas de fade",  str(len(brake.get("fade_zones_a", []))),
                           str(len(brake.get("fade_zones_b", [])))],
    ]
    tbl = Table(rows, colWidths=[5*cm, 5.5*cm, 5.5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    for zones_key, lap_label in [("fade_zones_a", la), ("fade_zones_b", lb)]:
        zones = brake.get(zones_key, [])
        if zones:
            elems.append(Spacer(1, 0.15*cm))
            elems.append(Paragraph(f"Zonas de fade — {lap_label}:", s["body"]))
            fade_rows = [["Inicio (m)", "Fin (m)", "Severidad", "Diagnóstico"]]
            for z in zones:
                sev = z.get("severity", 0)
                fade_rows.append([
                    f"{z.get('start', 0):.0f}", f"{z.get('end', 0):.0f}",
                    f"{sev*100:.0f}%",
                    "Leve" if sev < 0.15 else ("Moderado" if sev < 0.30 else "Severo ⚠"),
                ])
            fade_tbl = Table(fade_rows, colWidths=[3.5*cm, 3.5*cm, 3*cm, 5*cm])
            fade_tbl.setStyle(_tbl_style())
            elems.append(fade_tbl)
    elems.append(Spacer(1, 0.25*cm))
    img = _chart_brake_fade(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "La eficiencia de frenada es el ratio deceleración (g) / presión de freno (%). "
            "Una curva descendente a lo largo de la vuelta indica fade: los frenos pierden "
            "mordiente al calentarse. Las zonas sombreadas son los segmentos detectados "
            "automáticamente. Fade severo requiere compuestos más resistentes al calor "
            "o aumentar los conductos de refrigeración.",
            s["explain"]
        ))
    return elems


def _section_inputs(result: dict, s: dict, lang: str = 'es') -> list:
    inputs = result.get("driver_inputs", {})
    if not inputs.get("available"):
        return []
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("INPUTS DEL PILOTO", s["h2"])]
    ni_a = inputs.get("nervousness_score_a", 0) or 0
    ni_b = inputs.get("nervousness_score_b", 0) or 0
    rows = [["", la, lb],
            ["Nerviosismo",
             f"{ni_a*100:.1f}%  ({inputs.get('nervousness_label_a','—')})",
             f"{ni_b*100:.1f}%  ({inputs.get('nervousness_label_b','—')})"]]
    for suffix, lbl in [("a", la), ("b", lb)]:
        bands = inputs.get(f"fft_bands_{suffix}", {}) or {}
        lo = bands.get("low",  0) * 100
        mi = bands.get("mid",  0) * 100
        hi = bands.get("high", 0) * 100
        rows.append([f"FFT B/M/A ({lbl})", f"{lo:.1f}% / {mi:.1f}% / {hi:.1f}%", ""])
    ov_a = inputs.get("overlap_pct_a")
    ov_b = inputs.get("overlap_pct_b")
    if ov_a is not None:
        rows.append(["Solapamiento freno-gas",
                     f"{ov_a:.1f}%" if ov_a is not None else "—",
                     f"{ov_b:.1f}%" if ov_b is not None else "—"])
    tbl = Table(rows, colWidths=[5.5*cm, 6*cm, 5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    elems.append(Spacer(1, 0.25*cm))
    img = _chart_nervousness(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "El índice de nerviosismo mide la frecuencia de correcciones al volante por encima "
            "de un umbral. Valores > 0.5 indican coche inestable o piloto en el límite con "
            "microcorrecciones frecuentes. FFT con alta componente de alta frecuencia (>1 Hz) "
            "sugiere lucha con la parte trasera o desequilibrio aerodinámico.",
            s["explain"]
        ))
    return elems


def _section_suspension(result: dict, s: dict, lang: str = 'es') -> list:
    susp = result.get("suspension", {})
    if not susp.get("available"):
        return []
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("SUSPENSIÓN — PITCH / ROLL / BOTTOMING", s["h2"])]
    sa = susp.get("summary_a", {}) or {}
    sb = susp.get("summary_b", {}) or {}
    rows = [["", la, lb]]
    for key, display in [
        ("max_roll_f",       "Roll máx. delantero (mm)"),
        ("max_roll_r",       "Roll máx. trasero (mm)"),
        ("max_pitch",        "Pitch máximo (mm)"),
        ("mean_pitch",       "Pitch medio (mm)"),
        ("bottoming_events", "Eventos de bottoming"),
    ]:
        va = sa.get(key)
        vb = sb.get(key)
        rows.append([display,
                     f"{va:.1f}" if isinstance(va, float) else str(va) if va is not None else "—",
                     f"{vb:.1f}" if isinstance(vb, float) else str(vb) if vb is not None else "—"])
    tbl = Table(rows, colWidths=[7*cm, 4.5*cm, 4.5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    for bot_key, lap_label in [("bottoming_a", la), ("bottoming_b", lb)]:
        events = susp.get(bot_key, [])
        if events:
            elems.append(Spacer(1, 0.15*cm))
            elems.append(Paragraph(f"Bottoming events — {lap_label}:", s["body"]))
            bot_rows = [["Corner", "Inicio (m)", "Fin (m)", "Severidad"]]
            for ev in events:
                sev = ev.get("severity", 0)
                bot_rows.append([
                    ev.get("corner", "?"),
                    f"{ev.get('start_m', 0):.0f}",
                    f"{ev.get('end_m',   0):.0f}",
                    f"{sev*100:.0f}%" + (" ⚠" if sev > 0.96 else ""),
                ])
            bot_tbl = Table(bot_rows, colWidths=[2*cm, 3*cm, 3*cm, 3*cm])
            bot_tbl.setStyle(_tbl_style())
            elems.append(bot_tbl)
    elems.append(Spacer(1, 0.25*cm))
    img = _chart_suspension(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "Roll delantero/trasero (arriba) y pitch (abajo) a lo largo de la vuelta. "
            "Roll-F elevado vs Roll-R indica subviraje mecánico; más Roll-R indica sobreviraje. "
            "Pitch positivo = frenada (morro baja); negativo = aceleración (morro sube). "
            "Los eventos de bottoming marcan zonas donde la suspensión llega al tope mecánico.",
            s["explain"]
        ))
    return elems


def _section_slip(result: dict, s: dict, lang: str = 'es') -> list:
    slip = result.get("slip_angle", {})
    if not slip.get("available"):
        return []
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "Lap A")
    lb   = meta.get("label_b", "Lap B")
    elems = [Paragraph("ÁNGULO DE DESLIZAMIENTO — SIDESLIP β", s["h2"])]
    sa = slip.get("summary_a", {}) or {}
    sb = slip.get("summary_b", {}) or {}
    rows = [["", la, lb]]
    for key, display in [
        ("beta_max",       "β max (°)"),
        ("beta_p95",       "β P95 (°)"),
        ("balance_mean",   "αF-αR balance (°)"),
        ("understeer_pct", t("pdf_understeer_pct", lang=lang)),
        ("neutral_pct",    t("pdf_neutral_pct", lang=lang)),
        ("oversteer_pct",  t("pdf_oversteer_pct", lang=lang)),
    ]:
        va = sa.get(key)
        vb = sb.get(key)
        rows.append([display,
                     f"{va:.1f}" if va is not None else "—",
                     f"{vb:.1f}" if vb is not None else "—"])
    tbl = Table(rows, colWidths=[6*cm, 4.5*cm, 4.5*cm])
    tbl.setStyle(_tbl_style())
    elems.append(tbl)
    elems.append(Spacer(1, 0.25*cm))
    img = _chart_slip(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            "β (sideslip) es el ángulo entre el vector de velocidad del coche y su eje "
            "longitudinal. Arriba: β durante la vuelta — picos positivos = sobreviraje transitorio. "
            "Abajo: balance αF-αR — valores positivos (línea amarilla = umbral US +2°) "
            "indican subviraje estructural; negativos (línea naranja = OS −2°) indican sobreviraje. "
            "Balance óptimo en GT4: ligeramente subalante (+1–3°).",
            s["explain"]
        ))
    return elems


def _section_corners(result: dict, s: dict, lang: str = 'es') -> list:
    corners = result.get("corners", [])
    if not corners:
        return []
    elems = [Paragraph("ANÁLISIS DETALLADO POR CURVA", s["h2"])]
    header = [
        t("pdf_corner_header", lang=lang),
        t("pdf_brake_delta", lang=lang),
        t("pdf_apex_delta", lang=lang),
        t("pdf_throttle_delta", lang=lang),
        t("pdf_loss_seconds", lang=lang),
        t("pdf_diagnosis", lang=lang),
    ]
    rows = [header]
    for c in corners:
        tl  = c.get("time_loss_seconds",    0.0) or 0.0
        bd  = c.get("braking_delta_meters", 0.0) or 0.0
        asd = c.get("apex_speed_delta_kmh", 0.0) or 0.0
        td  = c.get("throttle_delta_meters",0.0) or 0.0
        desc = (c.get("description", "") or "")
        if len(desc) > 80:
            desc = desc[:77] + "..."
        rows.append([
            str(c.get("corner_number", "?")),
            f"{bd:+.0f}" if abs(bd) > 0.5 else "—",
            f"{asd:+.1f}" if abs(asd) > 0.5 else "—",
            f"{td:+.0f}" if abs(td) > 1 else "—",
            f"{tl:+.3f}",
            desc,
        ])
    tbl = Table(rows, colWidths=[1.2*cm, 2.5*cm, 2.8*cm, 2*cm, 2.5*cm, 8.5*cm])
    tbl.setStyle(_tbl_style())
    for i, c in enumerate(corners, start=1):
        tl = c.get("time_loss_seconds", 0.0) or 0.0
        if tl > 0.05:
            tbl.setStyle(TableStyle([("TEXTCOLOR", (4, i), (4, i), _RED)]))
        elif tl < -0.05:
            tbl.setStyle(TableStyle([("TEXTCOLOR", (4, i), (4, i), _GREEN)]))
    elems.append(tbl)
    return elems


def _section_corner_analysis(result: dict, s: dict, lang: str = 'es') -> list:
    meta = result.get("metadata", {})
    la   = meta.get("label_a", "A")
    lb   = meta.get("label_b", "B")
    advisor = result.get("setup_advisor") or {}
    priority = advisor.get("corner_priority", [])
    elems = [Paragraph("ANÁLISIS DE PÉRDIDA DE TIEMPO POR CURVA", s["h2"])]

    img = _chart_corner_losses(result, la, lb)
    if img:
        elems.append(img)
        elems.append(Paragraph(
            f"Barras rojas = {lb} pierde tiempo respecto a {la}. "
            "Barras verdes = {lb} gana tiempo. Los escalones más altos indican las curvas "
            "que más afectan al tiempo de vuelta total.",
            s["explain"]
        ))

    if priority:
        elems.append(Spacer(1, 0.25*cm))
        elems.append(Paragraph("Curvas prioritarias — dónde se decide la vuelta:", s["body"]))
        header = [
            "#",
            t("pdf_corner_header", lang=lang),
            t("pdf_loss_seconds", lang=lang),
            t("pdf_brake_delta", lang=lang),
            t("pdf_apex_delta", lang=lang),
            t("pdf_throttle_delta", lang=lang),
            t("pdf_dominant_phase", lang=lang),
            t("pdf_action", lang=lang),
        ]
        rows = [header]
        PHASE_ES = {"frenada": "Frenada", "apex": "Apex", "salida": "Salida"}
        for i, c in enumerate(priority, 1):
            rows.append([
                str(i),
                str(c.get("corner_number", "?")),
                f"{c.get('time_loss_seconds', 0):+.3f}s",
                f"{c.get('braking_delta_meters', 0):+.0f} m"  if abs(c.get('braking_delta_meters', 0)) > 0.5 else "—",
                f"{c.get('apex_speed_delta_kmh', 0):+.1f} km/h" if abs(c.get('apex_speed_delta_kmh', 0)) > 0.5 else "—",
                f"{c.get('throttle_delta_meters', 0):+.0f} m"  if abs(c.get('throttle_delta_meters', 0)) > 0.5 else "—",
                PHASE_ES.get(c.get("dominant_phase", ""), "—"),
                (c.get("focus", "") or "")[:35],
            ])
        tbl = Table(rows, colWidths=[0.6*cm, 1.2*cm, 1.8*cm, 2.0*cm, 2.4*cm, 1.8*cm, 2.2*cm, 5.0*cm])
        tbl.setStyle(_tbl_style())
        # Highlight time-loss column red for losers
        for i, c in enumerate(priority, 1):
            if c.get("time_loss_seconds", 0) > 0.05:
                tbl.setStyle(TableStyle([("TEXTCOLOR", (2, i), (2, i), _RED)]))
        elems.append(tbl)
    return elems


def _section_setup_advisor(result: dict, s: dict, lang: str = 'es') -> list:
    advisor = result.get("setup_advisor") or {}
    if not advisor.get("available"):
        return []
    recs = advisor.get("recommendations", [])
    if not recs:
        return []

    PRIORITY_STYLE = {"alta": ("⚠", "#CC2200"), "media": ("●", "#AA7700"), "baja": ("○", "#006622")}
    elems = [Paragraph("RECOMENDACIONES DE SETUP", s["h2"])]

    # Summary
    gain = advisor.get("total_gain_range", "—")
    elems.append(Paragraph(
        f"<b>{len(recs)} recomendaciones identificadas</b> — ganancia potencial total: "
        f"<b>{gain}s/vuelta</b> si se aplican todos los cambios de forma óptima.",
        s["body"]
    ))
    elems.append(Spacer(1, 0.2*cm))

    # Group by priority
    for prio_key, prio_label in [("alta", "PRIORIDAD ALTA"), ("media", "PRIORIDAD MEDIA"), ("baja", "PRIORIDAD BAJA")]:
        group = [r for r in recs if r.get("priority") == prio_key]
        if not group:
            continue
        icon, col_hex = PRIORITY_STYLE.get(prio_key, ("●", "#555555"))
        rl_col = colors.HexColor(col_hex)
        elems.append(Paragraph(f"{icon} {prio_label}", ParagraphStyle(
            f"rp_prio_{prio_key}", parent=s["body"],
            fontSize=9, fontName="Helvetica-Bold", textColor=rl_col,
            spaceBefore=8, spaceAfter=3,
        )))
        header = [
            t("pdf_setup_area", lang=lang),
            t("pdf_setup_problem", lang=lang),
            t("pdf_setup_rec", lang=lang),
            t("pdf_setup_gain", lang=lang),
        ]
        rows = [header]
        for r in group:
            problem = r.get("problem", "")
            if len(problem) > 55:
                problem = problem[:52] + "..."
            rec_text = r.get("recommendation", "")
            if len(rec_text) > 80:
                rec_text = rec_text[:77] + "..."
            rows.append([
                r.get("category", "")[:22],
                problem,
                rec_text,
                r.get("expected_gain", "—"),
            ])
        tbl = Table(rows, colWidths=[3.5*cm, 5.0*cm, 6.5*cm, 2.0*cm])
        tbl.setStyle(_tbl_style())
        elems.append(tbl)
        elems.append(Spacer(1, 0.15*cm))

    elems.append(Paragraph(
        "* Ganancias estimadas son rangos teóricos. Aplicar cambios de forma incremental y verificar en pista.",
        s["caption"]
    ))
    return elems


# ── Main entry point ──────────────────────────────────────────────────────────

def export_report_pdf(comparison_result: dict, filepath: Optional[str] = None, lang: str = "es") -> bytes:
    """
    Generate a comprehensive PDF report with matplotlib charts from a comparison result dict.
    Returns PDF bytes; optionally saves to filepath.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm,  bottomMargin=1.5*cm,
    )
    s     = _styles()
    story: list = []

    story += _section_identity(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.4*cm))
    story += _section_key_findings(comparison_result, s)
    story.append(Spacer(1, 0.2*cm))
    story += _section_summary(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.4*cm))
    story += _section_speed_delta(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_brake_throttle(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_gg(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_tyres(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_brakes(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_inputs(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_suspension(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_slip(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_corner_analysis(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_setup_advisor(comparison_result, s, lang=lang)
    story.append(Spacer(1, 0.3*cm))
    story += _section_corners(comparison_result, s, lang=lang)

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#AAAACC")))
    story.append(Paragraph("Generado por Motorsport Analytics Pipeline", s["caption"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    if filepath:
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
        logger.info("PDF guardado: %s (%d KB)", filepath, len(pdf_bytes) // 1024)
    return pdf_bytes
