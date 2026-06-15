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
    Incluye todos los módulos de análisis avanzado disponibles.
    """
    summary  = comparison_result["summary"]
    corners  = comparison_result["corners"]
    metadata = comparison_result.get("metadata", {})

    label_a = metadata.get("label_a", "Vuelta A")
    label_b = metadata.get("label_b", "Vuelta B")

    lines = []
    lines.append("=" * 70)
    lines.append("  REPORTE DE COMPARACIÓN DE VUELTAS — EL ANALISTA AUTOMATIZADO")
    lines.append("=" * 70)
    lines.append("")

    # ── Identidad ─────────────────────────────────────────────────────────────
    if metadata:
        lines.append("─── IDENTIDAD ───")
        lines.append(f"  {label_a}: {metadata.get('driver_a', '—')} | {metadata.get('vehicle_a', '—')}")
        lines.append(f"  {label_b}: {metadata.get('driver_b', '—')} | {metadata.get('vehicle_b', '—')}")
        if metadata.get("venue"):
            lines.append(f"  Circuito: {metadata.get('venue')}")
        if not metadata.get("same_vehicle", True):
            lines.append("")
            lines.append("  ⚠️  ADVERTENCIA: Vehículos distintos.")
            lines.append("      Los deltas pueden reflejar diferencias mecánicas, no solo pilotaje.")
        elif not metadata.get("same_driver", True):
            lines.append("  ℹ️  INFO: Comparando pilotos en el mismo vehículo.")
        lines.append("")

    # ── Advertencia de distancia sintética ───────────────────────────────────
    if metadata.get("distance_synthetic"):
        lines.append("⚠️  ADVERTENCIA DE PRECISIÓN ──────────────────────────────────────────")
        lines.append("  El canal Distance no estaba presente en el CSV original.")
        lines.append("  La distancia fue sintetizada integrando Velocidad × Tiempo.")
        lines.append("  Los deltas de punto de frenada pueden tener un error de ±5–15 m.")
        lines.append("  Los resultados de ángulo de deslizamiento (β) no están disponibles.")
        lines.append("─" * 70)
        lines.append("")

    # ── Resumen general ───────────────────────────────────────────────────────
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
    if summary.get("worst_corner", 0) > 0:
        lines.append(f"  ⚠️  Peor curva: #{summary['worst_corner']} "
                     f"(pérdida de {summary['worst_corner_loss']:.3f}s)")
    lines.append("")

    # ── Temperatura de Neumáticos ─────────────────────────────────────────────
    tyre = comparison_result.get("tyre_analysis", {})
    if tyre.get("available"):
        STATUS_ICON = {
            "fria": "🔵", "suboptima": "🔷",
            "optima": "🟢", "caliente": "🟡", "sobrecalentada": "🔴",
        }
        t_min = tyre.get("t_min", 80)
        t_max = tyre.get("t_max", 100)
        lines.append(f"─── TEMPERATURA DE NEUMÁTICOS (ventana óptima {t_min}–{t_max}°C) ───")
        lines.append("")

        for lap_key, lap_label in [("lap_a", label_a), ("lap_b", label_b)]:
            lap_data = tyre.get(lap_key, {})
            if not lap_data.get("corners"):
                continue
            lines.append(f"  [{lap_label}]")
            for c in lap_data["corners"]:
                icon   = STATUS_ICON.get(c.get("window_status", ""), "  ")
                surf   = c.get("surface_mean")
                core   = c.get("core_mean")
                dt     = c.get("delta_t")
                stress = c.get("high_stress_pct", 0)
                status = c.get("window_status", "—")
                parts  = [f"  {icon} {c['corner']:2s}: {status:14s}"]
                if surf is not None:
                    parts.append(f"Sup {surf:.1f}°C")
                if core is not None:
                    parts.append(f"Núcleo {core:.1f}°C")
                if dt is not None:
                    stress_flag = "  ⚠️ estrés térmico" if stress > 20 else ""
                    parts.append(f"ΔT {dt:.1f}°C  (estrés {stress:.0f}%){stress_flag}")
                lines.append("    " + "  |  ".join(parts))

            # Tiempo en ventana óptima por corner
            opt_corners = [c["corner"] for c in lap_data["corners"]
                           if c.get("window_status") == "optima"]
            hot_corners = [c["corner"] for c in lap_data["corners"]
                           if c.get("window_status") in ("caliente", "sobrecalentada")]
            cold_corners = [c["corner"] for c in lap_data["corners"]
                            if c.get("window_status") in ("fria", "suboptima")]
            if opt_corners:
                lines.append(f"    ✓ En ventana: {', '.join(opt_corners)}")
            if hot_corners:
                lines.append(f"    ⚠️ Caliente/Sobrecalentado: {', '.join(hot_corners)}")
            if cold_corners:
                lines.append(f"    ℹ️ Frío/Subóptimo: {', '.join(cold_corners)}")
            lines.append("")

    # ── Eficiencia de Frenos ──────────────────────────────────────────────────
    brake = comparison_result.get("brake_analysis", {})
    if brake.get("available"):
        lines.append("─── EFICIENCIA DE FRENOS ───")
        lines.append("")
        score_a    = brake.get("score_a")
        score_b    = brake.get("score_b")
        baseline_a = brake.get("baseline_a")
        baseline_b = brake.get("baseline_b")

        def _fmt_score(s, bl):
            if s is None:
                return "—"
            degradation = (1 - s / bl) * 100 if bl and bl > 0 else 0
            deg_str = f"  ({degradation:.1f}% bajo baseline)" if abs(degradation) > 3 else "  (sin fade)"
            return f"{s:.4f} g/%  baseline {bl:.4f}{deg_str}"

        lines.append(f"  {label_a}: {_fmt_score(score_a, baseline_a)}")
        lines.append(f"  {label_b}: {_fmt_score(score_b, baseline_b)}")

        if score_a and score_b and score_b > 0:
            diff_pct = (score_a - score_b) / score_b * 100
            if abs(diff_pct) > 3:
                better = label_a if diff_pct > 0 else label_b
                lines.append(f"  → {better} frena {abs(diff_pct):.1f}% más eficientemente")

        for lap_key, lap_label in [("fade_zones_a", label_a), ("fade_zones_b", label_b)]:
            zones = brake.get(lap_key, [])
            if zones:
                lines.append(f"  Zonas de fade {lap_label}: {len(zones)}")
                for z in zones:
                    sev = z.get("severity", 0)
                    sev_label = "leve" if sev < 0.15 else ("moderado" if sev < 0.30 else "severo ⚠️")
                    lines.append(f"    • {z.get('start', 0):.0f}m – {z.get('end', 0):.0f}m  "
                                 f"severidad {sev*100:.0f}%  ({sev_label})")
            else:
                lines.append(f"  Zonas de fade {lap_label}: ninguna ✓")
        lines.append("")

    # ── Inputs del Piloto ─────────────────────────────────────────────────────
    inputs = comparison_result.get("driver_inputs", {})
    if inputs.get("available"):
        lines.append("─── INPUTS DEL PILOTO ───")
        lines.append("")
        for score_key, bands_key, label_key, overlap_key, lap_label in [
            ("nervousness_score_a", "fft_bands_a", "nervousness_label_a", "overlap_pct_a", label_a),
            ("nervousness_score_b", "fft_bands_b", "nervousness_label_b", "overlap_pct_b", label_b),
        ]:
            ni     = inputs.get(score_key)
            bands  = inputs.get(bands_key, {})
            label  = inputs.get(label_key, "—")
            overlap = inputs.get(overlap_key)

            if ni is None:
                continue
            lines.append(f"  [{lap_label}]  Nerviosismo: {ni*100:.1f}%  → {label}")
            if bands:
                low  = bands.get("low", 0) * 100
                mid  = bands.get("mid", 0) * 100
                high = bands.get("high", 0) * 100
                high_flag = "  ⚠️ muchas micro-correcciones" if high > 35 else ""
                lines.append(f"    FFT: Baja {low:.1f}%  |  Media {mid:.1f}%  |  Alta {high:.1f}%{high_flag}")
            if overlap is not None:
                overlap_flag = "  ⚠️ solapamiento alto" if overlap > 12 else ""
                lines.append(f"    Solapamiento freno-gas: {overlap:.1f}%{overlap_flag}")
            lines.append("")

        # Comparación directa
        ni_a = inputs.get("nervousness_score_a")
        ni_b = inputs.get("nervousness_score_b")
        if ni_a is not None and ni_b is not None:
            diff = (ni_b - ni_a) * 100
            if abs(diff) > 5:
                more = label_b if diff > 0 else label_a
                lines.append(f"  → {more} es {abs(diff):.1f}% más nervioso/a al volante")
                lines.append("")

    # ── Suspensión ────────────────────────────────────────────────────────────
    susp = comparison_result.get("suspension", {})
    if susp.get("available"):
        lines.append("─── SUSPENSIÓN (Pitch / Roll / Bottoming) ───")
        lines.append("")
        for sum_key, bot_key, lap_label in [
            ("summary_a", "bottoming_a", label_a),
            ("summary_b", "bottoming_b", label_b),
        ]:
            s = susp.get(sum_key, {})
            if not s:
                continue
            lines.append(f"  [{lap_label}]")
            roll_f = s.get("max_roll_f")
            roll_r = s.get("max_roll_r")
            pitch  = s.get("max_pitch")
            m_pitch = s.get("mean_pitch")
            if roll_f is not None:
                roll_flag = "  ⚠️ roll excesivo" if roll_f > 12 else ""
                lines.append(f"    Roll máx. delantero: {roll_f:.1f} mm  |  trasero: {roll_r:.1f} mm{roll_flag}")
            if pitch is not None:
                pitch_flag = "  ⚠️ pitch pronunciado" if pitch > 10 else ""
                lines.append(f"    Pitch máximo: {pitch:.1f} mm  |  medio: {m_pitch:.1f} mm{pitch_flag}")
                if roll_f is not None and roll_r is not None:
                    if abs(roll_f) > abs(roll_r) * 1.3:
                        lines.append(f"    ↳ Eje trasero más rígido en roll → tendencia a sobreviraje")
                    elif abs(roll_r) > abs(roll_f) * 1.3:
                        lines.append(f"    ↳ Eje delantero más rígido en roll → tendencia a subviraje")

            bottoming = susp.get(bot_key, [])
            if bottoming:
                lines.append(f"    Bottoming: {len(bottoming)} evento(s)")
                for ev in bottoming:
                    sev = ev.get("severity", 0)
                    sev_flag = "  ⚠️ crítico" if sev > 0.96 else ""
                    lines.append(f"      • {ev.get('corner', '?')}  "
                                 f"{ev.get('start_m', 0):.0f}m – {ev.get('end_m', 0):.0f}m  "
                                 f"sev. {sev*100:.0f}%{sev_flag}")
            else:
                lines.append(f"    Bottoming: ninguno ✓")
            lines.append("")

    # ── Ángulo de Deslizamiento ───────────────────────────────────────────────
    slip = comparison_result.get("slip_angle", {})
    if slip.get("available"):
        lines.append("─── ÁNGULO DE DESLIZAMIENTO (Sideslip β) ───")
        lines.append("")
        for sum_key, lap_label in [("summary_a", label_a), ("summary_b", label_b)]:
            s = slip.get(sum_key, {})
            if not s:
                continue
            beta_max = s.get("beta_max")
            beta_p95 = s.get("beta_p95")
            us_pct   = s.get("understeer_pct", 0)
            os_pct   = s.get("oversteer_pct", 0)
            neu_pct  = s.get("neutral_pct", 0)
            bal_mean = s.get("balance_mean", 0)

            lines.append(f"  [{lap_label}]")
            if beta_max is not None:
                beta_flag = "  ⚠️ deslizamiento elevado" if beta_max > 6 else ""
                lines.append(f"    β máximo: {beta_max:.1f}°  |  β P95: {beta_p95:.1f}°{beta_flag}")
            if bal_mean is not None:
                if bal_mean > 1.5:
                    bal_diag = f"tendencia a SUBVIRAR  (+{bal_mean:.1f}°)"
                elif bal_mean < -1.5:
                    bal_diag = f"tendencia a SOBREVIRAJE  ({bal_mean:.1f}°)"
                else:
                    bal_diag = f"balance neutro  ({bal_mean:+.1f}°)"
                lines.append(f"    Balance medio: {bal_diag}")
            lines.append(f"    Distribución:  Subviraje {us_pct:.0f}%  |  "
                         f"Neutral {neu_pct:.0f}%  |  Sobreviraje {os_pct:.0f}%")

            # Diagnóstico automático
            if us_pct > 30:
                lines.append(f"    ↳ ⚠️  Subviraje crónico — revisar presión delantera o barra ant.")
            elif os_pct > 20:
                lines.append(f"    ↳ ⚠️  Sobreviraje frecuente — revisar diff o temperatura trasera")
            lines.append("")

        # Comparación directa si ambas disponibles
        sa = slip.get("summary_a", {})
        sb = slip.get("summary_b", {})
        if sa.get("beta_max") and sb.get("beta_max"):
            diff_beta = sb["beta_max"] - sa["beta_max"]
            if abs(diff_beta) > 1.0:
                more_slide = label_b if diff_beta > 0 else label_a
                lines.append(f"  → {more_slide} tiene {abs(diff_beta):.1f}° más de deslizamiento máximo")
                lines.append("")

    # ── Análisis detallado por curva ──────────────────────────────────────────
    lines.append("─── ANÁLISIS DETALLADO POR CURVA ───")
    lines.append("")

    for corner in corners:
        num = corner["corner_number"]
        tl  = corner.get("time_loss_seconds", 0)
        tl_icon = "⏱  +" if tl > 0.01 else ("⏱  −" if tl < -0.01 else "⏱  ")
        lines.append(f"  ┌─ Curva {num} {'─'*47}")
        lines.append(f"  │")

        # Braking point — detailed if basic format, delta-only if advanced format
        bd = corner.get("braking_delta_meters", 0)
        ref_brake = corner.get("ref_brake_distance")
        cmp_brake = corner.get("comp_brake_distance")
        lines.append(f"  │  Punto de frenado:")
        if ref_brake is not None and cmp_brake is not None:
            lines.append(f"  │    {label_a}: {ref_brake:.0f}m   {label_b}: {cmp_brake:.0f}m")
        if bd < -1:
            lines.append(f"  │    → Frenó {abs(bd):.0f}m ANTES ❌  (deja tiempo sobre la mesa)")
        elif bd > 1:
            lines.append(f"  │    → Frenó {abs(bd):.0f}m DESPUÉS ✅  (frenada más tardía)")
        else:
            lines.append(f"  │    → Punto de frenado similar ─")

        lines.append(f"  │")

        # Apex speed — detailed if basic format, delta-only if advanced format
        asd = corner.get("apex_speed_delta_kmh", 0)
        ref_apex = corner.get("ref_apex_speed")
        cmp_apex = corner.get("comp_apex_speed")
        lines.append(f"  │  Velocidad en Apex:")
        if ref_apex is not None and cmp_apex is not None:
            lines.append(f"  │    {label_a}: {ref_apex:.1f} km/h   {label_b}: {cmp_apex:.1f} km/h")
        if asd < -0.5:
            lines.append(f"  │    → {abs(asd):.1f} km/h MÁS LENTO en apex ❌  "
                         f"(entrada más conservadora o subviraje)")
        elif asd > 0.5:
            lines.append(f"  │    → {abs(asd):.1f} km/h MÁS RÁPIDO en apex ✅")
        else:
            lines.append(f"  │    → Velocidad en apex similar ─")

        td = corner.get("throttle_delta_meters", 0)
        if abs(td) > 1:
            lines.append(f"  │")
            lines.append(f"  │  Aceleración a fondo:")
            if td > 0:
                lines.append(f"  │    → Aceleró {td:.0f}m DESPUÉS ❌  (salida más conservadora)")
            else:
                lines.append(f"  │    → Aceleró {abs(td):.0f}m ANTES ✅  (salida más agresiva)")

        # Advanced insight description (from insights module)
        desc = corner.get("description", "")
        if desc:
            lines.append(f"  │")
            lines.append(f"  │  📋 {desc}")

        # Dynamic diagnosis (from dynamics module)
        diag = corner.get("diagnostics", {})
        if diag:
            underst = diag.get("understeer_severity")
            overst  = diag.get("oversteer_severity")
            if underst and underst != "none":
                lines.append(f"  │    ⚠️  Subviraje detectado ({underst})")
            if overst and overst != "none":
                lines.append(f"  │    ⚠️  Sobreviraje detectado ({overst})")

        lines.append(f"  │")
        if tl > 0.01:
            lines.append(f"  │  {tl_icon}{tl:.3f}s  pérdida en sector")
        elif tl < -0.01:
            lines.append(f"  │  {tl_icon}{abs(tl):.3f}s  ganancia en sector")
        else:
            lines.append(f"  │  {tl_icon}Sin diferencia significativa")
        lines.append(f"  └{'─'*53}")
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
