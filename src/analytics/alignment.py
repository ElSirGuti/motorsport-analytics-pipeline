"""
Módulo de alineación espacial y cálculo del Time Delta (Time Slip) acumulado.

En análisis de telemetría de motorsport profesional, comparar dos vueltas en
el dominio del tiempo es engañoso: si un piloto frena 20 metros antes, todas
las señales se desfasan. La solución estándar de la industria es re-indexar
ambas vueltas al mismo eje de distancia.

Adicionalmente, este módulo calcula el Time Delta acumulado, que es el canal
más importante para un ingeniero de carrera: en cada metro del circuito se sabe
exactamente cuántos milisegundos se están ganando o perdiendo respecto a la
vuelta de referencia.

Matemática del Time Delta:
    Dado un paso de distancia fijo Δs (metros), el tiempo diferencial en cada
    metro es Δt = Δs / v. La diferencia de tiempos acumulada es:

        ΔT[n] = Σ (1/v_slow[i] - 1/v_fast[i]) · Δs

    Si v_slow < v_fast en algún punto, el término es positivo (la vuelta lenta
    pierde tiempo respecto a la rápida). El gráfico de ΔT muestra exactamente
    la zona del circuito donde se está perdiendo o ganando tiempo.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Velocidad mínima (m/s) para evitar divisiones por cero en el pit lane
V_CLIP_MIN_MS = 1.0


def alinear_vueltas_y_calcular_delta(
    df_fast: pd.DataFrame,
    df_slow: pd.DataFrame,
    paso_metros: float = 1.0,
    canales_extra: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Remuestrea dos vueltas al mismo eje de distancia uniforme y calcula el
    Time Delta (Time Slip) acumulado metro a metro.

    Args:
        df_fast:       DataFrame de la vuelta rápida (referencia). Debe tener
                       columnas 'Distance' y 'Speed' (en km/h).
        df_slow:       DataFrame de la vuelta a comparar. Misma estructura.
        paso_metros:   Resolución del eje de distancia en metros (default 1.0).
        canales_extra: Lista opcional de canales adicionales a interpolar
                       (p.ej. ['Gear', 'SteerAngle']). Si el canal existe en
                       ambos DataFrames se añade con sufijos _Fast/_Slow.

    Returns:
        DataFrame alineado con las columnas:
          - Distance
          - Speed_Fast, Speed_Slow  (km/h)
          - Throttle_Fast, Throttle_Slow
          - Brake_Fast, Brake_Slow
          - Delta_Time  (segundos acumulados; positivo = vuelta lenta pierde tiempo)
          - Canales extra (si se especifican)
    """
    logger.info("📐 Alineando vueltas al eje de distancia uniforme...")

    # 1. Eliminar duplicados y ordenar
    def _preparar(df: pd.DataFrame) -> pd.DataFrame:
        return (
            df.drop_duplicates(subset=["Distance"])
              .sort_values("Distance")
              .reset_index(drop=True)
        )

    df_fast = _preparar(df_fast)
    df_slow = _preparar(df_slow)

    # 2. Rango de distancia compartido
    max_dist = min(df_fast["Distance"].max(), df_slow["Distance"].max())
    dist_uniforme = np.arange(0, max_dist, paso_metros)
    logger.info(f"  Rango compartido: 0 – {max_dist:.1f} m  ({len(dist_uniforme)} muestras)")

    # 3. Interpolación de velocidades → convertir a m/s para la física
    v_fast_kmh = np.interp(dist_uniforme, df_fast["Distance"], df_fast["Speed"])
    v_slow_kmh = np.interp(dist_uniforme, df_slow["Distance"], df_slow["Speed"])

    v_fast_ms = np.clip(v_fast_kmh / 3.6, V_CLIP_MIN_MS, None)
    v_slow_ms = np.clip(v_slow_kmh / 3.6, V_CLIP_MIN_MS, None)

    # 4. Integración numérica del Time Delta acumulado
    #    ΔT = Σ (1/v_slow - 1/v_fast) · Δs
    delta_tiempo = np.cumsum((1.0 / v_slow_ms - 1.0 / v_fast_ms) * paso_metros)

    df_alineado = pd.DataFrame({
        "Distance":   dist_uniforme,
        "Speed_Fast": v_fast_kmh,
        "Speed_Slow": v_slow_kmh,
        "Delta_Time": delta_tiempo,
    })

    # 5. Interpolar pedales estándar
    for canal in ["Throttle", "Brake"]:
        for etiqueta, df_src in [("Fast", df_fast), ("Slow", df_slow)]:
            col_out = f"{canal}_{etiqueta}"
            if canal in df_src.columns:
                df_alineado[col_out] = np.interp(
                    dist_uniforme, df_src["Distance"], df_src[canal]
                )

    # 6. Canales adicionales opcionales
    if canales_extra:
        for canal in canales_extra:
            for etiqueta, df_src in [("Fast", df_fast), ("Slow", df_slow)]:
                if canal in df_src.columns:
                    df_alineado[f"{canal}_{etiqueta}"] = np.interp(
                        dist_uniforme, df_src["Distance"], df_src[canal]
                    )

    delta_total = delta_tiempo[-1]
    signo = "+" if delta_total >= 0 else ""
    logger.info(f"  ✓ Time Delta total: {signo}{delta_total:.3f}s")
    return df_alineado


def resumir_delta_por_sector(
    df_alineado: pd.DataFrame,
    apexes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Divide el circuito en sectores entre Apexes y calcula el Time Delta
    parcial (delta ganado/perdido) en cada sector.

    Args:
        df_alineado: DataFrame devuelto por `alinear_vueltas_y_calcular_delta`.
        apexes:      DataFrame de Apexes devuelto por `detectar_apexes_perfectos`.

    Returns:
        DataFrame con columnas:
          - sector        (número de sector)
          - dist_inicio   (metro de inicio del sector)
          - dist_fin      (metro de fin del sector)
          - delta_parcial (segundos; positivo = vuelta lenta más lenta)
          - descripcion   (p.ej. "Sector 1 → Curva 2")
    """
    if apexes.empty:
        logger.warning("  Sin Apexes disponibles para sectorización.")
        return pd.DataFrame()

    distancias_corte = [0.0] + list(apexes["Distance"].values) + [df_alineado["Distance"].max()]
    delta = df_alineado["Delta_Time"].values
    dist  = df_alineado["Distance"].values

    filas = []
    for i in range(len(distancias_corte) - 1):
        d_ini = distancias_corte[i]
        d_fin = distancias_corte[i + 1]

        mask = (dist >= d_ini) & (dist <= d_fin)
        if not mask.any():
            continue

        delta_inicio = np.interp(d_ini, dist, delta)
        delta_final  = np.interp(d_fin, dist, delta)
        delta_parcial = delta_final - delta_inicio

        if i == 0:
            desc = f"Inicio → Curva 1"
        elif i < len(distancias_corte) - 2:
            desc = f"Curva {i} → Curva {i + 1}"
        else:
            desc = f"Curva {i} → Línea de Meta"

        filas.append({
            "sector":        i + 1,
            "dist_inicio":   round(d_ini, 1),
            "dist_fin":      round(d_fin, 1),
            "delta_parcial": round(delta_parcial, 3),
            "descripcion":   desc,
        })

    df_sectores = pd.DataFrame(filas)
    logger.info(f"  ✓ Sectorización: {len(df_sectores)} sectores calculados")
    return df_sectores
