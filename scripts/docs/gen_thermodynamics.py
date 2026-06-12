"""
gen_thermodynamics.py
---------------------
Generate synthetic documentation images for the Tire Thermodynamics module.
All data is produced with NumPy — no telemetry files are read.
Output: docs/images/thermodynamics/
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import os

# ---------------------------------------------------------------------------
# Paths and palette
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "images", "thermodynamics"
)
os.makedirs(OUT_DIR, exist_ok=True)

BG_FIGURE  = "#060A14"
BG_AXES    = "#0A0F1E"
CYAN       = "#00D4FF"
RED        = "#FF3D3D"
GREEN      = "#00E676"
AMBER      = "#FFB300"
PURPLE     = "#7C3AED"
BLUE       = "#4FC3F7"
DIM        = "#4A5578"
GRID_COLOR = (1, 1, 1, 0.07)

CORNERS    = ["FL", "FR", "RL", "RR"]
CORNER_LABELS = ["Del. Izq.", "Del. Der.", "Tra. Izq.", "Tra. Der."]
ZONES      = ["Inner", "Middle", "Outer", "Core"]

STATUS_COLORS = {
    "fria":          "#4FC3F7",
    "suboptima":     "#29B6F6",
    "optima":        "#00E676",
    "caliente":      "#FFB300",
    "sobrecalentada": "#FF3D3D",
}

T_MIN, T_MAX = 80, 100


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
# Figure 1 — Thermal Window and Status
# ===========================================================================
np.random.seed(42)

# Synthetic mean temperatures per corner (°C) — one vuelta A, one vuelta B
temps_A = np.array([76.0, 78.0, 95.0, 103.0])   # FL frío, FR subóptimo, RL óptimo, RR caliente
temps_B = np.array([84.0, 86.0, 92.0, 88.0])     # todos en ventana óptima
stds_A  = np.array([3.0,  2.5,  4.0,  5.0])
stds_B  = np.array([2.0,  2.0,  3.0,  2.5])

def get_status(t):
    if t < T_MIN - 15: return "fria"
    if t < T_MIN:      return "suboptima"
    if t <= T_MAX:     return "optima"
    if t <= T_MAX + 15: return "caliente"
    return "sobrecalentada"

fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

x = np.arange(len(CORNERS))
width = 0.35

bars_A = ax.bar(x - width/2, temps_A, width, yerr=stds_A,
                color=[STATUS_COLORS[get_status(t)] for t in temps_A],
                alpha=0.85, capsize=4, label="Vuelta A")
bars_B = ax.bar(x + width/2, temps_B, width, yerr=stds_B,
                color=[STATUS_COLORS[get_status(t)] for t in temps_B],
                alpha=0.50, capsize=4, label="Vuelta B", hatch="//",
                edgecolor="white", linewidth=0.5)

# Optimal window shading
ax.axhspan(T_MIN, T_MAX, color=GREEN, alpha=0.06, label=f"Ventana óptima {T_MIN}–{T_MAX}°C")
ax.axhline(T_MIN, color=GREEN, linestyle="--", linewidth=1.0, alpha=0.6)
ax.axhline(T_MAX, color=AMBER, linestyle="--", linewidth=1.0, alpha=0.6)

ax.set_xticks(x)
ax.set_xticklabels(CORNER_LABELS, fontsize=9)
ax.set_ylabel("Temperatura Superficial Media (°C)")
ax.set_ylim(55, 125)
ax.set_title("Fig 1 — Ventana Térmica de Neumáticos por Corner", fontsize=11, fontweight="bold")

# Status legend
status_patches = [
    mpatches.Patch(color=STATUS_COLORS["fria"],          label="Fría"),
    mpatches.Patch(color=STATUS_COLORS["suboptima"],     label="Subóptima"),
    mpatches.Patch(color=STATUS_COLORS["optima"],        label="Óptima"),
    mpatches.Patch(color=STATUS_COLORS["caliente"],      label="Caliente"),
    mpatches.Patch(color=STATUS_COLORS["sobrecalentada"],label="Sobrecalentada"),
]
ax.legend(handles=status_patches + [
    mpatches.Patch(color="none", label=""),
    mpatches.Patch(facecolor=DIM, alpha=0.85, label="Vuelta A"),
    mpatches.Patch(facecolor=DIM, alpha=0.50, hatch="//", edgecolor="white", label="Vuelta B"),
], fontsize=7, loc="upper left", facecolor=BG_AXES, edgecolor=DIM, ncol=2)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "thermal_window.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] thermal_window.png")


# ===========================================================================
# Figure 2 — ΔT Over the Lap
# ===========================================================================
np.random.seed(7)
dist = np.linspace(0, 3200, 400)
t_base = 92 + 6 * np.sin(np.linspace(0, 4 * np.pi, 400))

# 4 corners with different ΔT profiles
delta_FL = 12 + 4 * np.sin(dist / 500) + np.random.normal(0, 1.5, 400)
delta_FR = 10 + 6 * np.sin(dist / 400 + 0.5) + np.random.normal(0, 1.5, 400)
delta_RL = 18 + 8 * np.sin(dist / 600 + 1.0) + np.random.normal(0, 2.0, 400)
delta_RR = 22 + 10 * np.sin(dist / 700 + 1.5) + np.random.normal(0, 2.5, 400)

CORNER_COLORS = [CYAN, "#FF6B6B", "#FFD93D", "#6BCB77"]

fig, ax = plt.subplots(figsize=(12, 4.5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.axhspan(20, max(delta_RR) + 5, color=RED, alpha=0.07, label="Zona de estrés (ΔT > 20°C)")
ax.axhline(20, color=RED, linestyle="--", linewidth=1.2, alpha=0.7)

for delta, label, color in zip(
    [delta_FL, delta_FR, delta_RL, delta_RR],
    CORNER_LABELS, CORNER_COLORS
):
    ax.plot(dist, delta, color=color, linewidth=1.2, label=label, alpha=0.9)

ax.fill_between(dist, 0, delta_RR,
                where=(delta_RR > 20), color=RED, alpha=0.15)

ax.set_xlabel("Distancia (m)")
ax.set_ylabel("ΔT Superficie − Núcleo (°C)")
ax.set_title("Fig 2 — Gradiente ΔT a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax.set_xlim(0, 3200)
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "delta_t_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] delta_t_lap.png")


# ===========================================================================
# Figure 3 — Zone Heatmap (4 corners × 4 zones)
# ===========================================================================
np.random.seed(99)

# Temperature matrix [corner × zone]: FL, FR, RL, RR × Inner, Middle, Outer, Core
temps_matrix = np.array([
    [74.0, 76.0, 79.0, 72.0],   # FL — frío
    [82.0, 84.0, 86.0, 80.0],   # FR — óptimo
    [94.0, 96.0, 93.0, 91.0],   # RL — óptimo / caliente
    [108.0, 105.0, 101.0, 98.0], # RR — caliente / sobrecalentado
])

# Custom colormap: blue (cold) → green (optimal) → red (hot)
colors_cmap = [(0.1, 0.6, 1.0), (0.0, 0.9, 0.47), (1.0, 0.7, 0.0), (1.0, 0.24, 0.24)]
cmap_positions = [0.0, 0.35, 0.65, 1.0]
cmap = LinearSegmentedColormap.from_list(
    "tyre_thermal",
    list(zip(cmap_positions, colors_cmap))
)

fig, ax = plt.subplots(figsize=(8, 5))
fig.patch.set_facecolor(BG_FIGURE)
ax.set_facecolor(BG_AXES)

im = ax.imshow(temps_matrix, cmap=cmap, vmin=60, vmax=115, aspect="auto")

# Annotate cells
for i in range(4):
    for j in range(4):
        t = temps_matrix[i, j]
        text_color = "black" if 78 < t < 102 else "white"
        ax.text(j, i, f"{t:.0f}°C", ha="center", va="center",
                fontsize=9, color=text_color, fontweight="bold")

ax.set_xticks(range(4))
ax.set_xticklabels(ZONES, fontsize=9)
ax.set_yticks(range(4))
ax.set_yticklabels(CORNER_LABELS, fontsize=9)
ax.tick_params(colors=DIM)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label("Temperatura (°C)", color=DIM, fontsize=9)
cbar.ax.yaxis.set_tick_params(color=DIM, labelsize=8)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=DIM)

# Mark optimal band
for pos in [T_MIN, T_MAX]:
    ax.axhline(pos / 55 * 3 - 0.5, color=GREEN, linewidth=0, alpha=0)  # dummy

ax.set_title("Fig 3 — Mapa de Calor de Temperatura por Zona", fontsize=11, fontweight="bold",
             color=CYAN)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "zone_heatmap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] zone_heatmap.png")

print("Generated images for thermodynamics")
