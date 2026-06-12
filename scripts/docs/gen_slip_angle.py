"""
gen_slip_angle.py
-----------------
Generate synthetic documentation images for the Slip Angle (sideslip β) module.
All data is produced with NumPy — no telemetry files are read.
Output: docs/images/slip_angle/
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
    os.path.dirname(__file__), "..", "..", "docs", "images", "slip_angle"
)
os.makedirs(OUT_DIR, exist_ok=True)

BG_FIGURE  = "#060A14"
BG_AXES    = "#0A0F1E"
CYAN       = "#00D4FF"
RED        = "#FF3D3D"
GREEN      = "#00E676"
AMBER      = "#FFB300"
PURPLE     = "#A78BFA"
DIM        = "#4A5578"
GRID_COLOR = (1, 1, 1, 0.07)

G_MS2         = 9.80665
WHEELBASE     = 2.48
L_F           = WHEELBASE * 0.44
L_R           = WHEELBASE * 0.56
STEER_RATIO   = 14.0
OS_THRESHOLD  = 2.0
US_THRESHOLD  = 2.0


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
# Synthetic lap data
# ===========================================================================
np.random.seed(42)
N = 3200
dist = np.linspace(0, 3200, N)

# Speed: 80 km/h in corners, 180 in straights
speed_kmh = 120 + 60 * np.cos(2 * np.pi * dist / 900) + np.random.normal(0, 2, N)
speed_kmh = np.clip(speed_kmh, 40, 190)
Vx = speed_kmh / 3.6

# Lateral G: oscillates with the corners
lat_g = 0.9 * np.sin(2 * np.pi * dist / 900 + 0.2) + np.random.normal(0, 0.05, N)
lat_g = uniform_filter1d(lat_g, 20)

# Yaw rate (rad/s): steady-state approximation r = Vx * curvature
curvature = 0.006 * np.sin(2 * np.pi * dist / 900 + 0.2)
yaw_rad   = Vx * curvature + np.random.normal(0, 0.003, N)
yaw_rad   = uniform_filter1d(yaw_rad, 15)

# Steer angle
steer_deg = (lat_g * G_MS2 * L_R / (Vx**2 + 1e-3)) * np.degrees(1) * STEER_RATIO
steer_deg += np.random.normal(0, 0.3, N)
steer_deg = uniform_filter1d(steer_deg, 10)

# dt per sample (1 m / Vx)
dt = np.clip(1.0 / np.maximum(Vx, 3.0), 0, 2.0)

# Integrate beta
ay = lat_g * G_MS2
Vy_dot = ay - yaw_rad * Vx
Vy_raw = np.cumsum(Vy_dot * dt)
# Linear drift correction
drift = np.linspace(Vy_raw[0], Vy_raw[-1], N)
Vy = Vy_raw - drift

beta = np.degrees(np.arctan2(Vy, Vx))

# Wheel slip angles
delta_wheel = steer_deg / STEER_RATIO
alpha_F = delta_wheel - beta - np.degrees(yaw_rad * L_F / np.maximum(Vx, 3.0))
alpha_R =              -beta + np.degrees(yaw_rad * L_R / np.maximum(Vx, 3.0))
balance = alpha_F - alpha_R

# Second variant: oversteer character (slightly higher β, more negative balance)
beta_os     = beta     + 0.8 * np.sin(2 * np.pi * dist / 1100 + 1.2)
balance_os  = balance  - 1.2 * np.sin(2 * np.pi * dist / 1100 + 1.2)


# ===========================================================================
# Figure 1 — β Over the Lap (two-lap comparison)
# ===========================================================================
fig, ax = plt.subplots(figsize=(12, 4.5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.fill_between(dist, 0, beta,    color=CYAN,  alpha=0.20, label="β Vuelta A")
ax.plot(dist, beta,   color=CYAN, linewidth=1.5)
ax.fill_between(dist, 0, beta_os, color=RED,   alpha=0.12, label="β Vuelta B")
ax.plot(dist, beta_os, color=RED, linewidth=1.2, alpha=0.8)
ax.axhline(0, color=DIM, linewidth=0.8, linestyle="--", alpha=0.5)

# Annotate peak
peak_idx = int(np.argmax(np.abs(beta_os)))
ax.annotate(f"β pico = {beta_os[peak_idx]:.1f}°",
            xy=(dist[peak_idx], beta_os[peak_idx]),
            xytext=(dist[peak_idx] + 150, beta_os[peak_idx] + 1.5),
            arrowprops=dict(arrowstyle="->", color=RED, lw=1.1),
            color=RED, fontsize=8)

ax.set_xlabel("Distancia (m)")
ax.set_ylabel("Ángulo de Deslizamiento β (°)")
ax.set_title("Fig 1 — Sideslip β del Chasis a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "beta_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] beta_lap.png")


# ===========================================================================
# Figure 2 — Phase Diagram β vs. Yaw rate normalized
# ===========================================================================
# Normalized yaw: r * L / Vx
yaw_norm    = yaw_rad * WHEELBASE / np.maximum(Vx, 3.0)
yaw_norm_os = (yaw_rad + 0.004 * np.sin(2 * np.pi * dist / 900)) * WHEELBASE / np.maximum(Vx, 3.0)

fig, ax = plt.subplots(figsize=(7, 7))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

sc1 = ax.scatter(beta,    yaw_norm,    c=dist, cmap="cool",  s=6, alpha=0.6, label="Vuelta A")
sc2 = ax.scatter(beta_os, yaw_norm_os, c=dist, cmap="autumn", s=6, alpha=0.5, label="Vuelta B")

ax.axhline(0, color=DIM, linewidth=0.8, linestyle="--", alpha=0.5)
ax.axvline(0, color=DIM, linewidth=0.8, linestyle="--", alpha=0.5)

# Origin marker
ax.scatter([0], [0], color="white", s=80, zorder=5, marker="+")

ax.set_xlabel("Sideslip β (°)")
ax.set_ylabel("Yaw Rate Normalizado  r·L / Vx")
ax.set_title("Fig 2 — Diagrama de Fase β vs. Yaw Rate", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left", facecolor=BG_AXES, edgecolor=DIM)

# Quadrant labels
ax.text( 3.5,  0.06, "Sobreviraje\nderecha",  color=RED,  fontsize=7, alpha=0.8)
ax.text(-5.0,  0.06, "Sobreviraje\nizquierda", color=RED,  fontsize=7, alpha=0.8)
ax.text( 2.5, -0.05, "Subviraje\nderecha",    color=CYAN, fontsize=7, alpha=0.8)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "phase_diagram.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] phase_diagram.png")


# ===========================================================================
# Figure 3 — Balance αF − αR Over the Lap
# ===========================================================================
fig, ax = plt.subplots(figsize=(12, 4.5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.axhspan( US_THRESHOLD, balance.max() + 1, color=CYAN, alpha=0.07)
ax.axhspan( balance.min() - 1, -OS_THRESHOLD, color=RED,  alpha=0.07)
ax.axhline( US_THRESHOLD,  color=CYAN, linestyle="--", linewidth=1.0, alpha=0.7,
            label=f"+{US_THRESHOLD}° umbral subviraje")
ax.axhline(-OS_THRESHOLD, color=RED,  linestyle="--", linewidth=1.0, alpha=0.7,
            label=f"-{OS_THRESHOLD}° umbral sobreviraje")
ax.axhline(0, color=DIM, linewidth=0.8, linestyle=":", alpha=0.5)

ax.plot(dist, balance,    color=PURPLE, linewidth=1.5, label="Balance αF−αR Vuelta A")
ax.plot(dist, balance_os, color=AMBER,  linewidth=1.2, alpha=0.8, label="Balance αF−αR Vuelta B")

# Percentage annotations
us_pct  = (balance > US_THRESHOLD).mean() * 100
os_pct  = (balance < -OS_THRESHOLD).mean() * 100
neu_pct = 100 - us_pct - os_pct

ax.text(50, balance.max() * 0.85,
        f"Subviraje: {us_pct:.0f}%\nNeutral: {neu_pct:.0f}%\nSobreviraje: {os_pct:.0f}%",
        fontsize=8, color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=BG_AXES, edgecolor=DIM, alpha=0.9))

ax.set_xlabel("Distancia (m)")
ax.set_ylabel("Balance  αF − αR  (°)")
ax.set_title("Fig 3 — Balance de Pista αF−αR a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "balance_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] balance_lap.png")

print("Generated images for slip_angle")
