"""
Módulo de exportación de reportes.

Transforma el resultado de la comparación de vueltas en diferentes formatos
para consumo humano o por API.
"""

import json
import logging

logger = logging.getLogger(__name__)


def export_report_json(comparison_result: dict, filepath: str = None) -> str:
    """
    Serializa el resultado de la comparación a JSON.
    
    Args:
        comparison_result: Diccionario devuelto por compare_laps().
        filepath: Ruta opcional para guardar el archivo. Si None, solo retorna el string.
    
    Returns:
        String JSON formateado.
    """
    json_str = json.dumps(comparison_result, indent=2, ensure_ascii=False)
    
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info(f"  Reporte JSON guardado en: {filepath}")
    
    return json_str


def export_report_text(comparison_result: dict, filepath: str = None) -> str:
    """
    Genera un reporte en texto plano legible para el piloto/ingeniero.
    
    Este es el entregable principal del proyecto: un reporte claro que le dice
    al piloto exactamente dónde y por qué está perdiendo tiempo.
    
    Args:
        comparison_result: Diccionario devuelto por compare_laps().
        filepath: Ruta opcional para guardar el archivo.
    
    Returns:
        String con el reporte formateado.
    """
    summary = comparison_result["summary"]
    corners = comparison_result["corners"]
    metadata = comparison_result.get("metadata", {})
    
    label_a = metadata.get("label_a", "Piloto A")
    label_b = metadata.get("label_b", "Piloto B")
    
    lines = []
    lines.append("=" * 70)
    lines.append("  REPORTE DE COMPARACIÓN DE VUELTAS — EL ANALISTA AUTOMATIZADO")
    lines.append("=" * 70)
    lines.append("")
    
    # Identidad
    if metadata:
        lines.append("─── IDENTIDAD ───")
        lines.append(f"  Vuelta A (Ref): {metadata.get('driver_a', '—')} | {metadata.get('vehicle_a', '—')}")
        lines.append(f"  Vuelta B (Cmp): {metadata.get('driver_b', '—')} | {metadata.get('vehicle_b', '—')}")
        if metadata.get('venue'):
            lines.append(f"  Circuito:       {metadata.get('venue')}")
            
        if not metadata.get("same_vehicle", True):
            lines.append("")
            lines.append("  ⚠️ ADVERTENCIA: Vehículos distintos.")
            lines.append("     Los deltas pueden reflejar diferencias mecánicas, no solo pilotaje.")
        elif not metadata.get("same_driver", True):
            lines.append("")
            lines.append("  ℹ️ INFO: Comparando pilotos en el mismo vehículo.")
            
        lines.append("")
    
    # Resumen general
    delta = summary["total_time_delta"]
    lines.append("─── RESUMEN GENERAL ───")
    lines.append("")
    if delta > 0:
        lines.append(f"  ⏱  {label_b} es {delta:.3f}s MÁS LENTO que {label_a}")
    elif delta < 0:
        lines.append(f"  ⏱  {label_b} es {abs(delta):.3f}s MÁS RÁPIDO que {label_a}")
    else:
        lines.append(f"  ⏱  Tiempos idénticos entre ambos")
    
    lines.append(f"  📊  Curvas analizadas: {summary['num_corners_analyzed']}")
    
    if summary["worst_corner"] > 0:
        lines.append(f"  ⚠️  Peor curva: #{summary['worst_corner']} "
                      f"(pérdida de {summary['worst_corner_loss']:.3f}s)")
    
    lines.append("")
    lines.append("─── ANÁLISIS DETALLADO POR CURVA ───")
    lines.append("")
    
    for corner in corners:
        num = corner["corner_number"]
        lines.append(f"  ┌─ Curva {num} ─────────────────────────────────────────")
        lines.append(f"  │")
        lines.append(f"  │  Punto de frenado:")
        lines.append(f"  │    {label_a}: {corner['ref_brake_distance']:.0f}m")
        lines.append(f"  │    {label_b}: {corner['comp_brake_distance']:.0f}m")
        
        bd = corner["braking_delta_meters"]
        if bd < 0:
            lines.append(f"  │    → Frenó {abs(bd):.0f}m ANTES ❌")
        elif bd > 0:
            lines.append(f"  │    → Frenó {abs(bd):.0f}m DESPUÉS ✅")
        else:
            lines.append(f"  │    → Punto de frenado similar ─")
        
        lines.append(f"  │")
        lines.append(f"  │  Velocidad en Apex:")
        lines.append(f"  │    {label_a}: {corner['ref_apex_speed']:.1f} km/h")
        lines.append(f"  │    {label_b}: {corner['comp_apex_speed']:.1f} km/h")
        
        asd = corner["apex_speed_delta_kmh"]
        if asd < 0:
            lines.append(f"  │    → Fue {abs(asd):.1f} km/h MÁS LENTO ❌")
        elif asd > 0:
            lines.append(f"  │    → Fue {abs(asd):.1f} km/h MÁS RÁPIDO ✅")
        else:
            lines.append(f"  │    → Velocidad similar ─")
        
        lines.append(f"  │")
        
        td = corner["throttle_delta_meters"]
        if abs(td) > 1:
            lines.append(f"  │  Aceleración a fondo:")
            if td > 0:
                lines.append(f"  │    → Aceleró {td:.0f}m DESPUÉS ❌")
            else:
                lines.append(f"  │    → Aceleró {abs(td):.0f}m ANTES ✅")
            lines.append(f"  │")
        
        tl = corner["time_loss_seconds"]
        if tl > 0.01:
            lines.append(f"  │  ⏱  Pérdida en sector: {tl:.3f}s")
        elif tl < -0.01:
            lines.append(f"  │  ⏱  Ganancia en sector: {abs(tl):.3f}s")
        else:
            lines.append(f"  │  ⏱  Sin diferencia significativa")
        
        lines.append(f"  └────────────────────────────────────────────────")
        lines.append("")
    
    lines.append("=" * 70)
    lines.append("  Fin del reporte")
    lines.append("=" * 70)
    
    report = "\n".join(lines)
    
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"  Reporte de texto guardado en: {filepath}")
    
    return report
