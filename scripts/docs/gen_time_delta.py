"""
Script de generación de imágenes para la documentación:
Módulo 02 — Alineación Espacial y Delta de Tiempo Acumulado

Todas las figuras usan datos sintéticos generados con NumPy.
Salida: docs/images/time_delta/
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

matplotlib.use("Agg")

# ---------------------------------------------------------------------------
# Constantes de estilo
# ---------------------------------------------------------------------------
BG_FIGURE = "#060A14"
BG_AXES   = "#0A0F1E"
CYAN      = "#00D4FF"
RED       = "#FF3D3D"
GREEN     = "#00E676"
AMBER     = "#FFB300"
PURPLE    = "#7C3AED"
DIM       = "#4A5578"
WHITE     = "#E8EDF5"
GRID_COLOR = (1, 1, 1, 0.07)

OUT_DIR = "c:/Users/a.gutierrez/Documents/GitHub/motorsport-analytics-pipeline/docs/images/time_delta"

plt.style.use("dark_background")


def apply_base_style(fig, axes):
    """Aplica fondo y grilla estándar a figura y lista de ejes."""
    fig.patch.set_facecolor(BG_FIGURE)
    for ax in axes:
        ax.set_facecolor(BG_AXES)
        ax.grid(True, color=GRID_COLOR, linewidth=0.6)
        ax.tick_params(colors=DIM, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(DIM)
            spine.set_linewidth(0.5)


# ---------------------------------------------------------------------------
# Figura 1 — alignment_diagram.png
# Dos trazas de velocidad: eje tiempo (izquierda) → eje distancia (derecha)
# ---------------------------------------------------------------------------

rng = np.random.default_rng(42)

# Vuelta rápida: tiempo 0–90 s, vuelta lenta: 0–92 s
t_fast = np.linspace(0, 90, 1800)
t_slow = np.linspace(0, 92, 1840)

def synthetic_speed_time(t_arr, scale=1.0):
    """Perfil de velocidad sintético sobre eje temporal."""
    n = len(t_arr)
    t_norm = t_arr / t_arr[-1]
    base = 220 + 80 * np.sin(2 * np.pi * t_norm * 3) - 100 * np.abs(np.sin(2 * np.pi * t_norm * 3 + 0.4))
    noise = rng.normal(0, 3, n)
    return np.clip(base * scale + noise, 40, 330)

spd_fast_t = synthetic_speed_time(t_fast, 1.0)
spd_slow_t = synthetic_speed_time(t_slow, 0.96)

# Distância acumulada integrando velocidad
def integrate_distance(t, speed_kmh):
    speed_ms = speed_kmh / 3.6
    dt = np.diff(t, prepend=t[0])
    return np.cumsum(speed_ms * dt)

dist_fast = integrate_distance(t_fast, spd_fast_t)
dist_slow = integrate_distance(t_slow, spd_slow_t)

# Re-muestrear al eje de distancia uniforme
max_dist_shared = min(dist_fast[-1], dist_slow[-1])
dist_uniform = np.arange(0, max_dist_shared, 10.0)  # 10 m step

spd_fast_d = np.interp(dist_uniform, dist_fast, spd_fast_t)
spd_slow_d = np.interp(dist_uniform, dist_slow, spd_slow_t)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
apply_base_style(fig, [ax1, ax2])
fig.suptitle("Alineación de Trazas al Eje de Distancia", color=WHITE,
             fontsize=13, fontweight="bold", y=1.01)

# --- Panel izquierdo: dominio temporal ---
ax1.plot(t_fast, spd_fast_t, color=CYAN,  lw=1.4, label="Vuelta rápida (ref.)")
ax1.plot(t_slow, spd_slow_t, color=AMBER, lw=1.4, label="Vuelta comparada", alpha=0.85)

# Flecha mostrando el desfase
mid_t = 45
mid_f = np.interp(mid_t, t_fast, spd_fast_t)
mid_s = np.interp(mid_t * (90/92), t_slow, spd_slow_t)
ax1.annotate(
    "", xy=(mid_t + 2.5, mid_s + 18), xytext=(mid_t - 2.5, mid_f + 18),
    arrowprops=dict(arrowstyle="<->", color=RED, lw=1.5)
)
ax1.text(mid_t, mid_f + 28, "desfase\ntemporal", color=RED, ha="center",
         fontsize=7.5, fontstyle="italic")

ax1.set_xlabel("Tiempo (s)", color=WHITE, fontsize=9)
ax1.set_ylabel("Velocidad (km/h)", color=WHITE, fontsize=9)
ax1.set_title("Dominio temporal — señales desfasadas", color=DIM, fontsize=9)
ax1.legend(fontsize=8, framealpha=0.3, loc="lower right")

# --- Panel derecho: dominio distancia ---
ax2.plot(dist_uniform / 1000, spd_fast_d, color=CYAN,  lw=1.4, label="Vuelta rápida (ref.)")
ax2.plot(dist_uniform / 1000, spd_slow_d, color=AMBER, lw=1.4, label="Vuelta comparada", alpha=0.85)

mid_d_km = 1.8
mid_fd = np.interp(mid_d_km * 1000, dist_uniform, spd_fast_d)
ax2.annotate(
    "Alineadas\nen distancia",
    xy=(mid_d_km, mid_fd - 25),
    xytext=(mid_d_km + 0.5, mid_fd - 75),
    arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2),
    color=GREEN, fontsize=8
)

ax2.set_xlabel("Distancia (km)", color=WHITE, fontsize=9)
ax2.set_ylabel("Velocidad (km/h)", color=WHITE, fontsize=9)
ax2.set_title("Dominio distancia — señales alineadas", color=DIM, fontsize=9)
ax2.legend(fontsize=8, framealpha=0.3, loc="lower right")

plt.tight_layout(pad=1.5)
fig.savefig(f"{OUT_DIR}/alignment_diagram.png", dpi=150, bbox_inches="tight",
            facecolor=BG_FIGURE)
plt.close(fig)


# ---------------------------------------------------------------------------
# Figura 2 — time_delta.png
# Delta de tiempo acumulado con relleno verde/rojo y líneas de sector
# ---------------------------------------------------------------------------

# Calcular delta real desde los datos sintéticos
v_fast_ms = np.clip(spd_fast_d / 3.6, 1.0, None)
v_slow_ms = np.clip(spd_slow_d / 3.6, 1.0, None)
delta_t    = np.cumsum((1.0 / v_slow_ms - 1.0 / v_fast_ms) * 10.0)  # Δs = 10 m

# Sector boundaries (a ~1/3 y 2/3 del circuito)
n = len(dist_uniform)
s1_dist = dist_uniform[n // 3]
s2_dist = dist_uniform[2 * n // 3]
sector_dists_km = [s1_dist / 1000, s2_dist / 1000]

fig, ax = plt.subplots(figsize=(11, 4.5))
apply_base_style(fig, [ax])
fig.patch.set_facecolor(BG_FIGURE)

dist_km = dist_uniform / 1000
zero_line = np.zeros_like(delta_t)

# Rellenar verde donde delta < 0 (vuelta rápida gana) y rojo donde delta > 0
ax.fill_between(dist_km, zero_line, delta_t, where=(delta_t >= 0),
                color=RED, alpha=0.35, label="Vuelta lenta pierde tiempo")
ax.fill_between(dist_km, zero_line, delta_t, where=(delta_t < 0),
                color=GREEN, alpha=0.35, label="Vuelta lenta gana tiempo")
ax.plot(dist_km, delta_t, color=CYAN, lw=1.6, zorder=5)
ax.axhline(0, color=WHITE, lw=0.7, linestyle="--", alpha=0.4)

# Líneas de sector
for sd_km in sector_dists_km:
    ax.axvline(sd_km, color=AMBER, lw=1.0, linestyle="--", alpha=0.7)
    ax.text(sd_km + 0.02, ax.get_ylim()[1] if ax.get_ylim()[1] != 1 else delta_t.max() * 0.9,
            "sector", color=AMBER, fontsize=7, va="top", rotation=90, alpha=0.8)

# Anotaciones de texto
y_max = delta_t.max()
y_min = delta_t.min()
y_range = y_max - y_min

mid_x = dist_km[n // 2]
ax.text(dist_km[n // 6], y_max * 0.6,
        "Vuelta lenta\npíerde tiempo", color=RED, fontsize=8,
        ha="center", fontstyle="italic",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=BG_AXES, edgecolor=RED, alpha=0.6))

ax.text(dist_km[5 * n // 6], y_min * 0.5 if y_min < 0 else y_max * 0.3,
        "Vuelta rápida\ngana tiempo", color=GREEN, fontsize=8,
        ha="center", fontstyle="italic",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=BG_AXES, edgecolor=GREEN, alpha=0.6))

ax.set_xlabel("Distancia (km)", color=WHITE, fontsize=10)
ax.set_ylabel("Δt acumulado (s)", color=WHITE, fontsize=10)
ax.set_title("Time Delta Acumulado  —  ΔT(d) = Σ (1/v_slow − 1/v_fast) · Δd",
             color=WHITE, fontsize=11, fontweight="bold")

handles = [
    Line2D([0], [0], color=CYAN, lw=2, label="ΔT acumulado"),
    mpatches.Patch(color=RED,   alpha=0.5, label="Vuelta lenta pierde tiempo"),
    mpatches.Patch(color=GREEN, alpha=0.5, label="Vuelta lenta gana tiempo"),
    Line2D([0], [0], color=AMBER, lw=1, linestyle="--", label="Límite de sector"),
]
ax.legend(handles=handles, fontsize=8, framealpha=0.3, loc="upper left")

plt.tight_layout(pad=1.2)
fig.savefig(f"{OUT_DIR}/time_delta.png", dpi=150, bbox_inches="tight",
            facecolor=BG_FIGURE)
plt.close(fig)


# ---------------------------------------------------------------------------
# Figura 3 — rdp_compression.png
# Puntos originales (tenues) vs puntos RDP-comprimidos (brillantes)
# ---------------------------------------------------------------------------

def rdp_compress(points, epsilon):
    """
    Ramer-Douglas-Peucker recursivo simplificado.
    points: array (N, 2)  [x, y]
    Retorna: array de índices a conservar.
    """
    if len(points) < 3:
        return list(range(len(points)))

    start, end = points[0], points[-1]
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)

    if line_len == 0:
        dists = np.linalg.norm(points - start, axis=1)
    else:
        line_unit = line_vec / line_len
        vecs = points - start
        proj = np.dot(vecs, line_unit)
        perp = vecs - np.outer(proj, line_unit)
        dists = np.linalg.norm(perp, axis=1)

    idx_max = np.argmax(dists)
    max_dist = dists[idx_max]

    if max_dist > epsilon:
        left  = rdp_compress(points[:idx_max + 1], epsilon)
        right = rdp_compress(points[idx_max:], epsilon)
        # right indices are relative to points[idx_max:]
        return left[:-1] + [idx_max + r for r in right]
    else:
        return [0, len(points) - 1]


# Señal de referencia: delta_t sobre distancia, ~400 puntos
n_orig = 400
idx_sample = np.linspace(0, len(dist_uniform) - 1, n_orig, dtype=int)
x_orig = dist_uniform[idx_sample] / 1000
y_orig = delta_t[idx_sample]

pts = np.column_stack([x_orig, y_orig])
epsilon = 0.05  # segundos — umbral RDP típico

kept_idx = rdp_compress(pts, epsilon)
x_rdp = x_orig[kept_idx]
y_rdp = y_orig[kept_idx]

fig, ax = plt.subplots(figsize=(11, 4.5))
apply_base_style(fig, [ax])
fig.patch.set_facecolor(BG_FIGURE)

# Puntos originales (tenues)
ax.scatter(x_orig, y_orig, s=6, color=DIM, alpha=0.5, zorder=2, label=f"Original ({n_orig} puntos)")
ax.plot(x_orig, y_orig, color=DIM, lw=0.5, alpha=0.3, zorder=1)

# Puntos RDP comprimidos
ax.plot(x_rdp, y_rdp, color=CYAN, lw=1.6, zorder=4, label=f"RDP comprimido ({len(kept_idx)} puntos)")
ax.scatter(x_rdp, y_rdp, s=30, color=CYAN, zorder=5, edgecolors=WHITE, linewidths=0.5)

# Anotar reducción
reduction_pct = (1 - len(kept_idx) / n_orig) * 100
ax.text(
    0.98, 0.95,
    f"Reducción: {reduction_pct:.0f}%\n{n_orig} → {len(kept_idx)} puntos\nε = {epsilon} s",
    transform=ax.transAxes, ha="right", va="top",
    color=WHITE, fontsize=9,
    bbox=dict(boxstyle="round,pad=0.4", facecolor=BG_AXES, edgecolor=PURPLE, alpha=0.8)
)

ax.axhline(0, color=WHITE, lw=0.6, linestyle="--", alpha=0.3)
ax.set_xlabel("Distancia (km)", color=WHITE, fontsize=10)
ax.set_ylabel("Δt acumulado (s)", color=WHITE, fontsize=10)
ax.set_title(
    "Compresión RDP (Ramer-Douglas-Peucker)  —  Reducción de puntos para transmisión",
    color=WHITE, fontsize=11, fontweight="bold"
)
ax.legend(fontsize=9, framealpha=0.3, loc="upper left")

plt.tight_layout(pad=1.2)
fig.savefig(f"{OUT_DIR}/rdp_compression.png", dpi=150, bbox_inches="tight",
            facecolor=BG_FIGURE)
plt.close(fig)


print("Generated images for time_delta")
