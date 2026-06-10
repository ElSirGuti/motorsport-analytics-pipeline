"""
Generación de gráficos de telemetría con Matplotlib.

Produce visualizaciones estándar de ingeniería de pista:
- Velocidad vs Distancia (ambas vueltas superpuestas)
- Freno/Acelerador vs Distancia
- Delta de tiempo acumulado
- Detalle por curva
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Backend sin GUI (para servidor)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import logging
import io
import base64

logger = logging.getLogger(__name__)

# Estilo global para gráficos de motorsport
COLORS = {
    "lap_a": "#00D4FF",      # Cyan brillante (referencia)
    "lap_b": "#FF4444",      # Rojo (comparación)
    "brake_a": "#FF6B00",    # Naranja (freno A)
    "brake_b": "#FF0066",    # Rosa (freno B)
    "throttle_a": "#00FF88", # Verde (throttle A)
    "throttle_b": "#FFAA00", # Amarillo (throttle B)
    "delta_pos": "#FF4444",  # Rojo (pierde tiempo)
    "delta_neg": "#00FF88",  # Verde (gana tiempo)
    "grid": "#333333",
    "bg": "#1A1A2E",
    "text": "#E0E0E0",
}


def _setup_style():
    """Configura el estilo dark de los gráficos."""
    plt.rcParams.update({
        "figure.facecolor": COLORS["bg"],
        "axes.facecolor": "#16213E",
        "axes.edgecolor": COLORS["grid"],
        "axes.labelcolor": COLORS["text"],
        "text.color": COLORS["text"],
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "grid.color": COLORS["grid"],
        "grid.alpha": 0.3,
        "font.family": "sans-serif",
        "font.size": 10,
    })


def _fig_to_base64(fig) -> str:
    """Convierte una figura Matplotlib a string base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def plot_speed_comparison(comparison_result: dict, save_path: str = None) -> str:
    """
    Gráfico de velocidad superpuesta vs distancia.
    
    Args:
        comparison_result: Diccionario devuelto por compare_laps().
        save_path: Ruta opcional para guardar PNG.
    
    Returns:
        String base64 de la imagen PNG.
    """
    _setup_style()
    
    data = comparison_result["speed_comparison"]
    distance = data["distance"]
    
    fig, ax = plt.subplots(figsize=(16, 5))
    
    ax.plot(distance, data["speed_a"], color=COLORS["lap_a"],
            linewidth=1.5, label="Piloto A (Referencia)", alpha=0.9)
    ax.plot(distance, data["speed_b"], color=COLORS["lap_b"],
            linewidth=1.5, label="Piloto B", alpha=0.9)
    
    # Sombrear zonas donde B es más lento
    speed_a = np.array(data["speed_a"])
    speed_b = np.array(data["speed_b"])
    ax.fill_between(distance, speed_a, speed_b,
                    where=(speed_b < speed_a),
                    color=COLORS["delta_pos"], alpha=0.15, label="B más lento")
    ax.fill_between(distance, speed_a, speed_b,
                    where=(speed_b > speed_a),
                    color=COLORS["delta_neg"], alpha=0.15, label="B más rápido")
    
    ax.set_xlabel("Distancia (m)")
    ax.set_ylabel("Velocidad (km/h)")
    ax.set_title("Comparación de Velocidad", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    ax.grid(True, alpha=0.2)
    ax.set_xlim(distance[0], distance[-1])
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        logger.info(f"  Gráfico guardado: {save_path}")
    
    return _fig_to_base64(fig)


def plot_brake_throttle_overlay(comparison_result: dict, save_path: str = None) -> str:
    """
    Gráfico de freno y acelerador superpuestos para ambas vueltas.
    
    Returns:
        String base64 de la imagen PNG.
    """
    _setup_style()
    
    brake_data = comparison_result["brake_comparison"]
    throttle_data = comparison_result["throttle_comparison"]
    distance = brake_data["distance"]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
    
    # Panel superior: Freno
    ax1.plot(distance, brake_data["brake_a"], color=COLORS["brake_a"],
             linewidth=1.2, label="Freno A", alpha=0.9)
    ax1.plot(distance, brake_data["brake_b"], color=COLORS["brake_b"],
             linewidth=1.2, label="Freno B", alpha=0.9)
    ax1.fill_between(distance, brake_data["brake_a"], alpha=0.15, color=COLORS["brake_a"])
    ax1.fill_between(distance, brake_data["brake_b"], alpha=0.1, color=COLORS["brake_b"])
    ax1.set_ylabel("Freno (%)")
    ax1.set_title("Comparación de Freno y Acelerador", fontsize=14, fontweight="bold")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.2)
    ax1.set_ylim(-5, 105)
    
    # Panel inferior: Acelerador
    ax2.plot(distance, throttle_data["throttle_a"], color=COLORS["throttle_a"],
             linewidth=1.2, label="Acelerador A", alpha=0.9)
    ax2.plot(distance, throttle_data["throttle_b"], color=COLORS["throttle_b"],
             linewidth=1.2, label="Acelerador B", alpha=0.9)
    ax2.fill_between(distance, throttle_data["throttle_a"], alpha=0.1, color=COLORS["throttle_a"])
    ax2.fill_between(distance, throttle_data["throttle_b"], alpha=0.1, color=COLORS["throttle_b"])
    ax2.set_xlabel("Distancia (m)")
    ax2.set_ylabel("Acelerador (%)")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.2)
    ax2.set_ylim(-5, 105)
    ax2.set_xlim(distance[0], distance[-1])
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
    
    return _fig_to_base64(fig)


def plot_time_delta(comparison_result: dict, save_path: str = None) -> str:
    """
    Gráfico del delta de tiempo acumulado a lo largo de la vuelta.
    
    Positivo = piloto B pierde tiempo.
    Negativo = piloto B gana tiempo.
    
    Returns:
        String base64 de la imagen PNG.
    """
    _setup_style()
    
    delta_data = comparison_result["time_delta_series"]
    distance = delta_data["distance"]
    delta = np.array(delta_data["delta"])
    
    fig, ax = plt.subplots(figsize=(16, 4))
    
    ax.fill_between(distance, delta, 0,
                    where=(delta >= 0), color=COLORS["delta_pos"], alpha=0.3)
    ax.fill_between(distance, delta, 0,
                    where=(delta < 0), color=COLORS["delta_neg"], alpha=0.3)
    ax.plot(distance, delta, color="#FFFFFF", linewidth=1.5, alpha=0.9)
    
    ax.axhline(y=0, color=COLORS["text"], linewidth=0.5, alpha=0.5)
    
    ax.set_xlabel("Distancia (m)")
    ax.set_ylabel("Delta (s)")
    ax.set_title(f"Delta de Tiempo Acumulado  |  Total: {delta[-1]:+.3f}s",
                fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.2)
    ax.set_xlim(distance[0], distance[-1])
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
    
    return _fig_to_base64(fig)


def generate_full_report_image(comparison_result: dict, save_path: str = None) -> str:
    """
    Genera una imagen combinada con los tres gráficos principales.
    
    Returns:
        String base64 de la imagen PNG.
    """
    _setup_style()
    
    fig = plt.figure(figsize=(18, 16))
    gs = gridspec.GridSpec(4, 1, height_ratios=[3, 2, 2, 2], hspace=0.35)
    
    speed_data = comparison_result["speed_comparison"]
    brake_data = comparison_result["brake_comparison"]
    throttle_data = comparison_result["throttle_comparison"]
    delta_data = comparison_result["time_delta_series"]
    distance = speed_data["distance"]
    
    # 1. Velocidad
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(distance, speed_data["speed_a"], color=COLORS["lap_a"],
             linewidth=1.5, label="Piloto A", alpha=0.9)
    ax1.plot(distance, speed_data["speed_b"], color=COLORS["lap_b"],
             linewidth=1.5, label="Piloto B", alpha=0.9)
    ax1.set_ylabel("Velocidad (km/h)")
    ax1.set_title("EL ANALISTA AUTOMATIZADO — Comparación de Vueltas",
                   fontsize=16, fontweight="bold", pad=15)
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.2)
    
    # 2. Freno
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(distance, brake_data["brake_a"], color=COLORS["brake_a"],
             linewidth=1.2, label="Freno A", alpha=0.9)
    ax2.plot(distance, brake_data["brake_b"], color=COLORS["brake_b"],
             linewidth=1.2, label="Freno B", alpha=0.9)
    ax2.set_ylabel("Freno (%)")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.2)
    ax2.set_ylim(-5, 105)
    
    # 3. Acelerador
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.plot(distance, throttle_data["throttle_a"], color=COLORS["throttle_a"],
             linewidth=1.2, label="Acelerador A", alpha=0.9)
    ax3.plot(distance, throttle_data["throttle_b"], color=COLORS["throttle_b"],
             linewidth=1.2, label="Acelerador B", alpha=0.9)
    ax3.set_ylabel("Acelerador (%)")
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.2)
    ax3.set_ylim(-5, 105)
    
    # 4. Delta
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    delta = np.array(delta_data["delta"])
    ax4.fill_between(distance, delta, 0,
                     where=(delta >= 0), color=COLORS["delta_pos"], alpha=0.3)
    ax4.fill_between(distance, delta, 0,
                     where=(delta < 0), color=COLORS["delta_neg"], alpha=0.3)
    ax4.plot(distance, delta, color="#FFFFFF", linewidth=1.5)
    ax4.axhline(y=0, color=COLORS["text"], linewidth=0.5, alpha=0.5)
    ax4.set_xlabel("Distancia (m)")
    ax4.set_ylabel("Delta (s)")
    ax4.set_title(f"Delta: {delta[-1]:+.3f}s", fontsize=11)
    ax4.grid(True, alpha=0.2)
    ax4.set_xlim(distance[0], distance[-1])
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        logger.info(f"  Reporte visual guardado: {save_path}")
    
    return _fig_to_base64(fig)
