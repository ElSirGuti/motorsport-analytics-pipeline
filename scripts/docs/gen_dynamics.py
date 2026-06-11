"""
gen_dynamics.py
---------------
Generate synthetic diagnostic images for the dynamics module documentation.
All data is generated with NumPy — no file reading required.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
plt.style.use('dark_background')

BG_FIGURE  = '#060A14'
BG_AXES    = '#0A0F1E'
CYAN       = '#00D4FF'
RED        = '#FF3D3D'
GREEN      = '#00E676'
AMBER      = '#FFB300'
PURPLE     = '#7C3AED'
DIM        = '#4A5578'
GRID_COLOR = (1, 1, 1, 0.07)

OUTPUT_DIR = "c:/Users/a.gutierrez/Documents/GitHub/motorsport-analytics-pipeline/docs/images/dynamics"


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
# Figure 1 — Understeer Detection
# ===========================================================================
np.random.seed(42)
n = 300
t = np.linspace(0, 10, n)

# Steer angle: ramp up strongly mid-section (driver sawing at wheel)
steer = np.zeros(n)
steer[:80]  = np.linspace(0, 4, 80)
steer[80:160] = np.linspace(4, 12, 80) + np.random.normal(0, 0.3, 80)  # rapid increase
steer[160:220] = np.linspace(12, 14, 60) + np.random.normal(0, 0.3, 60)
steer[220:] = np.linspace(14, 2, 80) + np.random.normal(0, 0.3, 80)

# Lateral G: barely responds when steer is rising fast (understeer zone)
lat_g = np.zeros(n)
lat_g[:80]   = np.linspace(0, 0.6, 80)
lat_g[80:160] = np.linspace(0.6, 0.75, 80) + np.random.normal(0, 0.02, 80)  # FLAT despite steer rise
lat_g[160:220] = np.linspace(0.75, 0.8, 60) + np.random.normal(0, 0.02, 60)
lat_g[220:]  = np.linspace(0.8, 0.1, 80) + np.random.normal(0, 0.02, 80)

# Smooth
from scipy.ndimage import uniform_filter1d
steer  = uniform_filter1d(steer, size=7)
lat_g  = uniform_filter1d(lat_g, size=7)

UNDERSTEER_START, UNDERSTEER_END = 80, 160

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
fig.patch.set_facecolor(BG_FIGURE)

# --- top: steer angle ---
ax1.plot(t, steer, color=CYAN, linewidth=1.5, label='Steer Angle (°)')
ax1.axhline(8,  color=AMBER, linestyle='--', linewidth=1.0, alpha=0.8, label='Umbral media 8°')
ax1.axhline(15, color=RED,   linestyle='--', linewidth=1.0, alpha=0.8, label='Umbral crítico 15°')
ax1.axvspan(t[UNDERSTEER_START], t[UNDERSTEER_END], color=RED, alpha=0.12, label='Zona subviraje')
ax1.set_ylabel('Steer Angle (°)')
ax1.set_title('Fig 1 — Detección de Subviraje', fontsize=11, fontweight='bold')
ax1.legend(fontsize=7, loc='upper right', facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax1)

# steer rate annotation
mid = (UNDERSTEER_START + UNDERSTEER_END) // 2
ax1.annotate(
    'Δsteer_rate > 0.3 rad/s\n(subviraje media)',
    xy=(t[mid], steer[mid]),
    xytext=(t[mid] + 1.0, steer[mid] + 2.0),
    arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2),
    color=AMBER, fontsize=8,
)

# --- bottom: lateral G ---
ax2.plot(t, lat_g, color=GREEN, linewidth=1.5, label='Lateral G (g)')
ax2.axhline(0.8, color=CYAN, linestyle='--', linewidth=1.0, alpha=0.8, label='G_expected(v, κ) ≈ 0.80 g')
ax2.axvspan(t[UNDERSTEER_START], t[UNDERSTEER_END], color=RED, alpha=0.12, label='G_lat < G_expected')
ax2.set_xlabel('Tiempo (s)')
ax2.set_ylabel('Lateral G (g)')
ax2.legend(fontsize=7, loc='upper right', facecolor=BG_AXES, edgecolor=DIM)
ax2.annotate(
    'G_lat plano: eje delantero\nsaturado',
    xy=(t[mid], lat_g[mid]),
    xytext=(t[mid] + 1.0, lat_g[mid] - 0.15),
    arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2),
    color=GREEN, fontsize=8,
)
apply_ax_style(ax2)

fig.tight_layout(pad=1.0)
fig.savefig(f"{OUTPUT_DIR}/understeer_detection.png", dpi=150, bbox_inches='tight',
            facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] understeer_detection.png")


# ===========================================================================
# Figure 2 — Oversteer Detection
# ===========================================================================
np.random.seed(7)
n = 300
t = np.linspace(0, 10, n)

# Smooth lateral G with sudden spike (oversteer: rear breaks away)
lat_g2 = np.zeros(n)
lat_g2[:100] = np.linspace(0, 0.9, 100)
lat_g2[100:130] = np.linspace(0.9, 1.8, 30)   # snap oversteer — sharp rise
lat_g2[130:160] = np.linspace(1.8, 0.7, 30)   # correction
lat_g2[160:220] = np.linspace(0.7, 0.3, 60)
lat_g2[220:]    = np.linspace(0.3, 0.0, 80)
lat_g2 += np.random.normal(0, 0.02, n)
lat_g2 = uniform_filter1d(lat_g2, size=5)

# Lateral jerk = |d(lat_g)/dt|
lat_jerk2 = np.abs(np.gradient(lat_g2, t))

OVERSTEER_START, OVERSTEER_END = 98, 145

# Severity thresholds (umbral_over = 0.5 g/s, from code)
umbral_over = 0.5
thr_leve    = umbral_over * 1.0
thr_media   = umbral_over * 1.5
thr_critico = umbral_over * 2.5

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
fig.patch.set_facecolor(BG_FIGURE)

ax1.plot(t, lat_g2, color=CYAN, linewidth=1.5, label='Lateral G (g)')
ax1.axvspan(t[OVERSTEER_START], t[OVERSTEER_END], color=RED, alpha=0.14, label='Evento sobreviraje')
ax1.set_ylabel('Lateral G (g)')
ax1.set_title('Fig 2 — Detección de Sobreviraje', fontsize=11, fontweight='bold')
ax1.legend(fontsize=7, loc='upper right', facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax1)

# lateral jerk
ax2.plot(t, lat_jerk2, color=AMBER, linewidth=1.5, label='|dG_lat/dt|  (g/s)')
ax2.axhline(thr_leve,    color=GREEN,  linestyle='--', linewidth=1.0, label=f'Leve    ≥ {thr_leve:.2f} g/s')
ax2.axhline(thr_media,   color=AMBER,  linestyle='--', linewidth=1.0, label=f'Media   ≥ {thr_media:.2f} g/s')
ax2.axhline(thr_critico, color=RED,    linestyle='--', linewidth=1.0, label=f'Crítico ≥ {thr_critico:.2f} g/s')
ax2.axvspan(t[OVERSTEER_START], t[OVERSTEER_END], color=RED, alpha=0.10)
ax2.set_xlabel('Tiempo (s)')
ax2.set_ylabel('Lateral Jerk (g/s)')

peak_idx = int(np.argmax(lat_jerk2[OVERSTEER_START:OVERSTEER_END])) + OVERSTEER_START
ax2.annotate(
    f'Jerk pico = {lat_jerk2[peak_idx]:.2f} g/s\n→ Sobreviraje crítico',
    xy=(t[peak_idx], lat_jerk2[peak_idx]),
    xytext=(t[peak_idx] + 0.8, lat_jerk2[peak_idx] + 0.04),
    arrowprops=dict(arrowstyle='->', color=RED, lw=1.2),
    color=RED, fontsize=8,
)
ax2.legend(fontsize=7, loc='upper right', facecolor=BG_AXES, edgecolor=DIM)
apply_ax_style(ax2)

fig.tight_layout(pad=1.0)
fig.savefig(f"{OUTPUT_DIR}/oversteer_detection.png", dpi=150, bbox_inches='tight',
            facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] oversteer_detection.png")


# ===========================================================================
# Figure 3 — Severity Scatter Diagram
# ===========================================================================
np.random.seed(99)

N_US = 60   # understeer events
N_OS = 50   # oversteer events

# Understeer: steer_rate 0.1–0.8, low lat_jerk_normalized
us_steer_rate = np.random.uniform(0.08, 0.80, N_US)
us_lat_jerk   = np.random.uniform(0.0,  0.35, N_US)
# Oversteer: low steer_rate, high lat_jerk_normalized
os_steer_rate = np.random.uniform(0.0,  0.30, N_OS)
os_lat_jerk   = np.random.uniform(0.30, 1.05, N_OS)

def severity_us(sr):
    if sr >= 0.6:
        return "critico"
    elif sr >= 0.3:
        return "media"
    return "leve"

def severity_os(lj):
    if lj >= 0.75:   # 2.5 * 0.3 normalised
        return "critico"
    elif lj >= 0.45: # 1.5 * 0.3
        return "media"
    return "leve"

sev_size = {"leve": 40, "media": 100, "critico": 220}
sev_alpha = {"leve": 0.5, "media": 0.70, "critico": 0.90}

fig, ax = plt.subplots(figsize=(9, 7))
fig.patch.set_facecolor(BG_FIGURE)
apply_ax_style(ax)

# Plot understeer events
for sr, lj in zip(us_steer_rate, us_lat_jerk):
    sev = severity_us(sr)
    ax.scatter(sr, lj, s=sev_size[sev], color=CYAN, alpha=sev_alpha[sev],
               edgecolors='none', zorder=3)

# Plot oversteer events
for sr, lj in zip(os_steer_rate, os_lat_jerk):
    sev = severity_os(lj)
    ax.scatter(sr, lj, s=sev_size[sev], color=RED, alpha=sev_alpha[sev],
               edgecolors='none', zorder=3)

# Quadrant boundary lines
ax.axvline(0.30, color=AMBER, linestyle='--', linewidth=1.0, alpha=0.7)
ax.axhline(0.30, color=AMBER, linestyle='--', linewidth=1.0, alpha=0.7)

# Severity threshold lines
ax.axvline(0.10, color=GREEN,  linestyle=':', linewidth=0.8, alpha=0.6, label='sub leve  = 0.1 rad/s')
ax.axvline(0.30, color=AMBER,  linestyle=':', linewidth=0.8, alpha=0.6)
ax.axvline(0.60, color=RED,    linestyle=':', linewidth=0.8, alpha=0.6)
ax.axhline(0.30, color=GREEN,  linestyle=':', linewidth=0.8, alpha=0.6, label='over leve  = 0.30')
ax.axhline(0.45, color=AMBER,  linestyle=':', linewidth=0.8, alpha=0.6)
ax.axhline(0.75, color=RED,    linestyle=':', linewidth=0.8, alpha=0.6)

# Quadrant labels
ax.text(0.62, 0.08, 'SUBVIRAJE\nDOMINANTE', color=CYAN,  fontsize=9, fontweight='bold', alpha=0.8)
ax.text(0.02, 0.82, 'SOBREVIRAJE\nDOMINANTE', color=RED,   fontsize=9, fontweight='bold', alpha=0.8)
ax.text(0.38, 0.75, 'MIXTO\nINESTABLE',       color=AMBER, fontsize=8, alpha=0.7)
ax.text(0.02, 0.06, 'ZONA\nNEUTRA',            color=GREEN, fontsize=8, alpha=0.7)

# Legend
legend_elements = [
    mpatches.Patch(facecolor=CYAN, alpha=0.75, label='Subviraje'),
    mpatches.Patch(facecolor=RED,  alpha=0.75, label='Sobreviraje'),
    Line2D([0], [0], marker='o', color='none', markerfacecolor='white', markersize=5,
           label='Leve  (s=40)',  alpha=0.5),
    Line2D([0], [0], marker='o', color='none', markerfacecolor='white', markersize=8,
           label='Media (s=100)', alpha=0.7),
    Line2D([0], [0], marker='o', color='none', markerfacecolor='white', markersize=12,
           label='Crítico (s=220)', alpha=0.9),
]
ax.legend(handles=legend_elements, fontsize=8, loc='upper right',
          facecolor=BG_AXES, edgecolor=DIM)

ax.set_xlabel('Steer Rate  (rad/s · sample⁻¹)', fontsize=10)
ax.set_ylabel('Lat Jerk Normalizado  (|ΔG_lat| / umbral_over)', fontsize=10)
ax.set_title('Fig 3 — Diagrama de Severidad: Subviraje vs Sobreviraje', fontsize=11, fontweight='bold')
ax.set_xlim(-0.02, 0.88)
ax.set_ylim(-0.03, 1.10)

fig.tight_layout(pad=1.2)
fig.savefig(f"{OUTPUT_DIR}/severity_diagram.png", dpi=150, bbox_inches='tight',
            facecolor=BG_FIGURE)
plt.close(fig)
print("  [OK] severity_diagram.png")

print("Generated images for dynamics")
