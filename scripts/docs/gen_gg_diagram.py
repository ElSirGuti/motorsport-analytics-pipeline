"""
gen_gg_diagram.py
Generates synthetic illustration images for docs/03_gg_diagram.md.
All data is produced with NumPy — no telemetry files are read.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import os

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..",
    "docs", "images", "gg_diagram",
)
OUT_DIR = os.path.normpath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
plt.style.use("dark_background")

BG_FIGURE = "#060A14"
BG_AXES   = "#0A0F1E"
CYAN      = "#00D4FF"
RED       = "#FF3D3D"
GREEN     = "#00E676"
AMBER     = "#FFB300"
ORANGE    = "#FF6B35"
PURPLE    = "#7C3AED"
DIM       = "#4A5578"
WHITE     = "#E8EAF0"

GRID_COLOR = (1, 1, 1, 0.07)

DPI = 150


def _style_ax(ax):
    ax.set_facecolor(BG_AXES)
    ax.tick_params(colors=DIM, labelsize=8)
    ax.xaxis.label.set_color(WHITE)
    ax.yaxis.label.set_color(WHITE)
    ax.title.set_color(WHITE)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5)


def _efficiency_color(eff):
    """Return RGBA color for a scalar efficiency value."""
    if eff >= 90:
        return GREEN
    elif eff >= 70:
        return AMBER
    elif eff >= 50:
        return ORANGE
    else:
        return RED


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------
rng = np.random.default_rng(42)

def _synthetic_lap(n=600):
    """
    Generate a synthetic lap of (distance, speed, lat_g, lon_g) data
    that looks like a realistic single-seater lap.
    """
    distance = np.linspace(0, 3200, n)
    # speed profile: sinusoidal base with corners
    t = np.linspace(0, 2 * np.pi * 6, n)
    speed = 80 + 60 * (0.5 + 0.5 * np.sin(t)) + rng.normal(0, 3, n)
    speed = np.clip(speed, 30, 220)

    # Smooth speed to get realistic acceleration
    from numpy.lib.stride_tricks import sliding_window_view
    kernel = np.ones(15) / 15
    speed_smooth = np.convolve(speed, kernel, mode="same")

    # Longitudinal G from speed gradient
    ds = distance[1] - distance[0]
    dv_ds = np.gradient(speed_smooth / 3.6, ds)
    lon_g = dv_ds * (speed_smooth / 3.6) / 9.81
    lon_g = np.clip(lon_g, -4.5, 3.5)

    # Lateral G: correlated with speed changes (corners)
    # Build curvature from sinusoidal track
    kappa = 0.004 * np.abs(np.sin(t * 1.3)) + 0.001 * np.abs(np.cos(t * 2.7))
    lat_g = (speed_smooth / 3.6) ** 2 * kappa / 9.81
    lat_g += rng.normal(0, 0.05, n)
    lat_g = np.clip(lat_g, 0, 3.5)

    # Give sign (left/right) based on track direction
    sign = np.sign(np.sin(t * 1.3 + 0.4))
    lat_g = lat_g * sign

    # G_sum and efficiency
    g_sum = np.sqrt(lat_g**2 + lon_g**2)
    g_limit = np.percentile(g_sum, 95)
    if g_limit < 0.1:
        g_limit = 1.0
    efficiency = np.clip(g_sum / g_limit * 100, 0, 120)

    return distance, speed_smooth, lat_g, lon_g, g_sum, efficiency, g_limit


distance, speed, lat_g, lon_g, g_sum, efficiency, g_limit = _synthetic_lap()


# ---------------------------------------------------------------------------
# Fig 1 — friction_circle.png
# ---------------------------------------------------------------------------
def fig_friction_circle():
    fig, ax = plt.subplots(figsize=(6, 6), facecolor=BG_FIGURE)
    _style_ax(ax)

    # Scatter colored by efficiency
    colors = [_efficiency_color(e) for e in efficiency]
    ax.scatter(lat_g, lon_g, c=colors, s=5, alpha=0.75, linewidths=0)

    # Friction limit circle (dashed white)
    theta = np.linspace(0, 2 * np.pi, 300)
    ax.plot(g_limit * np.cos(theta), g_limit * np.sin(theta),
            color=WHITE, linestyle="--", linewidth=1.2, label=f"Límite μ·g = {g_limit:.2f} G", alpha=0.8)

    # Zero axes
    ax.axhline(0, color=DIM, linewidth=0.7, alpha=0.6)
    ax.axvline(0, color=DIM, linewidth=0.7, alpha=0.6)

    lim = g_limit * 1.15
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim * 1.2, lim * 0.8)

    ax.set_xlabel("$G_{lateral}$ [g]", fontsize=10)
    ax.set_ylabel("$G_{longitudinal}$ [g]", fontsize=10)
    ax.set_title("Diagrama G-G — Círculo de Fricción", fontsize=12, fontweight="bold", color=WHITE, pad=10)

    # Legend patches
    patches = [
        mpatches.Patch(color=GREEN,  label="≥ 90 % eficiencia"),
        mpatches.Patch(color=AMBER,  label="70 – 90 %"),
        mpatches.Patch(color=ORANGE, label="50 – 70 %"),
        mpatches.Patch(color=RED,    label="< 50 %"),
    ]
    ax.legend(handles=patches, loc="lower right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)
    ax.legend(handles=patches + [
        plt.Line2D([0], [0], color=WHITE, linestyle="--", linewidth=1.2, label=f"Límite {g_limit:.2f} G")
    ], loc="lower right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)

    # Braking/accel labels
    ax.text(0.02, 0.97, "ACELERACIÓN ↑", transform=ax.transAxes,
            fontsize=7, color=GREEN, alpha=0.7, va="top")
    ax.text(0.02, 0.03, "FRENADA ↓", transform=ax.transAxes,
            fontsize=7, color=RED, alpha=0.7, va="bottom")
    ax.text(0.97, 0.5, "DERECHA →", transform=ax.transAxes,
            fontsize=7, color=CYAN, alpha=0.7, ha="right", va="center")
    ax.text(0.03, 0.5, "← IZQUIERDA", transform=ax.transAxes,
            fontsize=7, color=CYAN, alpha=0.7, ha="left", va="center")

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "friction_circle.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG_FIGURE)
    plt.close(fig)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Fig 2 — efficiency_over_distance.png
# ---------------------------------------------------------------------------
def fig_efficiency_over_distance():
    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG_FIGURE)
    _style_ax(ax)

    dist_km = distance / 1000.0

    # Draw the efficiency line
    ax.plot(dist_km, efficiency, color=CYAN, linewidth=1.0, alpha=0.9, zorder=3)

    # Fill regions by threshold
    ax.fill_between(dist_km, efficiency, 100, where=(efficiency >= 90),
                    color=GREEN, alpha=0.20, interpolate=True, label="≥ 90 % (verde)")
    ax.fill_between(dist_km, efficiency, 100, where=((efficiency >= 70) & (efficiency < 90)),
                    color=AMBER, alpha=0.20, interpolate=True, label="70 – 90 % (ámbar)")
    ax.fill_between(dist_km, efficiency, 100, where=(efficiency < 70),
                    color=RED, alpha=0.25, interpolate=True, label="< 70 % (rojo)")

    # Threshold lines
    ax.axhline(90, color=GREEN, linewidth=0.8, linestyle="--", alpha=0.6)
    ax.axhline(70, color=AMBER, linewidth=0.8, linestyle="--", alpha=0.6)
    ax.text(dist_km[-1] * 1.001, 91, "90 %", color=GREEN, fontsize=7, va="bottom")
    ax.text(dist_km[-1] * 1.001, 71, "70 %", color=AMBER, fontsize=7, va="bottom")

    ax.set_xlim(0, dist_km[-1])
    ax.set_ylim(0, 115)
    ax.set_xlabel("Distancia [km]", fontsize=10)
    ax.set_ylabel("Eficiencia G [%]", fontsize=10)
    ax.set_title("Eficiencia del Círculo de Fricción a lo largo de la vuelta", fontsize=12,
                 fontweight="bold", color=WHITE, pad=10)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "efficiency_over_distance.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG_FIGURE)
    plt.close(fig)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Fig 3 — kinematic_vs_sensor.png
# ---------------------------------------------------------------------------
def fig_kinematic_vs_sensor():
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), facecolor=BG_FIGURE, sharex=True)
    fig.subplots_adjust(hspace=0.08)

    dist_km = distance / 1000.0

    # Simulate sensor readings as kinematic + small noise + bias
    lat_sensor  = lat_g  + rng.normal(0, 0.04, len(lat_g))
    lon_sensor  = lon_g  + rng.normal(0, 0.06, len(lon_g))

    # Top: lateral G
    ax = axes[0]
    _style_ax(ax)
    ax.plot(dist_km, lat_sensor, color=CYAN,   linewidth=1.0, alpha=0.9, label="Sensor IMU")
    ax.plot(dist_km, lat_g,      color=AMBER,  linewidth=1.0, alpha=0.85, linestyle="--", label="Estimación cinemática")
    ax.axhline(0, color=DIM, linewidth=0.5, alpha=0.5)
    ax.set_ylabel("$G_{lateral}$ [g]", fontsize=9)
    ax.set_title("Comparación Sensor vs Estimación Cinemática", fontsize=12,
                 fontweight="bold", color=WHITE, pad=10)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)

    # Bottom: longitudinal G
    ax = axes[1]
    _style_ax(ax)
    ax.plot(dist_km, lon_sensor, color=GREEN,  linewidth=1.0, alpha=0.9, label="Sensor IMU")
    ax.plot(dist_km, lon_g,      color=PURPLE, linewidth=1.0, alpha=0.85, linestyle="--", label="Estimación cinemática")
    ax.axhline(0, color=DIM, linewidth=0.5, alpha=0.5)
    ax.set_ylabel("$G_{longitudinal}$ [g]", fontsize=9)
    ax.set_xlabel("Distancia [km]", fontsize=9)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)

    # Annotate a braking phase (find strongest braking zone)
    braking_idx = np.argmin(lon_g)
    bx = dist_km[braking_idx]
    for axi in axes:
        axi.axvspan(bx - 0.05, bx + 0.05, color=RED, alpha=0.12)
    axes[1].annotate("Fase de\nfrenada",
                     xy=(bx, lon_g[braking_idx]),
                     xytext=(bx + 0.12, lon_g[braking_idx] + 0.8),
                     fontsize=7, color=RED,
                     arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "kinematic_vs_sensor.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG_FIGURE)
    plt.close(fig)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Fig 4 — gg_quadrant.png
# ---------------------------------------------------------------------------
def fig_gg_quadrant():
    fig, ax = plt.subplots(figsize=(7, 7), facecolor=BG_FIGURE)
    _style_ax(ax)

    # Classify each point by driving phase
    phase_color = []
    phase_label = []
    for lx, ly in zip(lat_g, lon_g):
        if ly > 0:
            # Aceleración
            col = GREEN if lx > 0 else CYAN
            lbl = "Aceleración + Derecha" if lx > 0 else "Aceleración + Izquierda"
        else:
            # Frenada
            col = RED if lx > 0 else PURPLE
            lbl = "Frenada + Derecha" if lx > 0 else "Frenada + Izquierda"
        phase_color.append(col)
        phase_label.append(lbl)

    ax.scatter(lat_g, lon_g, c=phase_color, s=6, alpha=0.70, linewidths=0)

    # Friction circle
    theta = np.linspace(0, 2 * np.pi, 300)
    ax.plot(g_limit * np.cos(theta), g_limit * np.sin(theta),
            color=WHITE, linestyle="--", linewidth=1.0, alpha=0.5)

    # Quadrant dividers
    ax.axhline(0, color=DIM, linewidth=1.0, alpha=0.7)
    ax.axvline(0, color=DIM, linewidth=1.0, alpha=0.7)

    lim = g_limit * 1.2
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim * 1.2, lim * 0.8)

    pad = lim * 0.07
    fs = 8
    ax.text( lim - pad,  lim * 0.55, "Aceleración\n+ Derecha",   color=GREEN,  fontsize=fs, ha="right", va="top",    alpha=0.85)
    ax.text(-lim + pad,  lim * 0.55, "Aceleración\n+ Izquierda", color=CYAN,   fontsize=fs, ha="left",  va="top",    alpha=0.85)
    ax.text( lim - pad, -lim * 1.0,  "Frenada\n+ Derecha",       color=RED,    fontsize=fs, ha="right", va="bottom", alpha=0.85)
    ax.text(-lim + pad, -lim * 1.0,  "Frenada\n+ Izquierda",     color=PURPLE, fontsize=fs, ha="left",  va="bottom", alpha=0.85)

    ax.set_xlabel("$G_{lateral}$ [g]", fontsize=10)
    ax.set_ylabel("$G_{longitudinal}$ [g]", fontsize=10)
    ax.set_title("Diagrama G-G — Cuadrantes de Fase de Conducción", fontsize=12,
                 fontweight="bold", color=WHITE, pad=10)

    patches = [
        mpatches.Patch(color=GREEN,  label="Aceleración + Derecha"),
        mpatches.Patch(color=CYAN,   label="Aceleración + Izquierda"),
        mpatches.Patch(color=RED,    label="Frenada + Derecha"),
        mpatches.Patch(color=PURPLE, label="Frenada + Izquierda"),
    ]
    ax.legend(handles=patches, loc="upper right", fontsize=7,
              facecolor=BG_AXES, edgecolor=DIM, labelcolor=WHITE, framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "gg_quadrant.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG_FIGURE)
    plt.close(fig)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Writing images to: {OUT_DIR}")
    fig_friction_circle()
    fig_efficiency_over_distance()
    fig_kinematic_vs_sensor()
    fig_gg_quadrant()
    print("Generated images for gg_diagram")
