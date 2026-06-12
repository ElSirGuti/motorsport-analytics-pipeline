"""
gen_driver_inputs.py
--------------------
Generate synthetic documentation images for the Driver Inputs (FFT/nervousness) module.
All data is produced with NumPy — no telemetry files are read.
Output: docs/images/driver_inputs/
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy.signal import welch
from scipy.ndimage import uniform_filter1d
import os

# ---------------------------------------------------------------------------
# Paths and palette
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "images", "driver_inputs"
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


def _nervousness(steer, win=80):
    rate = np.abs(np.diff(steer, prepend=steer[0]))
    smoothed = uniform_filter1d(rate, size=win)
    p99 = np.percentile(smoothed, 99)
    if p99 < 1e-6:
        return np.zeros_like(steer)
    return np.clip(smoothed / p99, 0, 1)


# ===========================================================================
# Synthetic steering signals
# ===========================================================================
np.random.seed(42)
N = 3200
dist = np.linspace(0, 3200, N)

# Smooth pilot: clean inputs, large wavelengths
smooth_base = 5.0 * np.sin(2 * np.pi * dist / 800) + 3.0 * np.sin(2 * np.pi * dist / 1500)
steer_smooth = smooth_base + np.random.normal(0, 0.3, N)   # light noise

# Nervous pilot: same base + high-freq micro-corrections
micro_hf = 1.8 * np.random.normal(0, 1, N)   # high-freq component
micro_mf = 1.2 * np.sin(2 * np.pi * dist / 300 + 0.7) * np.random.normal(0, 1, N)
steer_nervous = smooth_base + micro_hf + micro_mf + np.random.normal(0, 0.4, N)

rate_smooth  = np.abs(np.diff(steer_smooth,  prepend=steer_smooth[0]))
rate_nervous = np.abs(np.diff(steer_nervous, prepend=steer_nervous[0]))

# ===========================================================================
# Figure 1 — Steer Angle and Rate comparison
# ===========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
fig.patch.set_facecolor(BG_FIGURE)

ax1.plot(dist, steer_smooth,  color=CYAN,  linewidth=1.2, label="Suave")
ax1.plot(dist, steer_nervous, color=RED,   linewidth=1.0, alpha=0.8, label="Nervioso")
ax1.set_ylabel("Steer Angle (°)")
ax1.set_title("Fig 1 — Señal de Volante: Piloto Suave vs Nervioso", fontsize=11, fontweight="bold")
ax1.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax1)

ax2.plot(dist, rate_smooth,  color=CYAN, linewidth=1.2, label="Tasa suave |Δδ|")
ax2.plot(dist, rate_nervous, color=RED,  linewidth=1.0, alpha=0.8, label="Tasa nervioso |Δδ|")
ax2.set_xlabel("Distancia (m)")
ax2.set_ylabel("|Δ Steer| por muestra (°)")
ax2.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax2)

# Annotate region of high nervousness
high_zone = (dist > 1400) & (dist < 1800)
ax2.axvspan(1400, 1800, color=AMBER, alpha=0.10)
ax2.annotate("Alta actividad\nde correcciones",
             xy=(1600, rate_nervous[np.searchsorted(dist, 1600)]),
             xytext=(1700, 3.5),
             arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.1),
             color=AMBER, fontsize=8)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "steer_rate.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] steer_rate.png")


# ===========================================================================
# Figure 2 — Welch PSD comparison
# ===========================================================================
sample_rate = 14.0  # Hz (approx at 50 km/h, 1m/sample)

freqs_s, psd_s = welch(steer_smooth,  fs=sample_rate, nperseg=512)
freqs_n, psd_n = welch(steer_nervous, fs=sample_rate, nperseg=512)

fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.semilogy(freqs_s, psd_s, color=CYAN, linewidth=2.0, label="Piloto suave")
ax.semilogy(freqs_n, psd_n, color=RED,  linewidth=2.0, label="Piloto nervioso")

# Band shading
ax.axvspan(0,    0.5, color=GREEN, alpha=0.07, label="Baja (<0.5 Hz) — trazada")
ax.axvspan(0.5,  2.0, color=AMBER, alpha=0.06, label="Media (0.5–2 Hz) — balance")
ax.axvspan(2.0,  7.0, color=RED,   alpha=0.05, label="Alta (>2 Hz) — nerviosismo")
ax.axvline(0.5, color=GREEN, linestyle="--", linewidth=1.0, alpha=0.6)
ax.axvline(2.0, color=AMBER, linestyle="--", linewidth=1.0, alpha=0.6)

ax.set_xlabel("Frecuencia (Hz)")
ax.set_ylabel("PSD (°²/Hz) — escala log")
ax.set_xlim(0, 7)
ax.set_title("Fig 2 — Densidad Espectral de Potencia (Welch PSD)", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM, ncol=1)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "fft_psd.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] fft_psd.png")


# ===========================================================================
# Figure 3 — Nervousness Index Over the Lap
# ===========================================================================
nerv_smooth  = _nervousness(steer_smooth)
nerv_nervous = _nervousness(steer_nervous)

fig, ax = plt.subplots(figsize=(12, 4))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

ax.fill_between(dist, 0, nerv_smooth * 100,  color=CYAN, alpha=0.25, label="Suave")
ax.plot(dist, nerv_smooth * 100,  color=CYAN, linewidth=1.5)
ax.fill_between(dist, 0, nerv_nervous * 100, color=RED,  alpha=0.20, label="Nervioso")
ax.plot(dist, nerv_nervous * 100, color=RED,  linewidth=1.5)

# Highlight high-nervousness zones
threshold_pct = 50
high_nerv = nerv_nervous * 100 > threshold_pct
ax.fill_between(dist, 0, nerv_nervous * 100,
                where=high_nerv, color=AMBER, alpha=0.20,
                label=f"Zona alta (>{threshold_pct}%)")

ax.set_xlabel("Distancia (m)")
ax.set_ylabel("Índice de Nerviosismo (%)")
ax.set_title("Fig 3 — Índice de Nerviosismo a lo largo de la Vuelta", fontsize=11, fontweight="bold")
ax.set_xlim(0, 3200)
ax.set_ylim(0, 110)
ax.legend(fontsize=8, loc="upper right", facecolor=BG_AXES, edgecolor=DIM)

# Score annotations
ni_s = nerv_smooth.mean() * 100
ni_n = nerv_nervous.mean() * 100
ax.text(50, 102, f"NI suave  = {ni_s:.1f}%", fontsize=8, color=CYAN)
ax.text(50,  93, f"NI nervioso = {ni_n:.1f}%", fontsize=8, color=RED)

fig.tight_layout(pad=1.0)
fig.savefig(os.path.join(OUT_DIR, "nervousness_lap.png"), dpi=150,
            bbox_inches="tight", facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] nervousness_lap.png")

print("Generated images for driver_inputs")
