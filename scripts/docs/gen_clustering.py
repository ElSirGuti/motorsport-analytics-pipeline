"""
gen_clustering.py
Image generation script for docs/06_clustering.md

Generates synthetic visualisations for the K-Means driving-style classification module.
All data is generated with NumPy — no file reading required.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Ellipse
from matplotlib.gridspec import GridSpec
import os

# ---------------------------------------------------------------------------
# Style setup
# ---------------------------------------------------------------------------
plt.style.use("dark_background")

BG_FIGURE   = "#060A14"
BG_AXES     = "#0A0F1E"
CYAN        = "#00D4FF"
RED         = "#FF3D3D"
GREEN       = "#00E676"
AMBER       = "#FFB300"
PURPLE      = "#7C3AED"
DIM         = "#4A5578"

CLUSTER_COLORS = [CYAN, RED, GREEN, AMBER]
CLUSTER_NAMES  = [
    "Ataque Limpio",
    "Entrada Agresiva",
    "Conservador",
    "Salida Tardía",
]

FEATURES = [
    "apex_speed_delta",
    "braking_delta_m",
    "throttle_delta_m",
    "time_loss_s",
    "g_efficiency_pct",
    "steer_variance",
]

OUT_DIR = "c:/Users/a.gutierrez/Documents/GitHub/motorsport-analytics-pipeline/docs/images/clustering"

rng = np.random.default_rng(seed=42)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def savefig(fig, filename):
    path = os.path.join(OUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {path}")


def draw_ellipse(ax, center, cov, color, n_std=1.8, alpha=0.12):
    """Draw a covariance ellipse around a cluster center."""
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    angle = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(vals)
    ellipse = Ellipse(
        xy=center,
        width=width,
        height=height,
        angle=angle,
        facecolor=color,
        edgecolor=color,
        linewidth=1.4,
        alpha=alpha,
    )
    ax.add_patch(ellipse)
    ellipse2 = Ellipse(
        xy=center,
        width=width,
        height=height,
        angle=angle,
        facecolor="none",
        edgecolor=color,
        linewidth=1.0,
        alpha=0.55,
    )
    ax.add_patch(ellipse2)


# ---------------------------------------------------------------------------
# Synthetic cluster data
# ---------------------------------------------------------------------------
# Cluster definitions: [apex_speed_delta, time_loss_s]  (2D scatter space)
cluster_centers_2d = np.array([
    [ 4.5,  0.12],   # Ataque Limpio
    [ 1.2,  0.48],   # Entrada Agresiva
    [-4.1,  0.55],   # Conservador
    [-1.0,  0.72],   # Salida Tardía
])

cluster_std_2d = [
    (1.1, 0.05),
    (1.3, 0.07),
    (1.2, 0.06),
    (1.4, 0.08),
]

# 6-D centroid profiles (normalised 0-1 for radar)
# Order: apex_speed_delta, braking_delta_m, throttle_delta_m,
#        time_loss_s, g_efficiency_pct, steer_variance
# Higher = more of that feature (values re-coded so "high is bad" features are inverted for display)
cluster_radar = np.array([
    [0.90, 0.55, 0.85, 0.10, 0.92, 0.15],   # Ataque Limpio   — fast apex, early throttle, high G
    [0.60, 0.90, 0.40, 0.72, 0.62, 0.78],   # Entrada Agresiva— late brake, high steer variance
    [0.25, 0.35, 0.50, 0.68, 0.38, 0.32],   # Conservador     — low apex speed, low G usage
    [0.45, 0.48, 0.18, 0.85, 0.55, 0.42],   # Salida Tardía   — late throttle, high time loss
])

# Heatmap: 8 corners × 6 features
corner_ids   = np.arange(1, 9)
n_corners    = len(corner_ids)
n_features   = len(FEATURES)

# Each corner has a cluster assignment
corner_cluster = [0, 1, 2, 3, 0, 1, 3, 2]

corner_matrix = np.zeros((n_corners, n_features))
for i, cl in enumerate(corner_cluster):
    base = cluster_radar[cl].copy()
    noise = rng.normal(0, 0.07, n_features)
    corner_matrix[i] = np.clip(base + noise, 0, 1)

# ---------------------------------------------------------------------------
# FIG 1 — cluster_scatter.png
# ---------------------------------------------------------------------------

def generate_scatter():
    fig, ax = plt.subplots(figsize=(9, 6.5))
    fig.patch.set_facecolor(BG_FIGURE)
    ax.set_facecolor(BG_AXES)

    all_points = []
    all_labels = []

    for ci, (cx, cy) in enumerate(cluster_centers_2d):
        sx, sy = cluster_std_2d[ci]
        n_pts = rng.integers(14, 22)
        cov_mat = np.array([[sx**2, 0.3 * sx * sy],
                            [0.3 * sx * sy, sy**2]])
        pts = rng.multivariate_normal([cx, cy], cov_mat, n_pts)
        all_points.append(pts)
        all_labels.extend([ci] * n_pts)

        # Covariance ellipse
        draw_ellipse(ax, (cx, cy), cov_mat, CLUSTER_COLORS[ci])

        # Scatter points
        ax.scatter(
            pts[:, 0], pts[:, 1],
            s=48, color=CLUSTER_COLORS[ci], alpha=0.80,
            edgecolors="none", zorder=3,
        )

        # Centroid marker
        ax.scatter(
            cx, cy,
            s=220, color=CLUSTER_COLORS[ci],
            marker="D", edgecolors="white", linewidths=1.0,
            zorder=5, label=CLUSTER_NAMES[ci],
        )
        ax.annotate(
            CLUSTER_NAMES[ci],
            (cx, cy),
            textcoords="offset points",
            xytext=(10, 8),
            fontsize=8.5,
            color=CLUSTER_COLORS[ci],
            fontweight="bold",
        )

    # Grid & labels
    ax.grid(color=(1, 1, 1, 0.07), linewidth=0.7, linestyle="--")
    ax.set_xlabel("Δ Velocidad Apex (km/h)", color="white", fontsize=11)
    ax.set_ylabel("Pérdida de Tiempo (s)", color="white", fontsize=11)
    ax.set_title(
        "Clasificación K-Means de Curvas — Espacio de Features",
        color="white", fontsize=13, fontweight="bold", pad=14,
    )
    ax.tick_params(colors=DIM, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)

    # Inset legend
    handles = [
        mpatches.Patch(facecolor=CLUSTER_COLORS[i], label=CLUSTER_NAMES[i])
        for i in range(4)
    ]
    leg = ax.legend(
        handles=handles, loc="upper left",
        fontsize=8.5, framealpha=0.25,
        facecolor=BG_AXES, edgecolor=DIM, labelcolor="white",
    )

    # Axis annotation arrows
    ax.annotate("", xy=(5.8, 0.06), xytext=(2.5, 0.06),
                arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.2))
    ax.text(4.0, 0.04, "Más rápido", color=CYAN, fontsize=8, ha="center")

    ax.annotate("", xy=(-5.5, 0.10), xytext=(-5.5, 0.68),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2))
    ax.text(-5.5, 0.79, "Más tiempo perdido", color=RED, fontsize=7.5, ha="center")

    plt.tight_layout()
    savefig(fig, "cluster_scatter.png")


# ---------------------------------------------------------------------------
# FIG 2 — cluster_profiles.png (radar / spider chart)
# ---------------------------------------------------------------------------

RADAR_LABELS = [
    "Apex\nSpeed",
    "Freno\nTardío",
    "Accel\nTemprana",
    "Bajo\nTime Loss",
    "G\nEfficiency",
    "Estabilidad\nVolante",
]


def generate_radar():
    N = len(RADAR_LABELS)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the loop

    fig, axes = plt.subplots(
        2, 2, figsize=(10, 8.5),
        subplot_kw=dict(polar=True),
    )
    fig.patch.set_facecolor(BG_FIGURE)
    fig.suptitle(
        "Perfiles de Estilo de Conducción — K-Means (K=4)",
        color="white", fontsize=13, fontweight="bold", y=1.01,
    )

    for idx, ax in enumerate(axes.flat):
        ax.set_facecolor(BG_AXES)
        values = cluster_radar[idx].tolist()
        values += values[:1]

        color = CLUSTER_COLORS[idx]

        # Background rings
        for r in [0.25, 0.5, 0.75, 1.0]:
            ax.plot(angles, [r] * (N + 1), color=(1, 1, 1, 0.06), lw=0.7)

        # Spokes
        for a in angles[:-1]:
            ax.plot([a, a], [0, 1], color=(1, 1, 1, 0.06), lw=0.7)

        # Cluster polygon
        ax.fill(angles, values, color=color, alpha=0.22)
        ax.plot(angles, values, color=color, lw=2.0)
        ax.scatter(angles[:-1], values[:-1], s=60, color=color, zorder=5)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(RADAR_LABELS, fontsize=8.5, color="white")
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0.25", "0.5", "0.75", "1.0"], fontsize=6.5, color=DIM)
        ax.set_ylim(0, 1)

        ax.tick_params(colors=DIM)
        ax.spines["polar"].set_color(DIM)
        ax.grid(color=(1, 1, 1, 0.07))

        ax.set_title(
            CLUSTER_NAMES[idx],
            color=color, fontsize=10.5, fontweight="bold", pad=16,
        )

    plt.tight_layout()
    savefig(fig, "cluster_profiles.png")


# ---------------------------------------------------------------------------
# FIG 3 — corner_heatmap.png
# ---------------------------------------------------------------------------

FEATURE_LABELS = [
    "apex_speed_delta",
    "braking_delta_m",
    "throttle_delta_m",
    "time_loss_s",
    "g_efficiency_pct",
    "steer_variance",
]


def generate_heatmap():
    from matplotlib.colors import LinearSegmentedColormap

    # Custom colormap: dark blue → cyan
    cmap = LinearSegmentedColormap.from_list(
        "moto",
        ["#0A0F1E", "#0D47A1", "#00D4FF", "#FFB300"],
        N=256,
    )

    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor(BG_FIGURE)
    ax.set_facecolor(BG_AXES)

    im = ax.imshow(
        corner_matrix.T,
        aspect="auto",
        cmap=cmap,
        vmin=0, vmax=1,
        interpolation="nearest",
    )

    # Cell annotations
    for row in range(n_features):
        for col in range(n_corners):
            val = corner_matrix[col, row]
            text_color = "white" if val < 0.7 else "#060A14"
            ax.text(
                col, row, f"{val:.2f}",
                ha="center", va="center",
                fontsize=8.0, color=text_color, fontweight="bold",
            )

    # Corner labels with cluster color
    xtick_labels = []
    for ci_idx, cl in enumerate(corner_cluster):
        xtick_labels.append(f"C{ci_idx+1}")

    ax.set_xticks(range(n_corners))
    ax.set_xticklabels(xtick_labels, fontsize=9.5)
    for tick, cl in zip(ax.get_xticklabels(), corner_cluster):
        tick.set_color(CLUSTER_COLORS[cl])
        tick.set_fontweight("bold")

    ax.set_yticks(range(n_features))
    ax.set_yticklabels(FEATURE_LABELS, fontsize=9.5, color="white")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Valor Normalizado (0–1)", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white", labelcolor="white")
    cbar.outline.set_edgecolor(DIM)

    ax.set_xlabel("Número de Curva (colores = clúster asignado)", color="white", fontsize=10)
    ax.set_title(
        "Heatmap de Features por Curva — Sesión Analizada",
        color="white", fontsize=12, fontweight="bold", pad=12,
    )
    ax.tick_params(colors=DIM)
    for spine in ax.spines.values():
        spine.set_edgecolor(DIM)

    # Cluster legend below
    handles = [
        mpatches.Patch(facecolor=CLUSTER_COLORS[i], label=CLUSTER_NAMES[i])
        for i in range(4)
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=4, fontsize=8.5,
        framealpha=0.25,
        facecolor=BG_AXES, edgecolor=DIM, labelcolor="white",
    )

    plt.tight_layout()
    savefig(fig, "corner_heatmap.png")


# ---------------------------------------------------------------------------
# Run all generators
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating clustering documentation images...")
    generate_scatter()
    generate_radar()
    generate_heatmap()
    print("Generated images for clustering")
