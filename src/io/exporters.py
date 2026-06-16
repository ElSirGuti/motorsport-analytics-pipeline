"""
Report export module.

Transforms lap comparison results into different formats
for human consumption or API delivery.
"""

import json
import logging
from src.i18n import _ as t

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


def export_report_text(comparison_result: dict, filepath: str = None, lang: str = "es") -> str:
    """
    Generates a plain-text report readable for the driver/engineer.
    Includes all available advanced analysis modules.
    """
    summary  = comparison_result["summary"]
    corners  = comparison_result["corners"]
    metadata = comparison_result.get("metadata", {})

    label_a = metadata.get("label_a", "Vuelta A")
    label_b = metadata.get("label_b", "Vuelta B")

    lines = []
    lines.append("=" * 70)
    lines.append("  " + t("export_header", lang=lang))
    lines.append("=" * 70)
    lines.append("")

    # ── Identity ─────────────────────────────────────────────────────────────
    if metadata:
        lines.append("─── " + t("export_identity", lang=lang) + " ───")
        lines.append(f"  {label_a}: {metadata.get('driver_a', '—')} | {metadata.get('vehicle_a', '—')}")
        lines.append(f"  {label_b}: {metadata.get('driver_b', '—')} | {metadata.get('vehicle_b', '—')}")
        if metadata.get("venue"):
            lines.append(f"  Circuito: {metadata.get('venue')}")
        if not metadata.get("same_vehicle", True):
            lines.append("")
            lines.append("  " + t("export_vehicle_diff_warning", lang=lang))
            lines.append("      " + t("export_vehicle_diff_detail", lang=lang))
        elif not metadata.get("same_driver", True):
            lines.append("  " + t("export_same_vehicle_info", lang=lang))
        lines.append("")

    # ── Synthetic distance warning ───────────────────────────────────
    if metadata.get("distance_synthetic"):
        lines.append("⚠️  " + t("export_synthetic_distance", lang=lang) + " ──────────────────────────────────────────")
        lines.append("  " + t("export_synthetic_distance_msg", lang=lang))
        lines.append("  " + t("export_synthetic_distance_integrated", lang=lang))
        lines.append("  " + t("export_synthetic_distance_error", lang=lang))
        lines.append("  " + t("export_synthetic_distance_no_slip", lang=lang))
        lines.append("─" * 70)
        lines.append("")

    # ── General summary ───────────────────────────────────────────────────────
    delta = summary["total_time_delta"]
    lines.append("─── " + t("export_summary", lang=lang) + " ───")
    lines.append("")
    if delta > 0:
        lines.append("  ⏱  " + t("export_slower", lang=lang, label_b=label_b, delta=f"{delta:.3f}"))
    elif delta < 0:
        lines.append("  ⏱  " + t("export_faster", lang=lang, label_b=label_b, delta=f"{abs(delta):.3f}"))
    else:
        lines.append("  ⏱  " + t("export_identical", lang=lang))
    lines.append("  📊  " + t("export_corners_analyzed", lang=lang, n=summary['num_corners_analyzed']))
    if summary.get("worst_corner", 0) > 0:
        lines.append("  ⚠️  " + t("export_worst_corner", lang=lang,
                                   num=summary['worst_corner'],
                                   loss=f"{summary['worst_corner_loss']:.3f}"))
    lines.append("")

    # ── Tyre Temperature ─────────────────────────────────────────────
    tyre = comparison_result.get("tyre_analysis", {})
    if tyre.get("available"):
        STATUS_ICON = {
            "fria": "🔵", "suboptima": "🔷",
            "optima": "🟢", "caliente": "🟡", "sobrecalentada": "🔴",
        }
        t_min = tyre.get("t_min", 80)
        t_max = tyre.get("t_max", 100)
        lines.append("─── " + t("export_tyre_temp", lang=lang, t_min=t_min, t_max=t_max) + " ───")
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

            # Time in optimal window per corner
            opt_corners = [c["corner"] for c in lap_data["corners"]
                           if c.get("window_status") == "optima"]
            hot_corners = [c["corner"] for c in lap_data["corners"]
                           if c.get("window_status") in ("caliente", "sobrecalentada")]
            cold_corners = [c["corner"] for c in lap_data["corners"]
                            if c.get("window_status") in ("fria", "suboptima")]
            if opt_corners:
                lines.append("    " + t("export_tyre_in_window", lang=lang, corners=", ".join(opt_corners)))
            if hot_corners:
                lines.append("    " + t("export_tyre_hot", lang=lang, corners=", ".join(hot_corners)))
            if cold_corners:
                lines.append("    " + t("export_tyre_cold", lang=lang, corners=", ".join(cold_corners)))
            lines.append("")

    # ── Brake Efficiency ──────────────────────────────────────────────────
    brake = comparison_result.get("brake_analysis", {})
    if brake.get("available"):
        lines.append("─── " + t("export_brake_efficiency", lang=lang) + " ───")
        lines.append("")
        score_a    = brake.get("score_a")
        score_b    = brake.get("score_b")
        baseline_a = brake.get("baseline_a")
        baseline_b = brake.get("baseline_b")

        def _fmt_score(s, bl):
            if s is None:
                return "—"
            degradation = (1 - s / bl) * 100 if bl and bl > 0 else 0
            if abs(degradation) > 3:
                deg_str = "  (" + t("export_brake_degradation", lang=lang, deg=f"{degradation:.1f}") + ")"
            else:
                deg_str = "  (" + t("export_brake_no_fade", lang=lang) + ")"
            return f"{s:.4f} g/%  baseline {bl:.4f}{deg_str}"

        lines.append(f"  {label_a}: {_fmt_score(score_a, baseline_a)}")
        lines.append(f"  {label_b}: {_fmt_score(score_b, baseline_b)}")

        if score_a and score_b and score_b > 0:
            diff_pct = (score_a - score_b) / score_b * 100
            if abs(diff_pct) > 3:
                better = label_a if diff_pct > 0 else label_b
                lines.append("  " + t("export_brake_more_efficient", lang=lang, better=better, diff=f"{abs(diff_pct):.1f}"))

        for lap_key, lap_label in [("fade_zones_a", label_a), ("fade_zones_b", label_b)]:
            zones = brake.get(lap_key, [])
            if zones:
                lines.append("  " + t("export_brake_fade_zones", lang=lang, label=lap_label, n=len(zones)))
                for z in zones:
                    sev = z.get("severity", 0)
                    if sev < 0.15:
                        sev_label = t("export_brake_fade_sev_light", lang=lang)
                    elif sev < 0.30:
                        sev_label = t("export_brake_fade_sev_moderate", lang=lang)
                    else:
                        sev_label = t("export_brake_fade_sev_severe", lang=lang)
                    lines.append(f"    • {z.get('start', 0):.0f}m – {z.get('end', 0):.0f}m  "
                                 f"severidad {sev*100:.0f}%  ({sev_label})")
            else:
                lines.append("  " + t("export_brake_fade_zones_none", lang=lang, label=lap_label))
        lines.append("")

    # ── Driver Inputs ─────────────────────────────────────────────────────
    inputs = comparison_result.get("driver_inputs", {})
    if inputs.get("available"):
        lines.append("─── " + t("export_driver_inputs", lang=lang) + " ───")
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
            lines.append(f"  [{lap_label}]  " + t("export_driver_nervousness", lang=lang, pct=f"{ni*100:.1f}", label=label))
            if bands:
                low  = bands.get("low", 0) * 100
                mid  = bands.get("mid", 0) * 100
                high = bands.get("high", 0) * 100
                high_flag = t("export_driver_fft_flag", lang=lang) if high > 35 else ""
                lines.append("    " + t("export_driver_fft", lang=lang, low=f"{low:.1f}", mid=f"{mid:.1f}", high=f"{high:.1f}", flag=high_flag))
            if overlap is not None:
                overlap_flag = t("export_driver_overlap_flag", lang=lang) if overlap > 12 else ""
                lines.append("    " + t("export_driver_overlap", lang=lang, ov=f"{overlap:.1f}", flag=overlap_flag))
            lines.append("")

        # Direct comparison
        ni_a = inputs.get("nervousness_score_a")
        ni_b = inputs.get("nervousness_score_b")
        if ni_a is not None and ni_b is not None:
            diff = (ni_b - ni_a) * 100
            if abs(diff) > 5:
                more = label_b if diff > 0 else label_a
                lines.append("  " + t("export_driver_more_nervous", lang=lang, more=more, diff=f"{abs(diff):.1f}"))
                lines.append("")

    # ── Suspension ────────────────────────────────────────────────────────────
    susp = comparison_result.get("suspension", {})
    if susp.get("available"):
        lines.append("─── " + t("export_suspension", lang=lang) + " ───")
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
                roll_flag = t("export_suspension_roll_flag", lang=lang) if roll_f > 12 else ""
                lines.append("    " + t("export_suspension_roll", lang=lang, roll_f=f"{roll_f:.1f}", roll_r=f"{roll_r:.1f}", flag=roll_flag))
            if pitch is not None:
                pitch_flag = t("export_suspension_pitch_flag", lang=lang) if pitch > 10 else ""
                lines.append("    " + t("export_suspension_pitch", lang=lang, pitch=f"{pitch:.1f}", mean_pitch=f"{m_pitch:.1f}", flag=pitch_flag))
                if roll_f is not None and roll_r is not None:
                    if abs(roll_f) > abs(roll_r) * 1.3:
                        lines.append("    " + t("export_suspension_oversteer_tendency", lang=lang))
                    elif abs(roll_r) > abs(roll_f) * 1.3:
                        lines.append("    " + t("export_suspension_understeer_tendency", lang=lang))

            bottoming = susp.get(bot_key, [])
            if bottoming:
                lines.append("    " + t("export_suspension_bottoming", lang=lang, n=len(bottoming)))
                for ev in bottoming:
                    sev = ev.get("severity", 0)
                    sev_flag = t("export_suspension_bottoming_critical_flag", lang=lang) if sev > 0.96 else ""
                    lines.append(f"      • {ev.get('corner', '?')}  "
                                 f"{ev.get('start_m', 0):.0f}m – {ev.get('end_m', 0):.0f}m  "
                                 f"sev. {sev*100:.0f}%{sev_flag}")
            else:
                lines.append("    " + t("export_suspension_bottoming_none", lang=lang))
            lines.append("")

    # ── Slip Angle ───────────────────────────────────────────────
    slip = comparison_result.get("slip_angle", {})
    if slip.get("available"):
        lines.append("─── " + t("export_slip_angle", lang=lang) + " ───")
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
                beta_flag = t("export_slip_beta_flag", lang=lang) if beta_max > 6 else ""
                lines.append("    " + t("export_slip_beta", lang=lang, beta_max=f"{beta_max:.1f}", beta_p95=f"{beta_p95:.1f}", flag=beta_flag))
            if bal_mean is not None:
                if bal_mean > 1.5:
                    bal_diag = t("export_slip_balance_understeer", lang=lang, bm=f"{bal_mean:+.1f}")
                elif bal_mean < -1.5:
                    bal_diag = t("export_slip_balance_oversteer", lang=lang, bm=f"{bal_mean:.1f}")
                else:
                    bal_diag = t("export_slip_balance_neutral", lang=lang, bm=f"{bal_mean:+.1f}")
                lines.append("    " + t("export_slip_balance", lang=lang, diag=bal_diag))
            lines.append("    " + t("export_slip_distribution", lang=lang, us=f"{us_pct:.0f}", neu=f"{neu_pct:.0f}", os=f"{os_pct:.0f}"))

            # Automatic diagnosis
            if us_pct > 30:
                lines.append("    " + t("export_slip_chronic_understeer", lang=lang))
            elif os_pct > 20:
                lines.append("    " + t("export_slip_frequent_oversteer", lang=lang))
            lines.append("")

        # Direct comparison if both available
        sa = slip.get("summary_a", {})
        sb = slip.get("summary_b", {})
        if sa.get("beta_max") and sb.get("beta_max"):
            diff_beta = sb["beta_max"] - sa["beta_max"]
            if abs(diff_beta) > 1.0:
                more_slide = label_b if diff_beta > 0 else label_a
                lines.append("  " + t("export_slip_more_slide", lang=lang, more=more_slide, delta=f"{abs(diff_beta):.1f}"))
                lines.append("")

    # ── Detailed corner analysis ──────────────────────────────────────────
    lines.append("─── " + t("export_corner_detail", lang=lang) + " ───")
    lines.append("")

    for corner in corners:
        num = corner["corner_number"]
        tl  = corner.get("time_loss_seconds", 0)
        tl_icon = "⏱  +" if tl > 0.01 else ("⏱  −" if tl < -0.01 else "⏱  ")
        lines.append("  ┌─ " + t("export_corner_header", lang=lang, num=num) + " " + "─" * 47)
        lines.append(f"  │")

        # Braking point
        bd = corner.get("braking_delta_meters", 0)
        ref_brake = corner.get("ref_brake_distance")
        cmp_brake = corner.get("comp_brake_distance")
        lines.append("  │  " + t("export_corner_braking", lang=lang))
        if ref_brake is not None and cmp_brake is not None:
            lines.append(f"  │    {label_a}: {ref_brake:.0f}m   {label_b}: {cmp_brake:.0f}m")
        if bd < -1:
            lines.append("  │    " + t("export_corner_brake_early", lang=lang, delta=f"{abs(bd):.0f}"))
        elif bd > 1:
            lines.append("  │    " + t("export_corner_brake_late", lang=lang, delta=f"{abs(bd):.0f}"))
        else:
            lines.append("  │    " + t("export_corner_brake_similar", lang=lang))

        lines.append(f"  │")

        # Apex speed
        asd = corner.get("apex_speed_delta_kmh", 0)
        ref_apex = corner.get("ref_apex_speed")
        cmp_apex = corner.get("comp_apex_speed")
        lines.append("  │  " + t("export_corner_apex", lang=lang))
        if ref_apex is not None and cmp_apex is not None:
            lines.append(f"  │    {label_a}: {ref_apex:.1f} km/h   {label_b}: {cmp_apex:.1f} km/h")
        if asd < -0.5:
            lines.append("  │    " + t("export_corner_apex_slower", lang=lang, delta=f"{abs(asd):.1f}"))
        elif asd > 0.5:
            lines.append("  │    " + t("export_corner_apex_faster", lang=lang, delta=f"{abs(asd):.1f}"))
        else:
            lines.append("  │    " + t("export_corner_apex_similar", lang=lang))

        td = corner.get("throttle_delta_meters", 0)
        if abs(td) > 1:
            lines.append(f"  │")
            lines.append("  │  Aceleración a fondo:")
            if td > 0:
                lines.append("  │    " + t("export_corner_throttle_late", lang=lang, delta=f"{td:.0f}"))
            else:
                lines.append("  │    " + t("export_corner_throttle_early", lang=lang, delta=f"{abs(td):.0f}"))

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
                lines.append("  │    " + t("export_corner_understeer", lang=lang, sev=underst))
            if overst and overst != "none":
                lines.append("  │    " + t("export_corner_oversteer", lang=lang, sev=overst))

        lines.append(f"  │")
        if tl > 0.01:
            lines.append("  │  " + t("export_corner_gain", lang=lang, time=f"{tl:.3f}"))
        elif tl < -0.01:
            lines.append("  │  " + t("export_corner_loss", lang=lang, time=f"{abs(tl):.3f}"))
        else:
            lines.append("  │  " + t("export_corner_neutral", lang=lang))
        lines.append(f"  └{'─'*53}")
        lines.append("")

    lines.append("=" * 70)
    lines.append("  " + t("export_footer", lang=lang))
    lines.append("=" * 70)

    report = "\n".join(lines)

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"  Reporte de texto guardado en: {filepath}")

    return report
