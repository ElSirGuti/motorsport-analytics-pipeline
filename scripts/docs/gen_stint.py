"""
gen_stint.py — Generate synthetic documentation images for the Stint Analysis module.
Outputs 4 figures to docs/images/stint/.
All data is fully synthetic (NumPy only — no file I/O required).
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
    os.path.dirname(__file__), "..", "..", "docs", "images", "stint"
)
OUT_DIR = os.path.normpath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

plt.style.use("dark_background")

BG      = "#060A14"
AX_BG   = "#0A0F1E"
CYAN    = "#00D4FF"
RED     = "#FF3D3D"
GREEN   = "#00E676"
AMBER   = "#FFB300"
PURPLE  = "#7C3AED"
DIM     = "#4A5578"
WHITE   = "#FFFFFF"
GRID_C  = (1, 1, 1, 0.07)

DPI = 150

# ---------------------------------------------------------------------------
# Synthetic stint data
# ---------------------------------------------------------------------------
np.random.seed(42)

N_LAPS    = 18
LAP_BASE  = 98.4          # seconds — GT3 baseline lap time
BETA1     = 0.08          # degradation rate s/lap
SIGMA_OBS = 0.22          # driver lap-to-lap sigma
FUEL_CAP  = 42.0          # kg at start of stint
FUEL_MEAN = 2.31          # kg/lap mean consumption
FUEL_STD  = 0.09          # kg/lap std

lap_numbers = np.arange(1, N_LAPS + 1)

# Lap times: linear trend + noise
noise_laps  = np.random.normal(0, SIGMA_OBS, N_LAPS)
lap_times   = LAP_BASE + BETA1 * (lap_numbers - 1) + noise_laps

# Linear fit (mimicking sklearn LinearRegression)
coeffs      = np.polyfit(lap_numbers, lap_times, 1)
trend_times = np.polyval(coeffs, lap_numbers)
beta0_fit   = coeffs[1]
beta1_fit   = coeffs[0]

y_pred = trend_times
ss_res = np.sum((lap_times - y_pred) ** 2)
ss_tot = np.sum((lap_times - lap_times.mean()) ** 2)
r2     = 1.0 - ss_res / ss_tot

# 95% confidence interval band
se     = np.std(lap_times - y_pred, ddof=2) * 1.96
ci_up  = trend_times + se
ci_dn  = trend_times - se

# G-sum degradation (max_g_sum per lap)
GRIP_BASE  = 2.85
GRIP_RATE  = -0.015   # grip loss per lap (negative = losing grip)
grip_noise = np.random.normal(0, 0.04, N_LAPS)
g_sum_vals = GRIP_BASE + GRIP_RATE * (lap_numbers - 1) + grip_noise

g_coeffs   = np.polyfit(lap_numbers, g_sum_vals, 1)
g_trend    = np.polyval(g_coeffs, lap_numbers)

# Fuel per lap
fuel_burned = np.abs(np.random.normal(FUEL_MEAN, FUEL_STD, N_LAPS))
fuel_cumsum = np.cumsum(fuel_burned)
fuel_levels = FUEL_CAP - fuel_cumsum

# Conservative and optimistic fuel estimates
f_safe = FUEL_MEAN + 1.65 * FUEL_STD
f_opt  = max(0.01, FUEL_MEAN - 0.5 * FUEL_STD)
fuel_current = float(fuel_levels[-1])
vueltas_min  = int(fuel_current // f_safe)
vueltas_max  = int(fuel_current // f_opt)
pit_window_open  = N_LAPS + vueltas_min - 1
pit_window_close = N_LAPS + vueltas_max

# Monte Carlo projection
N_SIM    = 500
N_FUTURE = 12
ultimo_tiempo = lap_times[-1]
last_lap      = N_LAPS
future_laps   = np.arange(last_lap + 1, last_lap + N_FUTURE + 1)

rng_mc = np.random.default_rng(42)
sims   = np.zeros((N_SIM, N_FUTURE))
for s in range(N_SIM):
    t = ultimo_tiempo
    for k in range(N_FUTURE):
        t += beta1_fit
        eps = rng_mc.normal(0, SIGMA_OBS)
        eps = max(eps, -0.5 * SIGMA_OBS)
        sims[s, k] = t + eps

p10 = np.percentile(sims, 10, axis=0)
p25 = np.percentile(sims, 25, axis=0)
p50 = np.percentile(sims, 50, axis=0)
p75 = np.percentile(sims, 75, axis=0)
p90 = np.percentile(sims, 90, axis=0)


# ===========================================================================
# Fig 1 — degradation_regression.png
# ===========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), facecolor=BG)
fig.subplots_adjust(hspace=0.45)

for ax in (ax1, ax2):
    ax.set_facecolor(AX_BG)
    ax.grid(True, color=GRID_C, linewidth=0.6)
    ax.tick_params(colors=DIM, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)
        spine.set_linewidth(0.6)

# --- Subplot 1: lap time regression ---
ax1.fill_between(lap_numbers, ci_dn, ci_up, color=CYAN, alpha=0.10, label="95 % CI")
ax1.scatter(lap_numbers, lap_times,   color=CYAN,  s=48, zorder=5,
            edgecolors="none", label="Vuelta observada")
ax1.plot(lap_numbers, trend_times, color=WHITE, linestyle="--",
         linewidth=1.6, label=f"Regresión lineal  β₁ = {beta1_fit:+.4f} s/lap")

ax1.annotate(
    f"β₁ = {beta1_fit:+.4f} s/lap\nR² = {r2:.3f}",
    xy=(lap_numbers[-1], trend_times[-1]),
    xytext=(-3, 10), textcoords="offset points",
    color=WHITE, fontsize=8.5,
    bbox=dict(boxstyle="round,pad=0.4", fc=AX_BG, ec=DIM, lw=0.8),
)

ax1.set_xlabel("Vuelta  n", color=DIM, fontsize=9)
ax1.set_ylabel("Tiempo de vuelta [s]", color=DIM, fontsize=9)
ax1.set_title("Degradación de Neumáticos — Regresión Lineal",
              color=WHITE, fontsize=11, pad=8)
ax1.legend(fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=WHITE)
ax1.set_xlim(0.5, N_LAPS + 0.5)

# --- Subplot 2: G-sum degradation ---
ax2.scatter(lap_numbers, g_sum_vals, color=RED, s=48, zorder=5,
            edgecolors="none", label="G-sum máx. observado")
ax2.plot(lap_numbers, g_trend, color=AMBER, linestyle="--",
         linewidth=1.6, label=f"α₁ = {g_coeffs[0]:+.4f} g/lap")

ax2.set_xlabel("Vuelta  n", color=DIM, fontsize=9)
ax2.set_ylabel("G-sum máx.  [g]", color=DIM, fontsize=9)
ax2.set_title("Pérdida de Grip — G-sum por Vuelta", color=WHITE, fontsize=11, pad=8)
ax2.legend(fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=WHITE)
ax2.set_xlim(0.5, N_LAPS + 0.5)

plt.savefig(os.path.join(OUT_DIR, "degradation_regression.png"),
            dpi=DPI, bbox_inches="tight", facecolor=BG)
plt.close()


# ===========================================================================
# Fig 2 — montecarlo_projection.png
# ===========================================================================
fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
ax.set_facecolor(AX_BG)
ax.grid(True, color=GRID_C, linewidth=0.6)
ax.tick_params(colors=DIM, labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)

# Historical laps
ax.plot(lap_numbers, lap_times, color=CYAN, linewidth=1.8, zorder=5)
ax.scatter(lap_numbers, lap_times, color=CYAN, s=40, zorder=6, edgecolors="none")

# Separator
ax.axvline(last_lap + 0.5, color=DIM, linestyle=":", linewidth=1.2)
ax.text(last_lap + 0.7, lap_times.min() - 0.3, "Proyección →",
        color=DIM, fontsize=8, va="top")

# MC bands
ax.fill_between(future_laps, p10, p90, color=AMBER, alpha=0.07, label="P10 – P90")
ax.fill_between(future_laps, p25, p75, color=AMBER, alpha=0.20, label="P25 – P75")
ax.plot(future_laps, p50, color=AMBER, linestyle="--",
        linewidth=1.8, label="P50 (mediana)")

# σ_real annotation
ax.annotate(
    f"σ_real = {SIGMA_OBS:.3f} s",
    xy=(4, lap_times[3]),
    xytext=(5, 8), textcoords="offset points",
    color=WHITE, fontsize=8.5,
    bbox=dict(boxstyle="round,pad=0.4", fc=AX_BG, ec=DIM, lw=0.8),
)

ax.set_xlabel("Vuelta  n", color=DIM, fontsize=9)
ax.set_ylabel("Tiempo de vuelta [s]", color=DIM, fontsize=9)
ax.set_title("Monte Carlo — Proyección de Tiempos (500 simulaciones, seed=42)",
             color=WHITE, fontsize=11, pad=8)
ax.legend(fontsize=8.5, facecolor=BG, edgecolor=DIM, labelcolor=WHITE,
          loc="upper left")

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "montecarlo_projection.png"),
            dpi=DPI, bbox_inches="tight", facecolor=BG)
plt.close()


# ===========================================================================
# Fig 3 — fuel_consumption.png
# ===========================================================================
fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
ax.set_facecolor(AX_BG)
ax.grid(True, color=GRID_C, linewidth=0.6, axis="y")
ax.tick_params(colors=DIM, labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)

bar_colors = [GREEN if fb < FUEL_MEAN else RED for fb in fuel_burned]
ax.bar(lap_numbers, fuel_burned, color=bar_colors, alpha=0.85, width=0.7, zorder=3)

# Mean line
ax.axhline(FUEL_MEAN, color=CYAN, linewidth=1.4, linestyle="-",
           label=f"Consumo medio  μ = {FUEL_MEAN:.3f} L/lap")

# Conservative line
ax.axhline(f_safe, color=AMBER, linewidth=1.4, linestyle="--",
           label=f"Conservador (95 %)  f_safe = {f_safe:.3f} L/lap")

# Pit window annotation arrow
pit_arrow_x = pit_window_open
ax.annotate(
    f"Pit window\nabre vta {pit_arrow_x}",
    xy=(pit_arrow_x, f_safe + 0.01),
    xytext=(pit_arrow_x + 2.5, f_safe + 0.12),
    color=AMBER, fontsize=8.5,
    arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.35", fc=AX_BG, ec=AMBER, lw=0.8),
)

ax.set_xlabel("Vuelta  n", color=DIM, fontsize=9)
ax.set_ylabel("Combustible consumido [L/lap]", color=DIM, fontsize=9)
ax.set_title("Consumo de Combustible por Vuelta",
             color=WHITE, fontsize=11, pad=8)
ax.legend(fontsize=8.5, facecolor=BG, edgecolor=DIM, labelcolor=WHITE)
ax.set_xlim(0.3, N_LAPS + 0.7)

# Green/Red legend patches
legend_extra = [
    mpatches.Patch(color=GREEN, alpha=0.85, label="Por debajo de μ"),
    mpatches.Patch(color=RED,   alpha=0.85, label="Por encima de μ"),
]
ax.legend(handles=ax.get_legend().legend_handles + legend_extra,
          fontsize=8, facecolor=BG, edgecolor=DIM, labelcolor=WHITE)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "fuel_consumption.png"),
            dpi=DPI, bbox_inches="tight", facecolor=BG)
plt.close()


# ===========================================================================
# Fig 4 — pit_window_diagram.png
# ===========================================================================
total_projected_laps = pit_window_close + 3
fig, ax = plt.subplots(figsize=(13, 3.5), facecolor=BG)
ax.set_facecolor(AX_BG)
ax.tick_params(colors=DIM, labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor(DIM)
    spine.set_linewidth(0.6)
ax.set_ylim(0, 1)
ax.set_yticks([])

# Zones -----------------------------------------------------------------------
# Safe zone: 1 → pit_window_open - 1
safe_end = pit_window_open - 1
ax.barh(0.5, safe_end, left=1,        height=0.55,
        color=GREEN, alpha=0.25, zorder=2)
# Pit window: pit_window_open → pit_window_close
ax.barh(0.5, pit_window_close - pit_window_open + 1,
        left=pit_window_open, height=0.55, color=AMBER, alpha=0.35, zorder=2)
# Critical zone: pit_window_close + 1 → total
ax.barh(0.5, total_projected_laps - pit_window_close,
        left=pit_window_close + 1, height=0.55, color=RED, alpha=0.30, zorder=2)

# Zone labels
mid_safe = 1 + safe_end / 2
mid_pit  = pit_window_open + (pit_window_close - pit_window_open + 1) / 2
mid_crit = pit_window_close + 1 + (total_projected_laps - pit_window_close) / 2

ax.text(mid_safe, 0.50, "ZONA SEGURA",  ha="center", va="center",
        color=GREEN,  fontsize=9, fontweight="bold", zorder=5)
ax.text(mid_pit,  0.50, "PIT WINDOW",  ha="center", va="center",
        color=AMBER,  fontsize=9, fontweight="bold", zorder=5)
ax.text(mid_crit, 0.50, "CRITICO",     ha="center", va="center",
        color=RED,    fontsize=9, fontweight="bold", zorder=5)

# Current lap vertical line
ax.axvline(N_LAPS, color=CYAN, linewidth=2.0, linestyle="-", zorder=6)
ax.text(N_LAPS, 0.95, f"Vuelta actual\n(n={N_LAPS})",
        ha="center", va="top", color=CYAN, fontsize=8.5)

# Pit window boundary dashed lines
ax.axvline(pit_window_open,  color=AMBER, linewidth=1.2, linestyle="--", zorder=4)
ax.axvline(pit_window_close, color=RED,   linewidth=1.2, linestyle="--", zorder=4)

ax.text(pit_window_open,  0.08, f"n={pit_window_open}",
        ha="center", va="bottom", color=AMBER, fontsize=8)
ax.text(pit_window_close, 0.08, f"n={pit_window_close}",
        ha="center", va="bottom", color=RED,   fontsize=8)

# Fuel remaining label
ax.text(0.99, 0.08,
        f"Combustible actual: {fuel_current:.1f} L\n"
        f"f_safe = {f_safe:.3f} L/lap\n"
        f"Vueltas min/max: {vueltas_min}/{vueltas_max}",
        ha="right", va="bottom", transform=ax.transAxes,
        color=WHITE, fontsize=8,
        bbox=dict(boxstyle="round,pad=0.45", fc=AX_BG, ec=DIM, lw=0.7))

ax.set_xlabel("Vuelta  n", color=DIM, fontsize=9)
ax.set_title("Diagrama de Pit Window — Estrategia de Combustible",
             color=WHITE, fontsize=11, pad=8)
ax.set_xlim(0, total_projected_laps + 1)
ax.grid(True, axis="x", color=GRID_C, linewidth=0.6)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "pit_window_diagram.png"),
            dpi=DPI, bbox_inches="tight", facecolor=BG)
plt.close()


print("Generated images for stint")
