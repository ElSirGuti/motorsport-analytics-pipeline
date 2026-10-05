"""
Motor de comparación de vueltas.

Este es el módulo central del proyecto: recibe dos vueltas alineadas por distancia
y produce un reporte detallado de las diferencias curva por curva.

El output principal es un diccionario estructurado con:
- Resumen general (delta de tiempo total, peor curva, etc.)
- Análisis detallado por curva (diferencias de frenado, apex, aceleración)
- Delta de tiempo acumulado a lo largo de la vuelta (para gráficos)
"""

import numpy as np
import pandas as pd
from ..telemetry.metrics import segment_corners, pair_corners
import logging

logger = logging.getLogger(__name__)


def _calculate_time_delta(df_a: pd.DataFrame, df_b: pd.DataFrame) -> np.ndarray:
    """
    Calcula el delta de tiempo acumulado entre dos vueltas alineadas por distancia.
    
    Para cada punto de distancia, estima cuánto tiempo lleva acumulado
    de ventaja/desventaja el piloto B respecto al piloto A.
    
    ΔT = Σ (1/v_B - 1/v_A) * Δd
    
    Un valor positivo significa que B va más lento (pierde tiempo).
    Un valor negativo significa que B va más rápido (gana tiempo).
    
    Args:
        df_a: DataFrame de la vuelta A (referencia).
        df_b: DataFrame de la vuelta B (a comparar).
    
    Returns:
        Array con el delta de tiempo acumulado en cada punto.
    """
    speed_a_ms = df_a["Speed"].values / 3.6  # km/h → m/s
    speed_b_ms = df_b["Speed"].values / 3.6
    
    # Evitar división por cero
    speed_a_ms = np.maximum(speed_a_ms, 1.0)
    speed_b_ms = np.maximum(speed_b_ms, 1.0)
    
    # Intervalo de distancia (asumimos uniforme tras alineación)
    ds = np.diff(df_a["Distance"].values)
    
    # Diferencia de tiempo invertida por tramo
    dt_diff = ds * (1.0 / speed_b_ms[:-1] - 1.0 / speed_a_ms[:-1])
    
    # Acumular
    time_delta = np.concatenate([[0], np.cumsum(dt_diff)])
    
    return time_delta


def _estimate_corner_time_loss(df_a: pd.DataFrame, df_b: pd.DataFrame,
                                corner_a: dict, corner_b: dict) -> float:
    """
    Estima el tiempo perdido en una curva específica.
    
    Calcula el delta entre el punto de frenado de A y el full throttle de A
    (toda la zona de la curva).
    """
    brake_d = min(corner_a["braking_point"]["distance"], 
                  corner_b["braking_point"]["distance"])
    throttle_d = max(corner_a["full_throttle"]["distance"],
                     corner_b["full_throttle"]["distance"])
    
    mask = (df_a["Distance"] >= brake_d) & (df_a["Distance"] <= throttle_d)
    
    if mask.sum() == 0:
        return 0.0
    
    speed_a = df_a.loc[mask, "Speed"].values / 3.6  # m/s
    speed_b = df_b.loc[mask, "Speed"].values / 3.6
    
    speed_a = np.maximum(speed_a, 1.0)
    speed_b = np.maximum(speed_b, 1.0)
    
    distances = df_a.loc[mask, "Distance"].values
    ds = np.diff(distances)
    
    dt = ds * (1.0 / speed_b[:-1] - 1.0 / speed_a[:-1])
    
    return float(np.sum(dt))


def _describe_corner(num: int, brake_delta: float, apex_speed_delta: float, throttle_delta: float,
                     time_loss: float, apex_speed_a: float, apex_speed_b: float) -> str:
    """Descripción en español de una curva (frenada, apex, gas y pérdida total)."""
    i = num - 1
    # Generar descripción en español
    desc_parts = []
    if brake_delta < -2:
        desc_parts.append(
            f"el piloto B frenó {abs(brake_delta):.0f} metros antes que el piloto A"
        )
    elif brake_delta > 2:
        desc_parts.append(
            f"el piloto B frenó {abs(brake_delta):.0f} metros después que el piloto A"
        )
    
    if apex_speed_delta < -2:
        desc_parts.append(
            f"lo que redujo su velocidad mínima en el Apex por {abs(apex_speed_delta):.1f} km/h"
        )
    elif apex_speed_delta > 2:
        desc_parts.append(
            f"lo que aumentó su velocidad mínima en el Apex por {abs(apex_speed_delta):.1f} km/h"
        )
    
    if throttle_delta > 2:
        # Estimar el retraso en segundos usando la velocidad media de la zona
        avg_speed_ms = (apex_speed_a / 3.6 + apex_speed_b / 3.6) / 2
        if avg_speed_ms > 0:
            throttle_time_delay = throttle_delta / avg_speed_ms
        else:
            throttle_time_delay = 0
        desc_parts.append(
            f"y retrasó la aceleración a fondo por {throttle_time_delay:.1f} segundos"
        )
    
    if time_loss > 0.01:
        desc_parts.append(
            f"Pérdida total en el sector: {time_loss:.2f} segundos"
        )
    
    description = ""
    if desc_parts:
        description = f"En la curva {i + 1}, " + ", ".join(desc_parts[:-1])
        if len(desc_parts) > 1:
            description += ". " + desc_parts[-1] + "."
        else:
            description += ". " + desc_parts[0] + "." if len(desc_parts) == 1 else "."
    else:
        description = f"Curva {i + 1}: rendimiento similar entre ambos pilotos."
    return description


def _corner_lap(df: pd.DataFrame) -> dict:
    """Lap dict for ``corner_metrics`` from an aligned frame (positions in metres, k = 1)."""
    def pedal(col):
        if col not in df.columns:
            return None
        v = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        return v * 100.0 if len(v) and np.nanmax(v) <= 1.05 else v
    d = df["Distance"].to_numpy(dtype=float)
    return {"grid": d, "speed": df["Speed"].to_numpy(dtype=float), "brake": pedal("Brake"),
            "throttle": pedal("Throttle"), "length": 1.0}


def _corners_from_map(df_a: pd.DataFrame, df_b: pd.DataFrame, corner_map: dict) -> tuple:
    """
    Per-corner comparison for the corners of the unified corner map (positions already in the metres of
    the aligned frames). Same fields as the classic report, plus the map fields. flat_out / kink corners
    keep their time loss but report 0.0 braking / apex / throttle deltas with ``*_available`` False.
    Returns (corner_analyses, worst_corner, worst_loss).
    """
    from src.analytics import corner_metrics as cm
    corners = corner_map["corners"]
    la, lb = _corner_lap(df_a), _corner_lap(df_b)   # length 1.0 with L = 1.0 below: no scaling (k = 1)
    out, worst_loss, worst_corner = [], 0.0, 0
    for c, (prev_apex, next_apex) in zip(corners, cm.neighbours(corners)):
        ma = cm.lap_corner_metrics(la, c, 1.0, prev_apex, next_apex)
        mb = cm.lap_corner_metrics(lb, c, 1.0, prev_apex, next_apex)
        d = cm.delta_vs_reference(ma, mb)
        flat = cm.is_flat(c)
        time_loss = d["time_loss"]
        brake_delta = d["brake_delta"] if d["brake_delta"] is not None else 0.0
        apex_delta = d["apex_delta"] if d["apex_delta"] is not None else 0.0
        thr_delta = d["thtl_delta"] if d["thtl_delta"] is not None else 0.0
        if time_loss > worst_loss:
            worst_loss, worst_corner = time_loss, int(c["number"])
        if flat:
            description = (f"Curva {c['number']}: curva a fondo, pérdida en la ventana "
                           f"{time_loss:+.2f} segundos." if abs(time_loss) > 0.01
                           else f"Curva {c['number']}: rendimiento similar entre ambos pilotos.")
        else:
            description = _describe_corner(int(c["number"]), brake_delta, apex_delta, thr_delta, time_loss,
                                           ma["vmin"] or 0.0, mb["vmin"] or 0.0)
        ev = [x for x in (ma["brake"], mb["brake"]) if x is not None]
        out.append({
            "corner_number": int(c["number"]),
            "braking_delta_meters": round(float(brake_delta), 1),
            "apex_speed_delta_kmh": round(float(apex_delta), 1),
            "throttle_delta_meters": round(float(thr_delta), 1),
            "time_loss_seconds": round(float(time_loss), 3),
            "description": description,
            "start_distance": round(float(min(ev + [c["start_m"]])), 1),
            "end_distance": round(float(c["end_m"]), 1),
            "ref_brake_distance": round(float(ma["brake"]), 1) if ma["brake"] is not None else None,
            "ref_apex_speed": round(float(ma["vmin"]), 1) if ma["vmin"] is not None else None,
            "ref_apex_distance": round(float(c["apex_distance_m"]), 1),
            "comp_brake_distance": round(float(mb["brake"]), 1) if mb["brake"] is not None else None,
            "comp_apex_speed": round(float(mb["vmin"]), 1) if mb["vmin"] is not None else None,
            "comp_apex_distance": round(float(c["apex_distance_m"]), 1),
            # unified corner map fields (additive)
            "braking_delta_available": d["brake_delta"] is not None,
            "apex_delta_available": d["apex_delta"] is not None,
            "throttle_delta_available": d["thtl_delta"] is not None,
            "number": int(c["number"]), "name": c.get("name"), "corner_name": c.get("name"),
            "kind": c.get("kind"), "direction": c.get("direction"), "min_radius_m": c.get("min_radius_m"),
            "flat_out_share": c.get("flat_out_share"), "confidence": c.get("confidence"),
            "is_complex": bool(c.get("is_complex")),
        })
    return out, worst_corner, worst_loss


def compare_laps(df_a: pd.DataFrame, df_b: pd.DataFrame, corner_map: dict | None = None) -> dict:
    """
    Compara dos vueltas alineadas por distancia y genera un reporte completo.
    
    Esta función es el corazón del proyecto. Toma dos DataFrames que ya han sido
    alineados por distancia (misma longitud, mismo vector de distancia) y produce
    un análisis detallado de las diferencias de pilotaje.
    
    Args:
        df_a: DataFrame vuelta A (referencia/mejor vuelta).
        df_b: DataFrame vuelta B (vuelta a analizar/con errores).
        corner_map: mapa unificado de curvas (``corner_service``), con las posiciones ya escaladas a la
                    vuelta A. Si se da, las curvas son las del mapa y no se detectan (``segment_corners``);
                    si no, camino clásico.
    
    Returns:
        Diccionario con la estructura:
        {
            "summary": {
                "total_time_delta": float,  # Segundos (positivo = B más lento)
                "worst_corner": int,
                "worst_corner_loss": float,
                "num_corners_analyzed": int,
            },
            "corners": [
                {
                    "corner_number": int,
                    "braking_delta_meters": float,  # Negativo = B frenó antes
                    "apex_speed_delta_kmh": float,  # Negativo = B más lento
                    "throttle_delta_meters": float,  # Positivo = B aceleró más tarde
                    "time_loss_seconds": float,
                    "description": str,
                }, ...
            ],
            "time_delta_series": {
                "distance": list[float],
                "delta": list[float],
            },
            "speed_comparison": {
                "distance": list[float],
                "speed_a": list[float],
                "speed_b": list[float],
            },
            "brake_comparison": {
                "distance": list[float],
                "brake_a": list[float],
                "brake_b": list[float],
            },
            "throttle_comparison": {
                "distance": list[float],
                "throttle_a": list[float],
                "throttle_b": list[float],
            },
        }
    """
    logger.info("=" * 60)
    logger.info("COMPARACIÓN DE VUELTAS")
    logger.info("=" * 60)
    
    # 1. Segmentar las curvas de cada vuelta (con el mapa unificado las curvas vienen dadas: no se detectan)
    use_map = bool(corner_map and corner_map.get("corners"))
    corners_a = [] if use_map else segment_corners(df_a)
    corners_b = [] if use_map else segment_corners(df_b)
    
    # 2. Calcular el delta de tiempo acumulado
    time_delta = _calculate_time_delta(df_a, df_b)
    total_time_delta = float(time_delta[-1])
    
    logger.info(f"  Delta de tiempo total: {total_time_delta:+.3f}s")
    
    # 3. Emparejar curvas de A y B por proximidad del apex
    paired = [] if use_map else pair_corners(corners_a, corners_b)
    num_corners = len(paired)
    
    corner_analyses = []
    worst_loss = 0
    worst_corner = 0
    
    for i, ca, cb in paired:
        
        # Diferencia en punto de frenado (metros)
        brake_delta = cb["braking_point"]["distance"] - ca["braking_point"]["distance"]
        
        # Diferencia en velocidad de apex (km/h)
        apex_speed_delta = cb["apex"]["speed"] - ca["apex"]["speed"]
        
        # Diferencia en punto de aceleración a fondo (metros)
        throttle_delta = cb["full_throttle"]["distance"] - ca["full_throttle"]["distance"]
        
        # Pérdida de tiempo en esta curva
        time_loss = _estimate_corner_time_loss(df_a, df_b, ca, cb)
        
        if time_loss > worst_loss:
            worst_loss = time_loss
            worst_corner = i + 1
        
        description = _describe_corner(i + 1, brake_delta, apex_speed_delta, throttle_delta, time_loss,
                                       ca["apex"]["speed"], cb["apex"]["speed"])

        start_dist = min(ca["braking_point"]["distance"], cb["braking_point"]["distance"])
        end_dist = max(ca["full_throttle"]["distance"], cb["full_throttle"]["distance"])

        corner_analyses.append({
            "corner_number": i + 1,
            "braking_delta_meters": round(float(brake_delta), 1),
            "apex_speed_delta_kmh": round(float(apex_speed_delta), 1),
            "throttle_delta_meters": round(float(throttle_delta), 1),
            "time_loss_seconds": round(float(time_loss), 3),
            "description": description,
            "start_distance": round(float(start_dist), 1),
            "end_distance": round(float(end_dist), 1),
            # Datos de referencia
            "ref_brake_distance": round(float(ca["braking_point"]["distance"]), 1),
            "ref_apex_speed": round(float(ca["apex"]["speed"]), 1),
            "ref_apex_distance": round(float(ca["apex"]["distance"]), 1),
            "comp_brake_distance": round(float(cb["braking_point"]["distance"]), 1),
            "comp_apex_speed": round(float(cb["apex"]["speed"]), 1),
            "comp_apex_distance": round(float(cb["apex"]["distance"]), 1),
        })
    
    if use_map:
        corner_analyses, worst_corner, worst_loss = _corners_from_map(df_a, df_b, corner_map)
        num_corners = len(corner_analyses)

    logger.info(f"  Peor curva: #{worst_corner} ({worst_loss:+.3f}s)")
    
    # 4. Construir resultado final
    distance_list = df_a["Distance"].tolist()
    
    result = {
        "summary": {
            "total_time_delta": round(total_time_delta, 3),
            "worst_corner": worst_corner,
            "worst_corner_loss": round(worst_loss, 3),
            "num_corners_analyzed": num_corners,
        },
        "corners": corner_analyses,
        "time_delta_series": {
            "distance": distance_list,
            "delta": [round(float(d), 4) for d in time_delta],
        },
        "speed_comparison": {
            "distance": distance_list,
            "speed_a": df_a["Speed"].round(2).tolist(),
            "speed_b": df_b["Speed"].round(2).tolist(),
        },
        "brake_comparison": {
            "distance": distance_list,
            "brake_a": df_a["Brake"].round(2).tolist(),
            "brake_b": df_b["Brake"].round(2).tolist(),
        },
        "throttle_comparison": {
            "distance": distance_list,
            "throttle_a": df_a["Throttle"].round(2).tolist(),
            "throttle_b": df_b["Throttle"].round(2).tolist(),
        },
    }
    
    logger.info("  ✓ Comparación completada")
    return result
