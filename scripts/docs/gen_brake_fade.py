"""
gen_brake_fade.py
-----------------
Generate synthetic documentation images for the Brake Fade module.
All data is produced with NumPy — no telemetry files are read.
Output: docs/images/brake_fade/
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os

# ---------------------------------------------------------------------------
# Paths and palette
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "images", "brake_fade"
)
os.makedirs(OUT_DIR, exist_ok=True)

BG_FIGURE  = "#060A14"
BG_AXES    = "#0A0F1E"
CYAN       = "#00D4FF"
RED        = "#FF3D3D"
GREEN      = "#00E676"
AMBER      = "#FFB300"
DIM        = "#4A5578"
GRID_COLOR = (1, 1, 1, 0.07)

FADE_DROP = 0.15


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
# Figure 1 — Efficiency Over the Lap
# ===========================================================================
np.random.seed(42)

dist = np.linspace(0, 3200, 600)
# Simulate discrete braking zones (positions of main braking points)
brake_zones_dist  = [200, 550, 900, 1300, 1650, 2100, 2450, 2900]
brake_zones_width = [80,  60,  100, 90,   70,   110,  80,   90  ]

# Build braking mask
braking_mask = np.zeros(len(dist), dtype=bool)
for d0, w in zip(brake_zones_dist, brake_zones_width):
    braking_mask |= (dist >= d0) & (dist <= d0 + w)

# Baseline efficiency
baseline = 0.045   # g per 1% brake pressure

# Vuelta A: gradual fade (last 2 brake zones degrade)
eff_A = np.full(len(dist), np.nan)
fade_factor_A = np.ones(len(dist))
fade_factor_A[dist > 2000] = np.linspace(1.0, 0.75, np.sum(dist > 2000))
eff_A[braking_mask] = (baseline * fade_factor_A[braking_mask]
                        + np.random.normal(0, 0.002, np.sum(braking_mask)))

# Vuelta B: no fade (control lap, first third of stint)
eff_B = np.full(len(dist), np.nan)
eff_B[braking_mask] = baseline + np.random.normal(0, 0.002, np.sum(braking_mask))

fig, ax = plt.subplots(figsize=(12, 4.5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

# Baseline line
ax.axhline(baseline, color=AMBER, linestyle="--", linewidth=1.2, alpha=0.7,
           label=f"Baseline = {baseline:.3f} g/%")
ax.axhline(baseline * (1 - FADE_DROP), color=RED, linestyle="--", linewidth=1.0, alpha=0.6,
           label=f"Umbral fade (−{FADE_DROP*100:.0f}% baseline)")

# Plot efficiencies
ax.scatter(dist[braking_mask], eff_A[braking_mask],
           color=CYAN, s=15, alpha=0.7, label="Vuelta A (degradada)")
ax.scatter(dist[braking_mask], eff_B[braking_mask],
           color=GREEN, s=12, alpha=0.6, label="Vuelta B (referencia)")

# Fade zone shading (where A drops below threshold)
threshold = baseline * (1 - FADE_DROP)
fade_where = braking_mask & ~np.isnan(eff_A) & (eff_A < threshold)
for i in np.where(np.diff(fade_where.astype(int)) == 1)[0]:
    j_candidates = np.where(np.diff(fade_where[i:].astype(int)) == -1)[0]
    j = i + j_candidates[0] + 1 if len(j_candidates) > 0 else len(dist) - 1
    ax.axvspan(dist[i], dist[j], color=RED, alpha=0.15)

ax.set_xlabel("Distancia (m)")
ax.set_ylabel("Eficiencia  |LonG| / (presión/100)  (g/%)")
ax.set_title("Fig 1 — Eficiencia de Frenado a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax.set_xlim(0, 3200)
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

# Fade annotation
ax.annotate(
    "Fade activo:\neficiencia caída >15%",
    xy=(2200, baseline * 0.82),
    xytext=(2000, baseline * 0.65),
    arrowprops=dict(arrowstyle="->", color=RED, lw=1.2),
    color=RED, fontsize=8,
)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "efficiency_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] efficiency_lap.png")


# ===========================================================================
# Figure 2 — Baseline Degradation Over the Stint
# ===========================================================================
np.random.seed(13)

n_laps = 18
laps = np.arange(1, n_laps + 1)

# True baseline degrades exponentially
baseline_true = baseline * (1.0 - 0.015 * (laps - 1) + np.random.normal(0, 0.0015, n_laps))
critical_threshold = baseline * 0.85

fig, ax = plt.subplots(figsize=(10, 4.5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.plot(laps, baseline_true, color=CYAN, linewidth=2.0, marker="o",
        markersize=4, label="Baseline por vuelta")
ax.axhline(baseline, color=GREEN, linestyle="--", linewidth=1.0, alpha=0.8,
           label=f"Baseline inicial = {baseline:.3f}")
ax.axhline(critical_threshold, color=AMBER, linestyle="--", linewidth=1.0, alpha=0.8,
           label="Umbral crítico (85%)")

# Shade degradation zone
ax.fill_between(laps, baseline_true, baseline,
                where=(baseline_true < baseline), color=RED, alpha=0.10)

# Mark laps below threshold
below = baseline_true < critical_threshold
if below.any():
    ax.scatter(laps[below], baseline_true[below], color=RED, s=50, zorder=5,
               label="Fade severo", marker="X")

ax.set_xlabel("Número de Vuelta")
ax.set_ylabel("Eficiencia Baseline (g/%)")
ax.set_title("Fig 2 — Degradación del Baseline a lo largo del Stint", fontsize=11, fontweight="bold")
ax.set_xlim(0.5, n_laps + 0.5)
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "baseline_degradation.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] baseline_degradation.png")


# ===========================================================================
# Figure 3 — Fade Zone Map on Track
# ===========================================================================
np.random.seed(77)

# Synthetic fade zones: (start, end, severity)
fade_zones = [
    (820, 875, 0.11),
    (2090, 2160, 0.22),
    (2430, 2510, 0.31),
    (2880, 2960, 0.28),
]

braking_labels = [(190, "F1"), (540, "F2"), (890, "F3"), (1290, "F4"),
                  (1640, "F5"), (2090, "F6"), (2440, "F7"), (2880, "F8")]

def severity_color(s):
    if s < 0.15: return GREEN
    if s < 0.25: return AMBER
    return RED

fig, ax = plt.subplots(figsize=(13, 3))
fig.patch.set_facecolor(BG_FIGURE)
ax.set_facecolor(BG_AXES)

# Track baseline
ax.axhline(0.5, color=DIM, linewidth=2.5, alpha=0.4)

# Braking zone markers
for d, label in braking_labels:
    ax.axvline(d, color=DIM, linewidth=1.5, alpha=0.3, linestyle=":")
    ax.text(d, 0.92, label, ha="center", fontsize=7.5, color=DIM)

# Fade zones
for start, end, sev in fade_zones:
    color = severity_color(sev)
    ax.barh(0.5, end - start, left=start, height=0.25,
            color=color, alpha=0.75)
    ax.text((start + end) / 2, 0.5, f"{sev*100:.0f}%",
            ha="center", va="center", fontsize=7.5, color="black", fontweight="bold")

# Legend
legend_elements = [
    mpatches.Patch(color=GREEN, alpha=0.75, label="Leve (<15%)"),
    mpatches.Patch(color=AMBER, alpha=0.75, label="Moderado (15–25%)"),
    mpatches.Patch(color=RED,   alpha=0.75, label="Severo (>25%)"),
]
ax.legend(handles=legend_elements, fontsize=8, loc="lower right",
          facecolor=BG_AXES, edgecolor=DIM)

ax.set_xlim(0, 3200)
ax.set_ylim(0, 1.2)
ax.set_xlabel("Distancia (m)")
ax.set_yticks([])
ax.set_title("Fig 3 — Mapa de Zonas de Fade en la Pista", fontsize=11, fontweight="bold",
             color=CYAN)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "fade_zone_map.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] fade_zone_map.png")

print("Generated images for brake_fade")
