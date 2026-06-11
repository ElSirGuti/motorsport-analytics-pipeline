"""
gen_laptime.py — Generate documentation images for the Lap Time Potential module.

All data is synthetic (NumPy only). No file reading required.
Output: docs/images/laptime/
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

# ── Style ─────────────────────────────────────────────────────────────────────

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

OUT_DIR = Path("c:/Users/a.gutierrez/Documents/GitHub/motorsport-analytics-pipeline/docs/images/laptime")
OUT_DIR.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(42)

matplotlib.rcParams.update({
    'font.family':       'monospace',
    'axes.facecolor':    BG_AXES,
    'figure.facecolor':  BG_FIGURE,
    'text.color':        '#E0E6FF',
    'axes.labelcolor':   '#E0E6FF',
    'xtick.color':       '#8899BB',
    'ytick.color':       '#8899BB',
    'axes.edgecolor':    DIM,
    'axes.spines.top':   False,
    'axes.spines.right': False,
})


# ─────────────────────────────────────────────────────────────────────────────
# FIG 1 — percentile_comparison.png
# Distribution of historical time_loss for one corner; mark P10, P25, min, median
# ─────────────────────────────────────────────────────────────────────────────

def fig_percentile_comparison():
    # Synthetic time_loss distribution for corner 5 (right-hander)
    # Gamma-distributed to mimic real lap-time spread (right-skewed)
    n = 120
    losses = rng.gamma(shape=3.5, scale=0.09, size=n) + 0.05  # range ~0.05–1.2 s

    p10    = float(np.percentile(losses, 10))
    p25    = float(np.percentile(losses, 25))
    median = float(np.median(losses))
    mn     = float(np.min(losses))

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG_FIGURE)
    ax.set_facecolor(BG_AXES)

    # Histogram
    counts, edges, patches = ax.hist(
        losses, bins=28, color=DIM, alpha=0.55, edgecolor='none', label='Distribución histórica'
    )
    # Colour bins by zone
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    for patch, bc in zip(patches, bin_centers):
        if bc < p10:
            patch.set_facecolor(CYAN)
            patch.set_alpha(0.80)
        elif bc < p25:
            patch.set_facecolor(AMBER)
            patch.set_alpha(0.70)

    # Vertical lines
    ymax = counts.max() * 1.18
    ax.axvline(mn,     color=PURPLE, lw=1.6, ls='--', label=f'Mínimo absoluto  {mn:.3f}s')
    ax.axvline(p10,    color=CYAN,   lw=2.2, ls='-',  label=f'P10 — Reachable  {p10:.3f}s')
    ax.axvline(p25,    color=AMBER,  lw=1.6, ls='-',  label=f'P25              {p25:.3f}s')
    ax.axvline(median, color=RED,    lw=1.4, ls=':',  label=f'Mediana          {median:.3f}s')

    # Annotation: Utopia gap (min) vs Reachable gap (p10)
    actual_example = median  # pilot's current lap
    ax.annotate(
        '', xy=(mn, ymax * 0.88), xytext=(actual_example, ymax * 0.88),
        arrowprops=dict(arrowstyle='<->', color=PURPLE, lw=1.5)
    )
    ax.text((mn + actual_example) / 2, ymax * 0.91, '"Utopia" gap',
            ha='center', va='bottom', color=PURPLE, fontsize=8, style='italic')

    ax.annotate(
        '', xy=(p10, ymax * 0.76), xytext=(actual_example, ymax * 0.76),
        arrowprops=dict(arrowstyle='<->', color=CYAN, lw=1.8)
    )
    ax.text((p10 + actual_example) / 2, ymax * 0.79, 'Reachable gap',
            ha='center', va='bottom', color=CYAN, fontsize=8.5, fontweight='bold')

    ax.set_xlabel('time_loss_s  [s]', fontsize=10)
    ax.set_ylabel('Frecuencia', fontsize=10)
    ax.set_title('Curva 5 — Distribución Histórica de Pérdida de Tiempo (n=120)',
                 fontsize=11, color='#E0E6FF', pad=12)
    ax.set_ylim(0, ymax * 1.02)
    ax.grid(axis='y', color=GRID_COLOR, linewidth=0.7)
    ax.legend(fontsize=8.5, framealpha=0.15, loc='upper right',
              facecolor=BG_AXES, edgecolor=DIM)

    # Subtitle strip
    fig.text(0.5, 0.01,
             'P10 es el percentil alcanzable — más honesto que el mínimo absoluto (ruido)',
             ha='center', color=DIM, fontsize=8)

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT_DIR / 'percentile_comparison.png', dpi=150, bbox_inches='tight',
                facecolor=BG_FIGURE)
    plt.close(fig)
    print("  [1/4] percentile_comparison.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 2 — consistency_visual.png
# 8 corners, horizontal bars coloured by consistency %, error bars for σ
# ─────────────────────────────────────────────────────────────────────────────

def fig_consistency_visual():
    corner_labels = [f'C{i}' for i in range(1, 9)]
    # Synthetic consistency scores (some good, some bad)
    consistency  = np.array([92.1, 85.4, 61.3, 48.7, 78.9, 33.2, 88.0, 54.6])
    mean_loss    = np.array([0.18, 0.12, 0.31, 0.42, 0.22, 0.55, 0.15, 0.38])
    # std from consistency formula: std = mean*(1 - consistency/100)
    std_loss     = mean_loss * (1.0 - consistency / 100.0)

    colors = []
    for c in consistency:
        if c >= 80:
            colors.append(GREEN)
        elif c >= 50:
            colors.append(AMBER)
        else:
            colors.append(RED)

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG_FIGURE)
    ax.set_facecolor(BG_AXES)

    y_pos = np.arange(len(corner_labels))
    bars  = ax.barh(y_pos, consistency, height=0.55, color=colors, alpha=0.82,
                    xerr=std_loss * 100, error_kw=dict(ecolor='#FFFFFF', capsize=4,
                                                        elinewidth=1.2, capthick=1.2))

    # Threshold lines
    ax.axvline(80, color=GREEN, lw=1.2, ls='--', alpha=0.5, label='80% — Robótico')
    ax.axvline(50, color=AMBER, lw=1.2, ls='--', alpha=0.5, label='50% — Alta varianza')

    # Value labels
    for i, (val, col) in enumerate(zip(consistency, colors)):
        ax.text(val + 1.5, i, f'{val:.1f}%', va='center', ha='left',
                color=col, fontsize=9, fontweight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(corner_labels, fontsize=10)
    ax.set_xlabel('Consistency Score  [%]', fontsize=10)
    ax.set_xlim(0, 110)
    ax.set_title('Consistencia por Curva — Historial de Vuelta',
                 fontsize=11, color='#E0E6FF', pad=12)
    ax.grid(axis='x', color=GRID_COLOR, linewidth=0.7)

    # Legend patches
    legend_patches = [
        mpatches.Patch(color=GREEN, label='≥ 80 %  Consistente'),
        mpatches.Patch(color=AMBER, label='≥ 50 %  Optimizable'),
        mpatches.Patch(color=RED,   label='< 50 %  Crítico'),
    ]
    ax.legend(handles=legend_patches, fontsize=8.5, loc='lower right',
              framealpha=0.15, facecolor=BG_AXES, edgecolor=DIM)

    fig.text(0.5, 0.01,
             'Las barras de error representan σ (desviación estándar) del time_loss histórico',
             ha='center', color=DIM, fontsize=8)

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT_DIR / 'consistency_visual.png', dpi=150, bbox_inches='tight',
                facecolor=BG_FIGURE)
    plt.close(fig)
    print("  [2/4] consistency_visual.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 3 — reachable_vs_actual.png
# Bar chart per sector: actual loss (red) vs reachable P10 (green)
# ─────────────────────────────────────────────────────────────────────────────

def fig_reachable_vs_actual():
    sector_labels = [f'S{i}' for i in range(1, 9)]
    actual_loss   = np.array([0.48, 0.15, 0.62, 0.31, 0.55, 0.22, 0.40, 0.18])
    reachable_p10 = np.array([0.18, 0.10, 0.22, 0.14, 0.20, 0.08, 0.16, 0.09])
    recoverable   = actual_loss - reachable_p10

    total_actual     = actual_loss.sum()
    total_reachable  = reachable_p10.sum()
    total_recoverable = recoverable.sum()

    x     = np.arange(len(sector_labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor=BG_FIGURE)
    ax.set_facecolor(BG_AXES)

    bars_actual    = ax.bar(x - width / 2, actual_loss,   width, color=RED,   alpha=0.80,
                            label=f'Pérdida actual  (Σ={total_actual:.2f}s)')
    bars_reachable = ax.bar(x + width / 2, reachable_p10, width, color=GREEN, alpha=0.80,
                            label=f'Reachable P10  (Σ={total_reachable:.2f}s)')

    # Recoverable arrows / annotations
    for i, (act, reach, rec) in enumerate(zip(actual_loss, reachable_p10, recoverable)):
        mid_x = x[i] - width / 2
        ax.annotate(
            f'-{rec:.2f}s',
            xy=(mid_x, act + 0.01), xytext=(mid_x, act + 0.06),
            ha='center', va='bottom', color=CYAN, fontsize=7.5,
            arrowprops=dict(arrowstyle='->', color=CYAN, lw=0.8)
        )

    ax.set_xticks(x)
    ax.set_xticklabels(sector_labels, fontsize=10)
    ax.set_ylabel('time_loss_s  [s]', fontsize=10)
    ax.set_title('Pérdida Real vs Reachable (P10) por Sector',
                 fontsize=11, color='#E0E6FF', pad=12)
    ax.grid(axis='y', color=GRID_COLOR, linewidth=0.7)
    ax.legend(fontsize=9, framealpha=0.15, facecolor=BG_AXES, edgecolor=DIM)

    # Total recoverable annotation box
    ax.text(0.98, 0.94,
            f'Tiempo recuperable total\n{total_recoverable:.3f} s',
            transform=ax.transAxes, ha='right', va='top',
            color=CYAN, fontsize=9.5, fontweight='bold',
            bbox=dict(facecolor=BG_AXES, edgecolor=CYAN, boxstyle='round,pad=0.4', alpha=0.7))

    plt.tight_layout()
    fig.savefig(OUT_DIR / 'reachable_vs_actual.png', dpi=150, bbox_inches='tight',
                facecolor=BG_FIGURE)
    plt.close(fig)
    print("  [3/4] reachable_vs_actual.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIG 4 — xgboost_feature_importance.png
# Horizontal bar chart of feature importances + deviation chips for 2 corners
# ─────────────────────────────────────────────────────────────────────────────

def fig_xgboost_feature_importance():
    features     = ['V. entrada', 'V. apex', 'Gas salida', 'Frenada',
                    'Gas delta', 'Efic. G', 'Var. volante']
    feature_keys = ['entry_speed_kmh', 'apex_speed_kmh', 'exit_throttle_pct',
                    'braking_delta_m', 'throttle_delta_m', 'g_efficiency_pct',
                    'steer_variance']
    # Synthetic importances (sum ~1 after softmax-style)
    raw_imp = np.array([0.22, 0.28, 0.18, 0.12, 0.08, 0.07, 0.05])
    importances = raw_imp / raw_imp.sum()

    # Feature type colours
    speed_idx = [0, 1, 2]
    ctrl_idx  = [3, 4, 6]
    eff_idx   = [5]
    bar_colors = []
    for i in range(len(features)):
        if i in speed_idx:
            bar_colors.append(CYAN)
        elif i in ctrl_idx:
            bar_colors.append(AMBER)
        else:
            bar_colors.append(PURPLE)

    y_pos = np.arange(len(features))
    # Sort by importance descending
    order = np.argsort(importances)

    fig, (ax_imp, ax_chip) = plt.subplots(
        1, 2, figsize=(13, 6),
        gridspec_kw={'width_ratios': [1.6, 1]},
        facecolor=BG_FIGURE
    )

    # ── Left: feature importances ──
    ax_imp.set_facecolor(BG_AXES)
    ax_imp.barh(
        np.arange(len(features)),
        importances[order],
        height=0.55,
        color=[bar_colors[i] for i in order],
        alpha=0.82,
    )
    ax_imp.set_yticks(np.arange(len(features)))
    ax_imp.set_yticklabels([features[i] for i in order], fontsize=10)
    ax_imp.set_xlabel('Importancia relativa (XGBoost gain)', fontsize=9.5)
    ax_imp.set_title('Importancia de Features — XGBoost', fontsize=11,
                     color='#E0E6FF', pad=10)
    ax_imp.grid(axis='x', color=GRID_COLOR, linewidth=0.7)

    # Value labels
    for j, idx in enumerate(order):
        ax_imp.text(importances[idx] + 0.003, j, f'{importances[idx]:.3f}',
                    va='center', color='#E0E6FF', fontsize=8.5)

    # Legend for bar colours
    legend_patches = [
        mpatches.Patch(color=CYAN,   label='Velocidad'),
        mpatches.Patch(color=AMBER,  label='Control'),
        mpatches.Patch(color=PURPLE, label='Eficiencia'),
    ]
    ax_imp.legend(handles=legend_patches, fontsize=8, framealpha=0.15,
                  facecolor=BG_AXES, edgecolor=DIM, loc='lower right')

    # ── Right: deviation chips for 2 example corners ──
    ax_chip.set_facecolor(BG_AXES)
    ax_chip.set_xlim(0, 1)
    ax_chip.set_ylim(0, 1)
    ax_chip.axis('off')
    ax_chip.set_title('Desviaciones vs Perfil Rápido', fontsize=10,
                      color='#E0E6FF', pad=10)

    # Corner A deviations
    corner_a_title = 'Curva 3 — Chicana'
    deviations_a = [
        ('V. apex',  '112 km/h', '↑ 125 km/h', RED,   'z=1.8'),
        ('Frenada',  '+18 m',    '→ +8 m',      AMBER, 'z=1.1'),
    ]
    # Corner B deviations
    corner_b_title = 'Curva 7 — Curva rápida'
    deviations_b = [
        ('Gas salida', '78 %',  '↑ 92 %',   RED,  'z=2.1'),
        ('Efic. G',    '61 %',  '↑ 74 %',   AMBER,'z=0.9'),
    ]

    def draw_chip_block(title, deviations, y_start):
        ax_chip.text(0.05, y_start, title, color=CYAN, fontsize=9.5,
                     fontweight='bold', va='top')
        y = y_start - 0.08
        for feat, actual, optimal, col, z_label in deviations:
            # Background chip
            rect = FancyBboxPatch((0.03, y - 0.07), 0.92, 0.10,
                                  boxstyle='round,pad=0.01',
                                  linewidth=0.8, edgecolor=col,
                                  facecolor=BG_FIGURE, alpha=0.7,
                                  transform=ax_chip.transAxes)
            ax_chip.add_patch(rect)
            ax_chip.text(0.07, y - 0.01, feat, color='#E0E6FF', fontsize=8.5,
                         va='center', fontweight='bold')
            ax_chip.text(0.40, y - 0.01, actual, color=col, fontsize=8.5,
                         va='center')
            ax_chip.text(0.62, y - 0.01, optimal, color=GREEN, fontsize=8.5,
                         va='center')
            ax_chip.text(0.90, y - 0.01, z_label, color=DIM, fontsize=7.5,
                         va='center')
            y -= 0.13

    draw_chip_block(corner_a_title, deviations_a, 0.92)
    draw_chip_block(corner_b_title, deviations_b, 0.52)

    # Column headers
    ax_chip.text(0.07, 0.97, 'Feature',   color=DIM, fontsize=7.5)
    ax_chip.text(0.40, 0.97, 'Real',      color=DIM, fontsize=7.5)
    ax_chip.text(0.62, 0.97, 'Objetivo',  color=DIM, fontsize=7.5)
    ax_chip.text(0.88, 0.97, 'z-score',   color=DIM, fontsize=7.5)

    plt.tight_layout()
    fig.savefig(OUT_DIR / 'xgboost_feature_importance.png', dpi=150,
                bbox_inches='tight', facecolor=BG_FIGURE)
    plt.close(fig)
    print("  [4/4] xgboost_feature_importance.png")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Writing images to {OUT_DIR}")
    fig_percentile_comparison()
    fig_consistency_visual()
    fig_reachable_vs_actual()
    fig_xgboost_feature_importance()
    print("Generated images for laptime")
