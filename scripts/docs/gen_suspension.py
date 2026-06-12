"""
gen_suspension.py
-----------------
Generate synthetic documentation images for the Suspension (pitch/roll/bottoming) module.
All data is produced with NumPy — no telemetry files are read.
Output: docs/images/suspension/
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy.ndimage import uniform_filter1d
import os

# ---------------------------------------------------------------------------
# Paths and palette
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "images", "suspension"
)
os.makedirs(OUT_DIR, exist_ok=True)

BG_FIGURE  = "#060A14"
BG_AXES    = "#0A0F1E"
CYAN       = "#00D4FF"
RED        = "#FF3D3D"
GREEN      = "#00E676"
AMBER      = "#FFB300"
YELLOW     = "#FFD93D"
DIM        = "#4A5578"
GRID_COLOR = (1, 1, 1, 0.07)

CORNER_COLORS = {"FL": CYAN, "FR": "#FF6B6B", "RL": YELLOW, "RR": "#6BCB77"}


def apply_ax_style(ax):
    ax.set_facecolor(BG_AXES)
    ax.tick_params(colors=DIM, labelsize=8)
    ax.xaxis.label.set_color(DIM)
    ax.yaxis.label.set_color(DIM)
    ax.title.set_color(CYAN)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)
        spine.set_linewidth(0.6)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5)


# ===========================================================================
# Synthetic data: 4-corner suspension travel over a lap
# ===========================================================================
np.random.seed(42)
N = 3200
dist = np.linspace(0, 3200, N)

# Base ride height (25 mm) + aero contribution at high speed (rectas)
base = 25.0

# Speed envelope: high on straights, low in corners
speed_env = 0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(np.ones(N) * 0.0008))

# Roll component: positive in right-hand curves, negative in left
roll_signal = 8.0 * np.sin(2 * np.pi * dist / 600 + 0.3)
roll_signal = uniform_filter1d(roll_signal, size=40)

# Pitch component: negative (morro baja) in braking zones
pitch_signal = -6.0 * np.clip(-np.sin(2 * np.pi * dist / 800 + 0.8), 0, 1)
pitch_signal = uniform_filter1d(pitch_signal, size=20)

noise = lambda: np.random.normal(0, 0.5, N)

# 4 corners
FL = base + pitch_signal / 2 - roll_signal / 2 + noise()
FR = base + pitch_signal / 2 + roll_signal / 2 + noise()
RL = base - pitch_signal / 2 - roll_signal / 2 + noise()
RR = base - pitch_signal / 2 + roll_signal / 2 + noise()

# Smooth
FL = uniform_filter1d(FL, 15)
FR = uniform_filter1d(FR, 15)
RL = uniform_filter1d(RL, 15)
RR = uniform_filter1d(RR, 15)

# Inject bottoming events
def inject_bottoming(arr, start_idx, length, peak):
    spike = np.zeros(length)
    spike[:length//2] = np.linspace(0, peak, length//2)
    spike[length//2:] = np.linspace(peak, 0, length - length//2)
    arr = arr.copy()
    arr[start_idx:start_idx+length] += spike
    return arr

FL = inject_bottoming(FL, 1100, 40, 14.0)
RR = inject_bottoming(RR, 2300, 55, 18.0)
FR = inject_bottoming(FR, 2750, 35, 12.0)

# Derived channels
front_avg = (FL + FR) / 2
rear_avg  = (RL + RR) / 2
roll_f    = FR - FL
roll_r    = RR - RL
pitch     = front_avg - rear_avg


# ===========================================================================
# Figure 1 — Roll and Pitch Over the Lap
# ===========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
fig.patch.set_facecolor(BG_FIGURE)

# Roll delantero
ax1.plot(dist, roll_f, color=CYAN, linewidth=1.5, label="Roll Ax. Del. (FR−FL)")
ax1.plot(dist, roll_r, color=YELLOW, linewidth=1.0, alpha=0.7, label="Roll Ax. Tra. (RR−RL)")
ax1.axhline(0, color=DIM, linewidth=0.8, linestyle="--", alpha=0.5)
ax1.fill_between(dist, 0, roll_f, where=(roll_f > 5), color=CYAN, alpha=0.12)
ax1.fill_between(dist, 0, roll_f, where=(roll_f < -5), color="#FF6B6B", alpha=0.12)
ax1.set_ylabel("Roll (mm)")
ax1.set_title("Fig 1 — Roll y Pitch del Chasis a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax1.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax1)

# Pitch
ax2.plot(dist, pitch, color=AMBER, linewidth=1.5, label="Pitch (Front_avg − Rear_avg)")
ax2.axhline(0, color=DIM, linewidth=0.8, linestyle="--", alpha=0.5)
ax2.fill_between(dist, pitch, 0, where=(pitch < 0), color=AMBER, alpha=0.15,
                 label="Frenada (morro baja)")
ax2.fill_between(dist, pitch, 0, where=(pitch > 0), color=GREEN, alpha=0.10,
                 label="Aceleración (cola baja)")
ax2.set_xlabel("Distancia (m)")
ax2.set_ylabel("Pitch (mm)")
ax2.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax2)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "roll_pitch_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] roll_pitch_lap.png")


# ===========================================================================
# Figure 2 — 4 Individual Corner Travels
# ===========================================================================
BOTTOM_FRACTION = 0.90

fig, axes = plt.subplots(2, 2, figsize=(12, 6), sharex=True)
fig.patch.set_facecolor(BG_FIGURE)

for ax, (label, series) in zip(axes.flat,
                                [("FL", FL), ("FR", FR), ("RL", RL), ("RR", RR)]):
    apply_ax_style(ax)
    color = CORNER_COLORS[label]
    ax.plot(dist, series, color=color, linewidth=1.2)
    ax.fill_between(dist, series.min() - 1, series, color=color, alpha=0.10)

    # Bottoming threshold
    max_t = series.max()
    thresh = max_t * BOTTOM_FRACTION
    ax.axhline(thresh, color=RED, linestyle="--", linewidth=1.0, alpha=0.7,
               label=f"Umbral {BOTTOM_FRACTION*100:.0f}% = {thresh:.1f}mm")

    # Mark bottoming events
    bottoming = series >= thresh
    if bottoming.any():
        ax.scatter(dist[bottoming], series[bottoming],
                   color=RED, s=10, zorder=5, alpha=0.8)

    ax.set_title(label, fontsize=10, fontweight="bold")
    ax.set_ylabel("Recorrido (mm)")
    ax.legend(fontsize=7, loc="lower right", facecolor=BG_AXES, edgecolor=DIM)

for ax in axes[1]:
    ax.set_xlabel("Distancia (m)")

fig.suptitle("Fig 2 — Recorridos Individuales de los 4 Amortiguadores",
             fontsize=11, fontweight="bold", color=CYAN)
fig.patch.set_facecolor(BG_FIGURE)
fig.tight_layout(pad=1.0, rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(OUT_DIR, "travel_4corners.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] travel_4corners.png")


# ===========================================================================
# Figure 3 — Bottoming Events Diagram
# ===========================================================================
# Detect synthetic bottoming events
bottoming_events = []
for label, series in [("FL", FL), ("FR", FR), ("RL", RL), ("RR", RR)]:
    max_t = series.max()
    thresh = max_t * BOTTOM_FRACTION
    mask = series >= thresh
    in_ev, start_i = False, 0
    for i in range(len(mask)):
        if mask[i] and not in_ev:
            in_ev, start_i = True, i
        elif not mask[i] and in_ev:
            in_ev = False
            length_m = dist[i-1] - dist[start_i]
            if length_m >= 3.0:
                sev = float(series[start_i:i].max() / max_t)
                bottoming_events.append({
                    "corner": label, "start": dist[start_i], "end": dist[i-1],
                    "severity": sev, "color": CORNER_COLORS[label]
                })

fig, ax = plt.subplots(figsize=(12, 3.5))
fig.patch.set_facecolor(BG_FIGURE)
ax.set_facecolor(BG_AXES)

# Track baseline
ax.axhline(0.5, color=DIM, linewidth=2.0, alpha=0.35)

# Bottoming bars
y_offsets = {"FL": 0.65, "FR": 0.55, "RL": 0.45, "RR": 0.35}
for ev in bottoming_events:
    y = y_offsets[ev["corner"]]
    h = ev["severity"] * 0.35
    ax.barh(y, ev["end"] - ev["start"], left=ev["start"],
            height=h, color=ev["color"], alpha=0.80)
    cx = (ev["start"] + ev["end"]) / 2
    ax.text(cx, y + h / 2, f"{ev['corner']}\n{ev['severity']*100:.0f}%",
            ha="center", va="center", fontsize=7, color="black", fontweight="bold")

# Corner legend
legend_elements = [Line2D([0], [0], color=CORNER_COLORS[c], linewidth=4, label=c)
                   for c in ["FL", "FR", "RL", "RR"]]
ax.legend(handles=legend_elements, fontsize=8, loc="upper right",
          facecolor=BG_AXES, edgecolor=DIM)

ax.set_xlim(0, 3200)
ax.set_ylim(0.2, 1.0)
ax.set_xlabel("Distancia (m)")
ax.set_yticks([])
ax.set_title("Fig 3 — Eventos de Bottoming Detectados", fontsize=11, fontweight="bold",
             color=CYAN)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "bottoming_events.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] bottoming_events.png")

print("Generated images for suspension")
