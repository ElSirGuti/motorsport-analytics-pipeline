"""
Image generation script for Anomaly Detection documentation.
Generates synthetic visualizations for the Isolation Forest module.
All data is fully synthetic — no file reading required.
"""
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

matplotlib.use("Agg")

# ── Color Palette ──────────────────────────────────────────────────────────────
CYAN   = "#00D4FF"
RED    = "#FF3D3D"
GREEN  = "#00E676"
AMBER  = "#FFB300"
PURPLE = "#7C3AED"
DIM    = "#4A5578"
BG     = "#060A14"
AX_BG  = "#0A0F1E"

GRID_COLOR = (1, 1, 1, 0.07)

OUTPUT_DIR = "c:/Users/a.gutierrez/Documents/GitHub/motorsport-analytics-pipeline/docs/images/anomaly"

plt.style.use("dark_background")

def apply_base_style(fig, ax_list):
    fig.patch.set_facecolor(BG)
    for ax in ax_list if isinstance(ax_list, (list, tuple)) else [ax_list]:
        ax.set_facecolor(AX_BG)
        ax.tick_params(colors=DIM, labelsize=9)
        ax.xaxis.label.set_color(DIM)
        ax.yaxis.label.set_color(DIM)
        ax.title.set_color(CYAN)
        for spine in ax.spines.values():
            spine.set_edgecolor(DIM)
            spine.set_alpha(0.4)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")


# ── Fig 1: isolation_tree.png ─────────────────────────────────────────────────
def gen_isolation_tree():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.patch.set_facecolor(BG)
    fig.suptitle("Isolation Forest — Path Length Intuition", color=CYAN,
                 fontsize=14, fontweight="bold", y=1.01)

    np.random.seed(42)

    for ax, title, show_anomaly in zip(axes,
                                       ["Normal Point — Deep Isolation\n(many splits required)",
                                        "Anomalous Point — Shallow Isolation\n(few splits required)"],
                                       [False, True]):
        ax.set_facecolor(AX_BG)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.set_title(title, color=CYAN, fontsize=10, pad=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(DIM)
            spine.set_alpha(0.4)
        ax.tick_params(colors=DIM, labelsize=8)
        ax.set_xlabel("Feature 1 (Speed)", color=DIM, fontsize=9)
        ax.set_ylabel("Feature 2 (LateralG)", color=DIM, fontsize=9)
        ax.grid(True, color=GRID_COLOR, linewidth=0.4, linestyle="--")

        # Draw progressive splits (rectangles)
        split_colors = [DIM, DIM, DIM, DIM, DIM, DIM]
        split_alpha  = [0.25, 0.22, 0.20, 0.18, 0.16, 0.14]

        if not show_anomaly:
            # Normal point sits in a dense cluster — needs many splits
            splits = [
                (0.0, 0.0, 1.0, 1.0),    # level 0: full space
                (0.0, 0.0, 0.60, 1.0),   # level 1: left half
                (0.0, 0.0, 0.60, 0.55),  # level 2: lower left
                (0.30, 0.0, 0.30, 0.55), # level 3: sub-region
                (0.30, 0.20, 0.30, 0.35),# level 4: narrow
                (0.30, 0.20, 0.18, 0.35),# level 5: very narrow
            ]
            point = (0.42, 0.32)
            point_color = CYAN
            label = "Normal\n(depth = 12)"
            depth_text = "E[h(x)] = 12.3"
        else:
            # Anomalous point sits alone — isolated quickly
            splits = [
                (0.0, 0.0, 1.0, 1.0),   # level 0
                (0.72, 0.0, 0.28, 1.0), # level 1: isolates right
                (0.72, 0.70, 0.28, 0.30),# level 2: already isolated
            ]
            point = (0.86, 0.82)
            point_color = RED
            label = "Anomaly\n(depth = 3)"
            depth_text = "E[h(x)] = 3.1"

        for (x, y, w, h), col, alpha in zip(splits, split_colors, split_alpha):
            rect = patches.Rectangle((x, y), w, h,
                                      linewidth=1.2, edgecolor=CYAN,
                                      facecolor=col, alpha=alpha)
            ax.add_patch(rect)

        # Normal cluster background scatter
        nc = np.random.multivariate_normal([0.40, 0.30], [[0.012, 0.002],[0.002, 0.010]], 60)
        nc = np.clip(nc, 0.05, 0.95)
        ax.scatter(nc[:, 0], nc[:, 1], c=CYAN, s=18, alpha=0.35, zorder=3)

        # The featured point
        ax.scatter([point[0]], [point[1]], c=point_color, s=90, zorder=6,
                   edgecolors="white", linewidths=0.8)
        ax.annotate(f"{label}\n{depth_text}",
                    xy=point, xytext=(point[0] - 0.28, point[1] + 0.12),
                    fontsize=8.5, color=point_color,
                    arrowprops=dict(arrowstyle="->", color=point_color, lw=1.2),
                    bbox=dict(boxstyle="round,pad=0.3", fc=AX_BG, ec=point_color, alpha=0.85))

        # Split depth label
        for i, (x, y, w, h) in enumerate(splits):
            cx, cy = x + w / 2, y + h / 2
            ax.text(cx, cy, f"L{i}", color=(1, 1, 1, 0.25), fontsize=7,
                    ha="center", va="center")

    # Score formula annotation
    fig.text(0.5, -0.04,
             r"$s(x,\,n)\;=\;2^{-\,E[h(x)]\,/\,c(n)}$"
             r"          $c(n)=2H(n-1)-2(n-1)/n$",
             ha="center", color=AMBER, fontsize=11,
             fontfamily="monospace")

    plt.tight_layout(pad=1.5)
    path = f"{OUTPUT_DIR}/isolation_tree.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Fig 2: score_comparison.png ───────────────────────────────────────────────
def gen_score_comparison():
    np.random.seed(7)
    n = 800
    dist = np.linspace(0, 3200, n)

    # Fast lap: mostly low scores, small peaks at corners
    fast_base = 0.12 + 0.08 * np.sin(dist / 180) + 0.04 * np.random.randn(n)
    # Add small corner spikes
    for center in [400, 820, 1250, 1680, 2100, 2560, 2980]:
        fast_base += 0.18 * np.exp(-((dist - center) ** 2) / (2 * 30 ** 2))
    fast_base = np.clip(fast_base, 0, 1)
    fast_smooth = pd.rolling_smooth(fast_base, 5) if False else \
        np.convolve(fast_base, np.ones(5) / 5, mode="same")

    # Slow lap: generally higher, two prominent anomaly zones
    slow_base = 0.22 + 0.10 * np.sin(dist / 180 + 0.5) + 0.06 * np.random.randn(n)
    # Zone 1: ~850–1050 m
    zone1_mask = (dist >= 850) & (dist <= 1050)
    slow_base[zone1_mask] += 0.55 * np.exp(-((dist[zone1_mask] - 950) ** 2) / (2 * 60 ** 2))
    # Zone 2: ~2200–2450 m
    zone2_mask = (dist >= 2200) & (dist <= 2450)
    slow_base[zone2_mask] += 0.65 * np.exp(-((dist[zone2_mask] - 2325) ** 2) / (2 * 75 ** 2))
    slow_base = np.clip(slow_base, 0, 1)
    slow_smooth = np.convolve(slow_base, np.ones(5) / 5, mode="same")

    fig, ax = plt.subplots(figsize=(13, 5))
    apply_base_style(fig, ax)

    ax.set_title("Anomaly Score over Lap Distance — Fast vs Slow Lap",
                 color=CYAN, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel("Distance (m)", color=DIM, fontsize=10)
    ax.set_ylabel("Anomaly Score (normalised 0–1)", color=DIM, fontsize=10)

    # Areas
    ax.fill_between(dist, fast_smooth, alpha=0.25, color=CYAN, label="Fast Lap (reference)")
    ax.plot(dist, fast_smooth, color=CYAN, lw=1.4, alpha=0.85)

    ax.fill_between(dist, slow_smooth, alpha=0.20, color=RED, label="Slow Lap")
    ax.plot(dist, slow_smooth, color=RED, lw=1.4, alpha=0.90)

    # Threshold line
    ax.axhline(0.60, color=AMBER, lw=1.5, linestyle="--", alpha=0.9, label="Threshold (0.60)")
    ax.text(3250, 0.615, "θ = 0.60", color=AMBER, fontsize=9, va="bottom")

    # Anomaly zone bands
    ax.axvspan(850, 1050, alpha=0.13, color=RED, zorder=0)
    ax.text(950, 0.95, "Zone 1\n950 m", color=RED, fontsize=8.5,
            ha="center", fontweight="bold")

    ax.axvspan(2200, 2450, alpha=0.13, color=PURPLE, zorder=0)
    ax.text(2325, 0.95, "Zone 2\n2325 m", color=PURPLE, fontsize=8.5,
            ha="center", fontweight="bold")

    ax.set_xlim(0, 3350)
    ax.set_ylim(0, 1.08)
    ax.legend(loc="upper right", fontsize=9, facecolor=AX_BG,
              edgecolor=DIM, labelcolor="white", framealpha=0.85)

    plt.tight_layout(pad=1.5)
    path = f"{OUTPUT_DIR}/score_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Fig 3: feature_space.png ──────────────────────────────────────────────────
def gen_feature_space():
    np.random.seed(99)
    n_normal = 350
    n_anom   = 45

    # Normal cluster: medium speed, moderate lateral G
    speed_n  = np.random.normal(160, 28, n_normal)
    latg_n   = np.random.normal(1.8, 0.45, n_normal)
    score_n  = np.clip(np.random.beta(1.5, 8, n_normal) * 0.55 + 0.02, 0, 0.58)

    # Anomalous cluster: high lateral G at low speed (corner mistakes) or extreme combos
    speed_a  = np.concatenate([
        np.random.normal(75, 15, n_anom // 2),   # braking anomaly
        np.random.normal(210, 12, n_anom // 2),  # overspeed anomaly
    ])
    latg_a   = np.concatenate([
        np.random.normal(3.4, 0.35, n_anom // 2),
        np.random.normal(0.25, 0.15, n_anom // 2),
    ])
    score_a  = np.clip(np.random.beta(5, 2, len(speed_a)) * 0.40 + 0.61, 0.61, 1.0)

    speed_all = np.concatenate([speed_n, speed_a])
    latg_all  = np.concatenate([latg_n, latg_a])
    score_all = np.concatenate([score_n, score_a])

    # Custom colormap: cyan → amber → red
    cmap = LinearSegmentedColormap.from_list(
        "anomaly",
        [(0.0, CYAN), (0.55, AMBER), (1.0, RED)]
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    apply_base_style(fig, ax)

    ax.set_title("Feature Space — Speed vs Lateral G\n(colored by Anomaly Score)",
                 color=CYAN, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Speed (km/h)", color=DIM, fontsize=10)
    ax.set_ylabel("Lateral G (g)", color=DIM, fontsize=10)

    sc = ax.scatter(speed_all, latg_all, c=score_all, cmap=cmap, vmin=0, vmax=1,
                    s=38, alpha=0.82, edgecolors="none", zorder=3)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Anomaly Score", color=DIM, fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=DIM, labelsize=8)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=DIM)
    cbar.outline.set_edgecolor(DIM)
    cbar.outline.set_alpha(0.4)

    # Annotation arrows
    ax.annotate("Normal\ndriving cluster", xy=(155, 1.85),
                xytext=(130, 2.8), fontsize=9, color=CYAN,
                arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.1))
    ax.annotate("Braking\nanomaly", xy=(78, 3.38),
                xytext=(30, 3.6), fontsize=9, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.1))
    ax.annotate("Overspeed\nanomaly", xy=(208, 0.28),
                xytext=(215, 1.4), fontsize=9, color=AMBER,
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.1))

    plt.tight_layout(pad=1.5)
    path = f"{OUTPUT_DIR}/feature_space.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Fig 4: zone_severity.png ──────────────────────────────────────────────────
def gen_zone_severity():
    np.random.seed(22)

    zones = [
        {"label": "Z1\n320 m",  "avg": 0.64, "severity": "leve"},
        {"label": "Z2\n620 m",  "avg": 0.71, "severity": "media"},
        {"label": "Z3\n950 m",  "avg": 0.87, "severity": "critico"},
        {"label": "Z4\n1340 m", "avg": 0.65, "severity": "leve"},
        {"label": "Z5\n1780 m", "avg": 0.74, "severity": "media"},
        {"label": "Z6\n2325 m", "avg": 0.91, "severity": "critico"},
        {"label": "Z7\n2790 m", "avg": 0.63, "severity": "leve"},
    ]

    sev_color = {"leve": GREEN, "media": AMBER, "critico": RED}

    labels   = [z["label"] for z in zones]
    scores   = [z["avg"]   for z in zones]
    colors   = [sev_color[z["severity"]] for z in zones]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    apply_base_style(fig, ax)

    ax.set_title("Anomaly Zone Severity — Avg Score per Zone",
                 color=CYAN, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel("Anomaly Zone (position on lap)", color=DIM, fontsize=10)
    ax.set_ylabel("Average Anomaly Score", color=DIM, fontsize=10)

    bars = ax.bar(labels, scores, color=colors, alpha=0.82,
                  width=0.55, edgecolor="none", zorder=3)

    # Value labels on bars
    for bar, score, zone in zip(bars, scores, zones):
        ax.text(bar.get_x() + bar.get_width() / 2,
                score + 0.012,
                f"{score:.2f}\n{zone['severity']}",
                ha="center", va="bottom", fontsize=8.5,
                color=sev_color[zone["severity"]], fontweight="bold")

    # Threshold lines
    ax.axhline(0.60, color=AMBER, lw=1.3, linestyle="--", alpha=0.7, label="Threshold (0.60)")
    ax.axhline(0.68, color=AMBER, lw=0.9, linestyle=":", alpha=0.6, label="Media threshold (0.68)")
    ax.axhline(0.82, color=RED,   lw=0.9, linestyle=":", alpha=0.6, label="Crítico threshold (0.82)")

    ax.set_ylim(0, 1.05)

    # Legend for severity
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=GREEN,  alpha=0.82, label="Leve   (0.60–0.68)"),
        Patch(facecolor=AMBER,  alpha=0.82, label="Media  (0.68–0.82)"),
        Patch(facecolor=RED,    alpha=0.82, label="Crítico (> 0.82)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9,
              facecolor=AX_BG, edgecolor=DIM, labelcolor="white", framealpha=0.85)

    plt.tight_layout(pad=1.5)
    path = f"{OUTPUT_DIR}/zone_severity.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating anomaly detection visualizations...")
    gen_isolation_tree()
    gen_score_comparison()
    gen_feature_space()
    gen_zone_severity()
    print("Generated images for anomaly")
