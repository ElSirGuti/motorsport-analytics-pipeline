"""
gen_geometry.py — Image generation script for geometry module documentation.

Generates synthetic visualizations for:
  - curvature_filter.png     : Raw vs Savitzky-Golay smoothed curvature signal
  - apex_detection.png       : Track map coloured by curvature with apex markers
  - corner_zones.png         : Single corner entry/apex/exit zone diagram
  - curvature_distribution.png : Histogram with corner/straight threshold line

All data is synthetic (NumPy only). No file I/O required.
Output: docs/images/geometry/
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

# ── Output directory ──────────────────────────────────────────────────────────
OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "docs", "images", "geometry"
)
os.makedirs(OUT_DIR, exist_ok=True)

# ── Style constants ───────────────────────────────────────────────────────────
BG_DARK  = "#060A14"
BG_AXES  = "#0A0F1E"
CYAN     = "#00D4FF"
RED      = "#FF3D3D"
GREEN    = "#00E676"
AMBER    = "#FFB300"
PURPLE   = "#7C3AED"
DIM      = "#4A5578"
WHITE    = "#E8EDF5"
GRID_C   = (1, 1, 1, 0.07)

matplotlib.rcParams.update({
    "figure.facecolor":  BG_DARK,
    "axes.facecolor":    BG_AXES,
    "axes.edgecolor":    DIM,
    "axes.labelcolor":   WHITE,
    "xtick.color":       DIM,
    "ytick.color":       DIM,
    "text.color":        WHITE,
    "font.family":       "monospace",
    "font.size":         9,
})

plt.style.use("dark_background")

# ─────────────────────────────────────────────────────────────────────────────
# Savitzky-Golay helper (pure NumPy) to avoid scipy dependency in the script
# ─────────────────────────────────────────────────────────────────────────────

def savgol_numpy(y, window, polyorder):
    """Minimal Savitzky-Golay via polynomial least-squares (pure NumPy)."""
    half = window // 2
    result = np.empty_like(y, dtype=float)
    for i in range(len(y)):
        lo = max(0, i - half)
        hi = min(len(y), i + half + 1)
        x_local = np.arange(lo - i, hi - i)
        coeffs = np.polyfit(x_local, y[lo:hi], polyorder)
        result[i] = np.polyval(coeffs, 0)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FIG 1 — curvature_filter.png
#   Two subplots: raw (noisy) vs SG-smoothed curvature signal over distance
# ─────────────────────────────────────────────────────────────────────────────

rng = np.random.default_rng(42)

N = 600
dist = np.linspace(0, 3000, N)   # 3 km of track

# Build a synthetic "true" curvature profile: 6 corner peaks on a near-zero baseline
true_kappa = np.zeros(N)
corners = [( 80, 0.06, 25), (195, 0.03, 18), (310, 0.08, 20),
           (415, 0.045, 22), (510, 0.07, 16), (570, 0.055, 20)]
for centre, height, sigma in corners:
    idx = int(centre / 3000 * N)
    sigma_idx = int(sigma / 3000 * N)
    true_kappa += height * np.exp(-0.5 * ((np.arange(N) - idx) / sigma_idx) ** 2)

# Add sensor noise
noise = rng.normal(0, 0.008, N)
raw_kappa = true_kappa + noise + rng.normal(0, 0.003, N) ** 2  # skewed high-freq jitter
raw_kappa = np.clip(raw_kappa, 0, None)

# Smooth with our minimal SG (window=75 pts ~ 75 m at 1 m/sample, order=2)
smooth_kappa = savgol_numpy(raw_kappa, window=75, polyorder=2)

fig, axes = plt.subplots(1, 2, figsize=(13, 4), facecolor=BG_DARK)
fig.suptitle("Filtro Savitzky-Golay — Señal de Curvatura", color=WHITE,
             fontsize=11, fontweight="bold", y=1.01)

titles = ["Raw — señal con ruido del motor de física", "Savitzky-Golay smoothed (ventana=75 m, grado=2)"]
signals = [raw_kappa, smooth_kappa]
colors  = ["#4A90D9", CYAN]
alphas  = [0.7, 1.0]

for ax, title, sig, col, alp in zip(axes, titles, signals, colors, alphas):
    ax.set_facecolor(BG_AXES)
    ax.plot(dist, sig, color=col, lw=0.9 if col != CYAN else 1.4, alpha=alp)
    ax.axhline(0.008, color=AMBER, lw=0.8, ls="--", alpha=0.6, label="κ_min = 0.008")
    ax.set_xlabel("Distancia (m)")
    ax.set_ylabel("Curvatura κ  (m⁻¹)")
    ax.set_title(title, color=WHITE, fontsize=8.5)
    ax.grid(True, color=GRID_C, linewidth=0.5)
    ax.legend(fontsize=7.5, facecolor=BG_DARK, edgecolor=DIM)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)

# Annotate SNR improvement
axes[1].annotate("Picos preservados,\njitter eliminado", xy=(1560, smooth_kappa[int(310/3000*N)]),
                 xytext=(1800, 0.065), color=GREEN, fontsize=7.5,
                 arrowprops=dict(arrowstyle="->", color=GREEN, lw=0.8))

plt.tight_layout(pad=1.5)
plt.savefig(os.path.join(OUT_DIR, "curvature_filter.png"), dpi=150, bbox_inches="tight",
            facecolor=BG_DARK)
plt.close()
print("  [1/4] curvature_filter.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 2 — apex_detection.png
#   Scatter of track positions coloured by curvature + 5 apex stars
# ─────────────────────────────────────────────────────────────────────────────

# Synthesise a vaguely oval-shaped track layout in (X, Y)
t = np.linspace(0, 2 * np.pi, N, endpoint=False)

# Parametric track: distorted ellipse with chicane
x_track = 300 * np.cos(t) + 80 * np.cos(2 * t) + 40 * np.cos(3 * t)
y_track = 200 * np.sin(t) + 60 * np.sin(2 * t) + 20 * np.sin(3 * t)

# Compute curvature from parametric derivatives
dt = t[1] - t[0]
dx_t  = np.gradient(x_track, dt)
dy_t  = np.gradient(y_track, dt)
ddx_t = np.gradient(dx_t,    dt)
ddy_t = np.gradient(dy_t,    dt)
kappa_track = np.abs(dx_t * ddy_t - dy_t * ddx_t) / (dx_t**2 + dy_t**2) ** 1.5
kappa_track = np.clip(kappa_track, 0, 0.12)

# Identify 5 apex indices (top curvature peaks)
sorted_idx = np.argsort(kappa_track)[::-1]
apex_idx = []
for idx in sorted_idx:
    if all(abs(idx - a) > 40 for a in apex_idx):
        apex_idx.append(idx)
    if len(apex_idx) == 5:
        break

fig, ax = plt.subplots(figsize=(9, 7), facecolor=BG_DARK)
ax.set_facecolor(BG_AXES)
ax.set_title("Mapa de Curvatura y Detección de Apex", color=WHITE,
             fontsize=11, fontweight="bold")

# Custom green→amber→red colormap
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list(
    "apex_cmap", [(0.0, GREEN), (0.5, AMBER), (1.0, RED)])

sc = ax.scatter(x_track, y_track, c=kappa_track, cmap=cmap, s=4, alpha=0.85,
                vmin=0, vmax=kappa_track.max())

# Apex markers
ax.scatter(x_track[apex_idx], y_track[apex_idx], marker="*",
           s=260, color="white", zorder=6, label="Apex detectado", edgecolors=AMBER, linewidths=0.6)
for rank, idx in enumerate(apex_idx, 1):
    ax.annotate(f"C{rank}", (x_track[idx], y_track[idx]),
                textcoords="offset points", xytext=(8, 5),
                color=AMBER, fontsize=7.5, fontweight="bold")

# Arrow indicating travel direction
mid = N // 3
ax.annotate("", xy=(x_track[mid + 5], y_track[mid + 5]),
            xytext=(x_track[mid], y_track[mid]),
            arrowprops=dict(arrowstyle="-|>", color=DIM, lw=1.2))

cbar = plt.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("κ  (m⁻¹)", color=WHITE)
cbar.ax.yaxis.set_tick_params(color=DIM)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=WHITE, fontsize=7.5)

ax.set_xlabel("CarCoordX  (m)")
ax.set_ylabel("CarCoordY  (m)")
ax.legend(fontsize=8, facecolor=BG_DARK, edgecolor=DIM, markerscale=0.7)
ax.grid(True, color=GRID_C, linewidth=0.5)
ax.set_aspect("equal")
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)

plt.tight_layout(pad=1.0)
plt.savefig(os.path.join(OUT_DIR, "apex_detection.png"), dpi=150, bbox_inches="tight",
            facecolor=BG_DARK)
plt.close()
print("  [2/4] apex_detection.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 3 — corner_zones.png
#   Single corner: speed (top) + curvature (bottom) with zone shading
# ─────────────────────────────────────────────────────────────────────────────

d_corner = np.linspace(0, 300, 600)   # 300 m of a single corner

# Speed profile: braking → min at apex → acceleration
v_base = 160
v_min  = 72
speed_profile = v_base - (v_base - v_min) * np.exp(-0.5 * ((d_corner - 150) / 35) ** 2)

# Curvature profile: Gaussian peak at apex
kappa_corner = 0.065 * np.exp(-0.5 * ((d_corner - 150) / 28) ** 2) + \
               0.005 * rng.standard_normal(600)
kappa_corner = np.clip(kappa_corner, 0, None)

# Zone boundaries
entry_start, apex_start, apex_end, exit_end = 80, 130, 175, 240

fig, (ax_v, ax_k) = plt.subplots(2, 1, figsize=(10, 6), facecolor=BG_DARK, sharex=True)
fig.suptitle("Zonas de Curva — Entrada / Apex / Salida", color=WHITE,
             fontsize=11, fontweight="bold")

for ax in (ax_v, ax_k):
    ax.set_facecolor(BG_AXES)
    ax.grid(True, color=GRID_C, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)
    # Zone shading
    ax.axvspan(entry_start, apex_start, color=RED,   alpha=0.10, label="Zona Entrada")
    ax.axvspan(apex_start,  apex_end,   color=AMBER, alpha=0.15, label="Zona Apex")
    ax.axvspan(apex_end,    exit_end,   color=GREEN, alpha=0.10, label="Zona Salida")

# Speed subplot
ax_v.plot(d_corner, speed_profile, color=CYAN, lw=1.8)
ax_v.set_ylabel("Velocidad  (km/h)", color=WHITE)
ax_v.set_ylim(50, 180)
v_apex_val = speed_profile[int(150 / 300 * 600)]
ax_v.axvline(150, color=AMBER, lw=0.9, ls="--", alpha=0.8)
ax_v.scatter([150], [v_apex_val], color=AMBER, s=60, zorder=5)
ax_v.annotate(f"V-Apex = {v_apex_val:.0f} km/h", xy=(150, v_apex_val),
              xytext=(175, v_apex_val + 12), color=AMBER, fontsize=8,
              arrowprops=dict(arrowstyle="->", color=AMBER, lw=0.8))

# Legend for zones (only on top subplot)
handles = [
    mpatches.Patch(color=RED,   alpha=0.5, label="Zona Entrada"),
    mpatches.Patch(color=AMBER, alpha=0.6, label="Zona Apex"),
    mpatches.Patch(color=GREEN, alpha=0.5, label="Zona Salida"),
]
ax_v.legend(handles=handles, fontsize=7.5, facecolor=BG_DARK, edgecolor=DIM, loc="upper left")

# Curvature subplot
ax_k.plot(d_corner, kappa_corner, color=CYAN, lw=1.6, alpha=0.9)
ax_k.set_ylabel("Curvatura κ  (m⁻¹)", color=WHITE)
ax_k.set_xlabel("Distancia  (m)", color=WHITE)
ax_k.axhline(0.008, color=AMBER, lw=0.8, ls=":", alpha=0.7, label="κ_min = 0.008")
ax_k.axvline(150, color=AMBER, lw=0.9, ls="--", alpha=0.8)
k_apex_val = kappa_corner[int(150 / 300 * 600)]
ax_k.scatter([150], [k_apex_val], color=AMBER, s=60, zorder=5, label=f"Apex  κ={k_apex_val:.3f}")
ax_k.legend(fontsize=7.5, facecolor=BG_DARK, edgecolor=DIM, loc="upper right")

plt.tight_layout(pad=1.2)
plt.savefig(os.path.join(OUT_DIR, "corner_zones.png"), dpi=150, bbox_inches="tight",
            facecolor=BG_DARK)
plt.close()
print("  [3/4] corner_zones.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 4 — curvature_distribution.png
#   Histogram of curvature values with threshold line separating straight/corner
# ─────────────────────────────────────────────────────────────────────────────

# Generate a realistic full-lap curvature distribution:
# ~70 % straights (low κ) + ~30 % corners (higher κ)
kappa_straights = rng.exponential(scale=0.002, size=2800)
kappa_corners   = rng.gamma(shape=3, scale=0.018, size=900) + 0.006
kappa_all = np.concatenate([kappa_straights, kappa_corners])
kappa_all = np.clip(kappa_all, 0, 0.14)

THRESHOLD = 0.008   # APEX_HEIGHT_MIN from geometry.py

fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG_DARK)
ax.set_facecolor(BG_AXES)
ax.set_title("Distribución de Curvatura — Separación Recta vs Curva", color=WHITE,
             fontsize=11, fontweight="bold")

bins = np.linspace(0, 0.14, 80)
n_straight = kappa_all[kappa_all <  THRESHOLD]
n_corner   = kappa_all[kappa_all >= THRESHOLD]

ax.hist(n_straight, bins=bins, color=GREEN,  alpha=0.55, label=f"Recta  (κ < {THRESHOLD})")
ax.hist(n_corner,   bins=bins, color=AMBER,  alpha=0.65, label=f"Curva  (κ ≥ {THRESHOLD})")

ax.axvline(THRESHOLD, color=RED, lw=1.8, ls="--",
           label=f"Umbral  κ_min = {THRESHOLD}  (APEX_HEIGHT_MIN)")

# Annotate percentages
pct_straight = 100 * len(n_straight) / len(kappa_all)
pct_corner   = 100 * len(n_corner)   / len(kappa_all)
ax.text(0.001, ax.get_ylim()[1] * 0.88 if ax.get_ylim()[1] > 0 else 100,
        f"Rectas\n{pct_straight:.0f} %", color=GREEN, fontsize=9, ha="left")
ax.text(THRESHOLD + 0.002, ax.get_ylim()[1] * 0.88 if ax.get_ylim()[1] > 0 else 100,
        f"Curvas\n{pct_corner:.0f} %", color=AMBER, fontsize=9, ha="left")

ax.set_xlabel("Curvatura κ  (m⁻¹)", color=WHITE)
ax.set_ylabel("Frecuencia  (muestras)", color=WHITE)
ax.legend(fontsize=8, facecolor=BG_DARK, edgecolor=DIM)
ax.grid(True, color=GRID_C, linewidth=0.5)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)

# Fix annotation y-position after actual render
plt.tight_layout(pad=1.0)
# Re-draw to get real ylim
fig.canvas.draw()
ylim_top = ax.get_ylim()[1]
for txt in ax.texts:
    txt.set_y(ylim_top * 0.82)

plt.savefig(os.path.join(OUT_DIR, "curvature_distribution.png"), dpi=150, bbox_inches="tight",
            facecolor=BG_DARK)
plt.close()
print("  [4/4] curvature_distribution.png")

print("Generated images for geometry")
