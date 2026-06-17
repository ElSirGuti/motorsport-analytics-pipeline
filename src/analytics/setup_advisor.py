"""
Setup Advisor — rule-based engine that translates telemetry metrics into
concrete car setup recommendations with estimated time gains.

Covers: tyre pressures & camber, anti-roll bars, springs & ride height,
dampers, aerodynamic balance, brake cooling, and per-corner focus areas.
"""

import logging
import numpy as np
from src.i18n import _ as t

logger = logging.getLogger(__name__)

_PRIORITY_RANK = {"alta": 0, "media": 1, "baja": 2}

# ── Helpers ───────────────────────────────────────────────────────────────────

_PILOT_NOTE_MAP: dict[str, str] = {
    # Understeer
    "setup_problem_understeer":              "Car is pushing wide — try a later apex and smoother steering inputs",
    "setup_problem_mild_understeer":         "Car is pushing wide — try a later apex and smoother steering inputs",
    "setup_problem_understeer_session":      "Car is pushing wide — try a later apex and smoother steering inputs",
    "setup_problem_mild_understeer_session": "Car is pushing wide — try a later apex and smoother steering inputs",
    # Oversteer
    "setup_problem_oversteer":         "Car is rotating early — be patient on throttle application",
    "setup_problem_oversteer_session": "Car is rotating early — be patient on throttle application",
    # Brake bias / thermal — front heavy
    "setup_problem_thermal_front":  "Brakes feel heavy upfront — bias adjustment will improve feel",
    "setup_problem_front_hotter":   "Brakes feel heavy upfront — bias adjustment will improve feel",
    "setup_problem_fade":           "Brakes feel heavy upfront — bias adjustment will improve feel",
    "setup_problem_brake_fade":     "Brakes feel heavy upfront — bias adjustment will improve feel",
    "setup_problem_fade_zones":     "Brakes feel heavy upfront — bias adjustment will improve feel",
    # Brake bias / thermal — rear heavy
    "setup_problem_thermal_rear": "Rear locking under braking — bias adjustment coming",
    "setup_problem_rear_hotter":  "Rear locking under braking — bias adjustment coming",
    # Pressure / temperature in-window (when a pressure issue IS flagged the note explains it)
    "setup_problem_overheat":      "Tyre feel should be neutral — no pressure adjustment needed",
    "setup_problem_cold":          "Tyre feel should be neutral — no pressure adjustment needed",
    "setup_problem_temp_overheat": "Tyre feel should be neutral — no pressure adjustment needed",
    "setup_problem_temp_cold":     "Tyre feel should be neutral — no pressure adjustment needed",
    # Ride height / bottoming
    "setup_problem_bottoming":         "Setup change incoming — expect different kerb response next lap",
    "setup_problem_bottoming_session": "Setup change incoming — expect different kerb response next lap",
}

_PILOT_NOTE_DEFAULT = "Setup adjustment noted — check feel in next sector"


def _pilot_note_for(problem_key: str) -> str:
    return _PILOT_NOTE_MAP.get(problem_key, _PILOT_NOTE_DEFAULT)


def _rec(category: str, problem: str, root_cause: str, recommendation: str,
         gain_lo: float, gain_hi: float, priority: str,
         detail: str = "", solves: str = "",
         _problem_key: str = "") -> dict:
    return {
        "category":      category,
        "problem":       problem,
        "root_cause":    root_cause,
        "recommendation": recommendation,
        "detail":        detail,
        "solves":        solves,
        "expected_gain": f"{gain_lo:.2f}–{gain_hi:.2f}s/v",
        "gain_lo":       gain_lo,
        "gain_hi":       gain_hi,
        "priority":      priority,
        "pilot_note":    _pilot_note_for(_problem_key),
    }


def _tr(key: str, lang: str = "es", **kwargs) -> str:
    return t(key, lang=lang, **kwargs)


def _rec_t(t_cat, t_prob, t_rc, t_rec, t_det, t_sol,
           gain_lo, gain_hi, priority, lang="es", **t_fmt):
    return _rec(
        category=_tr(t_cat, lang=lang),
        problem=_tr(t_prob, lang=lang, **t_fmt),
        root_cause=_tr(t_rc, lang=lang, **t_fmt),
        recommendation=_tr(t_rec, lang=lang, **t_fmt),
        detail=_tr(t_det, lang=lang, **t_fmt) if t_det else "",
        solves=_tr(t_sol, lang=lang, **t_fmt) if t_sol else "",
        gain_lo=gain_lo, gain_hi=gain_hi, priority=priority,
        _problem_key=t_prob,
    )


def _ratio(a, b, default=1.0):
    return a / b if b and b > 0 else default


# ── Tyre analysis ─────────────────────────────────────────────────────────────

def _analyse_tyres(result: dict, lang: str = "es") -> list:
    tyre = result.get("tyre_analysis") or {}
    if not tyre.get("available"):
        return []
    recs = []

    for lap_key in ("lap_a", "lap_b"):
        corners = {c["corner"]: c for c in tyre.get(lap_key, {}).get("corners", [])}
        if not corners:
            continue

        # Per-tyre: camber from inner/middle/outer gradient
        for pos, c in corners.items():
            inner  = c.get("inner")
            middle = c.get("middle")
            outer  = c.get("outer")
            status = c.get("window_status", "optima")
            surf   = c.get("surface_mean") or 0
            axle   = "Delantero" if pos in ("FL", "FR") else "Trasero"

            # Camber diagnosis (inner vs outer gradient)
            if inner is not None and outer is not None:
                grad = inner - outer
                if grad > 15:
                    recs.append(_rec_t(
                        "setup_cat_camber", "setup_problem_camber_inner_hot",
                        "setup_rc_camber_insufficient", "setup_rec_camber_add",
                        "setup_detail_camber", "setup_solves_camber",
                        gain_lo=0.04, gain_hi=0.18, priority="alta", lang=lang,
                        pos=pos, grad=f"{grad:.0f}", axle=axle.lower(),
                        inner=f"{inner:.0f}", outer=f"{outer:.0f}"
                    ))
                elif grad < -12:
                    recs.append(_rec_t(
                        "setup_cat_camber", "setup_problem_camber_outer_hot",
                        "setup_rc_camber_excess", "setup_rec_camber_reduce",
                        "setup_detail_camber_outer", "setup_solves_camber_outer",
                        gain_lo=0.03, gain_hi=0.15, priority="media", lang=lang,
                        pos=pos, grad=f"{abs(grad):.0f}", axle=axle.lower(),
                        inner=f"{inner:.0f}", outer=f"{outer:.0f}"
                    ))

            # Pressure diagnosis from overall status
            if status == "sobrecalentada":
                recs.append(_rec_t(
                    "setup_cat_pressure", "setup_problem_overheat",
                    "setup_rc_overheat", "setup_rec_pressure_raise",
                    "setup_detail_overheat", "setup_solves_pressure",
                    gain_lo=0.05, gain_hi=0.15, priority="alta", lang=lang,
                    pos=pos, surf=f"{surf:.0f}"
                ))
            elif status == "fria":
                recs.append(_rec_t(
                    "setup_cat_pressure", "setup_problem_cold",
                    "setup_rc_cold", "setup_rec_pressure_lower",
                    "setup_detail_cold", "setup_solves_cold",
                    gain_lo=0.03, gain_hi=0.12, priority="media", lang=lang,
                    pos=pos, surf=f"{surf:.0f}"
                ))

        # Front vs rear thermal balance
        front = [corners[p]["surface_mean"] for p in ("FL", "FR")
                 if p in corners and corners[p].get("surface_mean")]
        rear  = [corners[p]["surface_mean"] for p in ("RL", "RR")
                 if p in corners and corners[p].get("surface_mean")]
        if front and rear:
            f_avg = sum(front) / len(front)
            r_avg = sum(rear)  / len(rear)
            delta = f_avg - r_avg
            if delta > 14:
                recs.append(_rec_t(
                    "setup_cat_thermal_balance", "setup_problem_thermal_front",
                    "setup_rc_thermal_front", "setup_rec_thermal_front",
                    "setup_detail_thermal_front", "setup_solves_thermal_front",
                    gain_lo=0.10, gain_hi=0.30, priority="alta", lang=lang,
                    delta=f"{delta:.0f}", f=f"{f_avg:.0f}", r=f"{r_avg:.0f}"
                ))
            elif delta < -14:
                recs.append(_rec_t(
                    "setup_cat_thermal_balance", "setup_problem_thermal_rear",
                    "setup_rc_thermal_rear", "setup_rec_thermal_rear",
                    "setup_detail_thermal_rear", "setup_solves_thermal_rear",
                    gain_lo=0.10, gain_hi=0.30, priority="alta", lang=lang,
                    delta=f"{abs(delta):.0f}", f=f"{f_avg:.0f}", r=f"{r_avg:.0f}"
                ))

        # Left/right asymmetry
        left  = [corners[p]["surface_mean"] for p in ("FL", "RL")
                 if p in corners and corners[p].get("surface_mean")]
        right = [corners[p]["surface_mean"] for p in ("FR", "RR")
                 if p in corners and corners[p].get("surface_mean")]
        if left and right:
            l_avg = sum(left)  / len(left)
            r_avg = sum(right) / len(right)
            dlr   = l_avg - r_avg
            if abs(dlr) > 12:
                hot  = "izquierdo" if dlr > 0 else "derecho"
                recs.append(_rec_t(
                    "setup_cat_asymmetry", "setup_problem_asymmetry",
                    "setup_rc_asymmetry", "setup_rec_asymmetry",
                    "setup_detail_asymmetry", "setup_solves_asymmetry",
                    gain_lo=0.02, gain_hi=0.08, priority="baja", lang=lang,
                    side=hot, delta=f"{abs(dlr):.0f}"
                ))

    return recs


# ── Brake analysis ────────────────────────────────────────────────────────────

def _analyse_brakes(result: dict, lang: str = "es") -> list:
    brake = result.get("brake_analysis") or {}
    if not brake.get("available"):
        return []
    recs = []

    for suffix, label in [("a", "la vuelta A"), ("b", "la vuelta B")]:
        score    = brake.get(f"score_{suffix}")    or 0
        baseline = brake.get(f"baseline_{suffix}") or 1
        zones    = brake.get(f"fade_zones_{suffix}", [])
        if not zones and not score:
            continue

        deg_pct = (1 - _ratio(score, baseline)) * 100

        if deg_pct > 15:
            prio = "alta" if deg_pct > 30 else "media"
            recs.append(_rec_t(
                "setup_cat_fade", "setup_problem_fade",
                "setup_rc_fade", "setup_rec_fade",
                "setup_detail_fade", "setup_solves_fade",
                gain_lo=0.08, gain_hi=0.25, priority=prio, lang=lang,
                deg=f"{deg_pct:.0f}", label=label,
                baseline=f"{baseline:.4f}", score=f"{score:.4f}"
            ))

        severe = [z for z in zones if z.get("severity", 0) > 0.30]
        if severe:
            worst = max(z["severity"] for z in severe)
            zones_detail = ", ".join(
                f"{z['start']:.0f}–{z['end']:.0f} m (sev. {z['severity']*100:.0f}%)"
                for z in severe
            )
            recs.append(_rec_t(
                "setup_cat_fade_zones", "setup_problem_fade_zones",
                "setup_rc_fade_zones", "setup_rec_fade_zones",
                "setup_detail_fade_zones", "setup_solves_fade_zones",
                gain_lo=0.05, gain_hi=0.20, priority="alta", lang=lang,
                n=len(severe), sev=f"{worst*100:.0f}", label=label,
                zones=zones_detail
            ))

    return recs


# ── Suspension analysis ───────────────────────────────────────────────────────

def _analyse_suspension(result: dict, lang: str = "es") -> list:
    susp = result.get("suspension") or {}
    if not susp.get("available"):
        return []
    recs = []

    for suffix, label in [("a", "vuelta A"), ("b", "vuelta B")]:
        sa = susp.get(f"summary_{suffix}") or {}
        if not sa:
            continue

        roll_f = sa.get("max_roll_f") or 0
        roll_r = sa.get("max_roll_r") or 0
        pitch  = sa.get("max_pitch")  or 0
        m_pitch= sa.get("mean_pitch") or 0
        bots   = susp.get(f"bottoming_{suffix}", [])

        # ARB balance from roll ratio
        if roll_f > 3 and roll_r > 3:
            ratio = _ratio(roll_f, roll_r)
            if ratio > 1.35:
                recs.append(_rec_t(
                    "setup_cat_arb_front", "setup_problem_roll_front",
                    "setup_rc_roll_front", "setup_rec_arb_front",
                    "setup_detail_arb_front", "setup_solves_arb_front",
                    gain_lo=0.06, gain_hi=0.20, priority="media", lang=lang,
                    roll_f=f"{roll_f:.1f}", roll_r=f"{roll_r:.1f}", ratio=f"{ratio:.2f}"
                ))
            elif ratio < 0.75:
                recs.append(_rec_t(
                    "setup_cat_arb_rear", "setup_problem_roll_rear",
                    "setup_rc_roll_rear", "setup_rec_arb_rear",
                    "setup_detail_arb_rear", "setup_solves_arb_rear",
                    gain_lo=0.06, gain_hi=0.20, priority="media", lang=lang,
                    roll_f=f"{roll_f:.1f}", roll_r=f"{roll_r:.1f}", ratio=f"{ratio:.2f}"
                ))

        # Bottoming events
        if bots:
            sev_max = max(b.get("severity", 0) for b in bots)
            prio    = "alta" if sev_max > 0.95 else "media"
            corners_aff = ", ".join(b.get("corner", "?") for b in bots[:4])
            recs.append(_rec_t(
                "setup_cat_ride_height", "setup_problem_bottoming",
                "setup_rc_bottoming", "setup_rec_ride_height",
                "setup_detail_bottoming", "setup_solves_ride_height",
                gain_lo=0.05, gain_hi=0.20, priority=prio, lang=lang,
                n=len(bots), label=label, sev=f"{sev_max*100:.0f}", corners=corners_aff
            ))

        # Pitch under braking
        if pitch > 15:
                recs.append(_rec_t(
                    "setup_cat_pitch", "setup_problem_pitch",
                    "setup_rc_pitch", "setup_rec_pitch",
                    "setup_detail_pitch", "setup_solves_pitch",
                    gain_lo=0.03, gain_hi=0.12, priority="baja", lang=lang,
                    pitch=f"{pitch:.1f}", mean=f"{m_pitch:.1f}", max=f"{pitch:.1f}"
                ))

    return recs


# ── Aerodynamic balance from slip angle ───────────────────────────────────────

def _analyse_slip(result: dict, lang: str = "es") -> list:
    slip = result.get("slip_angle") or {}
    if not slip.get("available"):
        return []
    recs = []

    for suffix, label in [("a", "vuelta A"), ("b", "vuelta B")]:
        sa  = slip.get(f"summary_{suffix}") or {}
        us  = sa.get("understeer_pct") or 0
        os_ = sa.get("oversteer_pct")  or 0
        bm  = sa.get("balance_mean")   or 0

        if us > 60:
            recs.append(_rec_t(
                "setup_cat_aero_balance", "setup_problem_understeer",
                "setup_rc_understeer", "setup_rec_understeer",
                "setup_detail_understeer", "setup_solves_understeer",
                gain_lo=0.12, gain_hi=0.40, priority="alta", lang=lang,
                pct=f"{us:.0f}", label=label, bm=f"{bm:+.1f}"
            ))
        elif os_ > 30:
            recs.append(_rec_t(
                "setup_cat_aero_balance", "setup_problem_oversteer",
                "setup_rc_oversteer", "setup_rec_oversteer",
                "setup_detail_oversteer", "setup_solves_oversteer",
                gain_lo=0.10, gain_hi=0.35, priority="alta", lang=lang,
                pct=f"{os_:.0f}", label=label, bm=f"{bm:+.1f}"
            ))
        elif 2 < bm <= 4 and us > 45:
            recs.append(_rec_t(
                "setup_cat_aero_fine", "setup_problem_mild_understeer",
                "setup_rc_mild_understeer", "setup_rec_mild_understeer",
                "setup_detail_mild_understeer", "setup_solves_mild_understeer",
                gain_lo=0.04, gain_hi=0.12, priority="baja", lang=lang,
                bm=f"{bm:+.1f}", label=label
            ))

    return recs


# ── Driver inputs / damper diagnosis ─────────────────────────────────────────

def _analyse_inputs(result: dict, lang: str = "es") -> list:
    inp = result.get("driver_inputs") or {}
    if not inp.get("available"):
        return []
    recs = []

    for suffix, label in [("a", "vuelta A"), ("b", "vuelta B")]:
        nerv  = inp.get(f"nervousness_score_{suffix}") or 0
        bands = inp.get(f"fft_bands_{suffix}")         or {}
        ov    = inp.get(f"overlap_pct_{suffix}")

        high_freq = bands.get("high", 0)
        mid_freq  = bands.get("mid",  0)

        if nerv > 0.65:
            if high_freq > 0.25:
                recs.append(_rec_t(
                    "setup_cat_dampers", "setup_problem_nervous_high_freq",
                    "setup_rc_nervous_high_freq", "setup_rec_nervous_high_freq",
                    "setup_detail_nervous_high_freq", "setup_solves_damper_rebound",
                    gain_lo=0.05, gain_hi=0.15, priority="media", lang=lang,
                    nerv=f"{nerv*100:.0f}", freq=f"{high_freq*100:.0f}", label=label
                ))
            elif mid_freq > 0.35:
                recs.append(_rec_t(
                    "setup_cat_springs", "setup_problem_nervous_mid_freq",
                    "setup_rc_nervous_mid_freq", "setup_rec_nervous_mid_freq",
                    "setup_detail_nervous_mid_freq", "setup_solves_springs",
                    gain_lo=0.04, gain_hi=0.12, priority="baja", lang=lang,
                    nerv=f"{nerv*100:.0f}", freq=f"{mid_freq*100:.0f}", label=label
                ))
            else:
                recs.append(_rec_t(
                    "setup_cat_mechanical", "setup_problem_nervous_general",
                    "setup_rc_nervous_general", "setup_rec_nervous_general",
                    "setup_detail_nervous_general", "setup_solves_mechanical",
                    gain_lo=0.05, gain_hi=0.20, priority="media", lang=lang,
                    nerv=f"{nerv*100:.0f}", label=label
                ))

        # Overlap brake-throttle: very low → driver not using trail brake
        if ov is not None and ov < 5:
            recs.append(_rec_t(
                "setup_cat_technique", "setup_problem_low_overlap",
                "setup_rc_low_overlap", "setup_rec_low_overlap",
                "setup_detail_low_overlap", "setup_solves_trail_braking",
                gain_lo=0.03, gain_hi=0.10, priority="baja", lang=lang,
                ov=f"{ov:.1f}", label=label
            ))

    return recs


# ── Corner-level analysis ─────────────────────────────────────────────────────

def _analyse_corners(result: dict, lang: str = "es") -> list:
    corners = result.get("corners") or []
    if not corners:
        return []
    recs = []

    # Identify patterns across corners
    brake_early = [c for c in corners
                   if (c.get("braking_delta_meters") or 0) > 10]
    apex_slow   = [c for c in corners
                   if (c.get("apex_speed_delta_kmh") or 0) < -5]
    late_gas    = [c for c in corners
                   if (c.get("throttle_delta_meters") or 0) > 10]

    if len(brake_early) >= 3:
        ns = [c["corner_number"] for c in sorted(brake_early,
              key=lambda c: c.get("braking_delta_meters", 0), reverse=True)[:3]]
        gain_lo_v = 0.05 * len(brake_early)
        gain_hi_v = 0.15 * len(brake_early)
        recs.append(_rec_t(
            "setup_cat_braking", "setup_problem_brake_early",
            "setup_rc_brake_early", "setup_rec_brake_early",
            "setup_detail_brake_early", "setup_solves_brake_early",
            gain_lo=gain_lo_v, gain_hi=gain_hi_v, priority="media", lang=lang,
            n=len(brake_early), corners=f"{ns}",
            gain_lo_str=f"{gain_lo_v:.2f}", gain_hi_str=f"{gain_hi_v:.2f}"
        ))

    if len(apex_slow) >= 2:
        ns = [c["corner_number"] for c in sorted(apex_slow,
              key=lambda c: c.get("apex_speed_delta_kmh", 0))[:3]]
        gain_lo_v = 0.08 * len(apex_slow)
        gain_hi_v = 0.20 * len(apex_slow)
        recs.append(_rec_t(
            "setup_cat_apex_speed", "setup_problem_slow_apex",
            "setup_rc_slow_apex", "setup_rec_slow_apex",
            "setup_detail_slow_apex", "setup_solves_slow_apex",
            gain_lo=gain_lo_v, gain_hi=gain_hi_v, priority="alta", lang=lang,
            n=len(apex_slow), corners=f"{ns}"
        ))

    if len(late_gas) >= 3:
        ns = [c["corner_number"] for c in sorted(late_gas,
              key=lambda c: c.get("throttle_delta_meters", 0), reverse=True)[:3]]
        recs.append(_rec_t(
            "setup_cat_throttle", "setup_problem_late_throttle",
            "setup_rc_late_throttle", "setup_rec_late_throttle",
            "setup_detail_late_throttle", "setup_solves_late_throttle",
            gain_lo=0.04 * len(late_gas), gain_hi=0.12 * len(late_gas),
            priority="media", lang=lang,
            n=len(late_gas), corners=f"{ns}"
        ))

    return recs


# ── Corner priority list ───────────────────────────────────────────────────────

def _corner_priority(result: dict, top_n: int = 8, lang: str = "es") -> list:
    corners = result.get("corners") or []
    ranked = sorted(
        [c for c in corners if abs(c.get("time_loss_seconds") or 0) >= 0.005],
        key=lambda c: abs(c.get("time_loss_seconds") or 0),
        reverse=True
    )[:top_n]

    out = []
    for c in ranked:
        tl  = c.get("time_loss_seconds")    or 0
        bd  = c.get("braking_delta_meters") or 0
        asd = c.get("apex_speed_delta_kmh") or 0
        td  = c.get("throttle_delta_meters")or 0

        # Identify dominant phase
        scores = {
            "frenada": abs(bd) * 0.015,          # ~0.015s per meter of brake delta
            "apex":    abs(asd) * 0.012,          # ~0.012s per km/h of apex speed
            "salida":  abs(td) * 0.010,           # ~0.010s per meter of throttle delta
        }
        phase = max(scores, key=scores.get)
        phase_labels = {
            "frenada": _tr("phase_label_braking", lang=lang),
            "apex":    _tr("phase_label_apex",    lang=lang),
            "salida":  _tr("phase_label_exit",    lang=lang),
        }

        out.append({
            "corner_number":        c.get("corner_number"),
            "time_loss_seconds":    round(tl, 3),
            "braking_delta_meters": round(bd, 1),
            "apex_speed_delta_kmh": round(asd, 1),
            "throttle_delta_meters":round(td, 1),
            "dominant_phase":       phase,
            "focus":                phase_labels[phase],
            "description":          c.get("description", ""),
        })
    return out


# ── Main entry point ──────────────────────────────────────────────────────────

_DOMAIN_LABELS = {
    "tyres":      "Neumáticos",
    "brakes":     "Frenos",
    "suspension": "Suspensión",
    "aero":       "Aerodinámica / Balance",
    "inputs":     "Técnica de Pilotaje",
    "corners":    "Análisis por Curvas",
}


def analizar_setup(result: dict, lang: str = "es") -> dict:
    """
    Analyse all available telemetry sections and return structured setup
    recommendations with priority ordering and estimated time gains.
    Always returns areas_status for every analyzed domain (nominal when no issues found).
    """
    domain_recs = {
        "tyres":      _analyse_tyres(result, lang=lang),
        "brakes":     _analyse_brakes(result, lang=lang),
        "suspension": _analyse_suspension(result, lang=lang),
        "aero":       _analyse_slip(result, lang=lang),
        "inputs":     _analyse_inputs(result, lang=lang),
        "corners":    _analyse_corners(result, lang=lang),
    }

    domains_avail = {
        "tyres":      bool((result.get("tyre_analysis") or {}).get("available")),
        "brakes":     bool((result.get("brake_analysis") or {}).get("available")),
        "suspension": bool((result.get("suspension") or {}).get("available")),
        "aero":       bool((result.get("slip_angle") or {}).get("available")),
        "inputs":     bool((result.get("driver_inputs") or {}).get("available")),
        "corners":    bool(result.get("corners")),
    }

    areas_status = []
    recs = []
    for domain, domain_list in domain_recs.items():
        recs += domain_list
        if not domains_avail[domain]:
            continue
        if domain_list:
            worst = min(domain_list, key=lambda r: _PRIORITY_RANK.get(r["priority"], 9))
            areas_status.append({
                "domain":   domain,
                "label":    _DOMAIN_LABELS[domain],
                "status":   worst["priority"],
                "n_issues": len(domain_list),
            })
        else:
            areas_status.append({
                "domain":   domain,
                "label":    _DOMAIN_LABELS[domain],
                "status":   "nominal",
                "n_issues": 0,
            })

    # De-duplicate by (category + problem) and keep highest-priority version
    seen: dict = {}
    for r in recs:
        key = (r["category"], r["problem"][:40])
        if key not in seen or _PRIORITY_RANK.get(r["priority"], 9) < _PRIORITY_RANK.get(seen[key]["priority"], 9):
            seen[key] = r
    recs = sorted(seen.values(), key=lambda r: _PRIORITY_RANK.get(r["priority"], 9))

    gain_lo = round(sum(r["gain_lo"] for r in recs), 2)
    gain_hi = round(sum(r["gain_hi"] for r in recs), 2)

    logger.info(
        "Setup advisor: %d recomendaciones, ganancia estimada %.2f–%.2f s/v",
        len(recs), gain_lo, gain_hi
    )
    return {
        "available":        bool(recs or areas_status),
        "recommendations":  recs,
        "areas_status":     areas_status,
        "corner_priority":  _corner_priority(result, lang=lang),
        "total_gain_lo":    gain_lo,
        "total_gain_hi":    gain_hi,
        "total_gain_range": f"{gain_lo:.2f}–{gain_hi:.2f}",
    }


# ── Session-level helpers ─────────────────────────────────────────────────────

def _analyse_consistency_sesion(curvas_sesion: dict, lang: str = "es") -> list:
    """Flags corners where technique is inconsistent across laps (high σ)."""
    corners = curvas_sesion.get("corners") or []
    recs = []
    inconsistentes = [c for c in corners if (c.get("std_loss_seconds") or 0) > 0.12]
    if len(inconsistentes) >= 2:
        ns = [
            c["corner_number"]
            for c in sorted(inconsistentes,
                            key=lambda c: c.get("std_loss_seconds", 0), reverse=True)[:3]
        ]
        avg_std = float(np.mean([c["std_loss_seconds"] for c in inconsistentes]))
        gain_lo_v = 0.05 * len(inconsistentes)
        gain_hi_v = 0.15 * len(inconsistentes)
        recs.append(_rec_t(
            "setup_cat_technique", "setup_problem_inconsistent",
            "setup_rc_inconsistent", "setup_rec_inconsistent",
            "setup_detail_inconsistent", "setup_solves_inconsistent",
            gain_lo=gain_lo_v, gain_hi=gain_hi_v, priority="media", lang=lang,
            n=len(inconsistentes), std=f"{avg_std:.2f}",
            corners=f"{ns}", avg_std=f"{avg_std:.3f}"
        ))
    return recs


def _analyse_degradacion_ritmo(degradacion: dict, lang: str = "es") -> list:
    """Generates setup recommendations from degradation trend data."""
    if not degradacion:
        return []
    recs = []
    tasa = degradacion.get("tasa_s_per_lap") or 0.0
    r2   = degradacion.get("r_squared")      or 0.0

    if tasa > 0.20 and r2 > 0.65:
        priority = "alta" if tasa > 0.35 else "media"
        gain_lo_v = round(tasa * 0.25, 3)
        gain_hi_v = round(tasa * 0.55, 3)
        recs.append(_rec_t(
            "setup_cat_degradation", "setup_problem_degradation_high",
            "setup_rc_degradation_high", "setup_rec_degradation_high",
            "setup_detail_degradation_high", "setup_solves_degradation_high",
            gain_lo=gain_lo_v, gain_hi=gain_hi_v, priority=priority, lang=lang,
            tasa=f"{tasa:+.4f}", r2=f"{r2:.2f}",
            gain_lo_str=f"{tasa*0.25:.2f}", gain_hi_str=f"{tasa*0.55:.2f}"
        ))
    elif 0.08 < tasa <= 0.20 and r2 > 0.45:
        recs.append(_rec_t(
            "setup_cat_management", "setup_problem_degradation_moderate",
            "setup_rc_degradation_moderate", "setup_rec_degradation_moderate",
            "setup_detail_degradation_moderate", "setup_solves_degradation_moderate",
            gain_lo=round(tasa * 0.15, 3), gain_hi=round(tasa * 0.35, 3),
            priority="baja", lang=lang,
            tasa=f"{tasa:+.4f}", r2=f"{r2:.3f}"
        ))
    return recs


# ── Session-level entry point ─────────────────────────────────────────────────

def _analyse_tyres_sesion(tel: dict, lang: str = "es") -> list:
    """Tyre temperature analysis from session telemetry aggregates."""
    tyre = tel.get("tyre") or {}
    if not tyre:
        return []
    recs = []
    T_MIN, T_MAX = 80.0, 100.0

    # Per-corner temperature window
    for pos in ("FL", "FR", "RL", "RR"):
        t = tyre.get(pos) or {}
        if "mean_temp" not in t:
            continue
        mean_t = t["mean_temp"]
        axle   = "Delantero" if pos in ("FL", "FR") else "Trasero"
        lado   = "Izquierdo" if pos in ("FL", "RL") else "Derecho"

        if mean_t > T_MAX + 20:
            recs.append(_rec_t(
                "setup_cat_temp", "setup_problem_temp_overheat",
                "setup_rc_temp_overheat", "setup_rec_temp_overheat",
                "setup_detail_temp_overheat", "setup_solves_temp_overheat",
                gain_lo=0.05, gain_hi=0.18, priority="alta", lang=lang,
                pos=pos, axle=axle, side=lado, t=f"{mean_t:.0f}",
                t_min=f"{T_MIN:.0f}", t_max=f"{T_MAX:.0f}",
                delta=f"{mean_t - T_MAX:.0f}",
                max_t=f"{t.get('max_temp', 0):.1f}"
            ))
        elif mean_t < T_MIN - 15:
            recs.append(_rec_t(
                "setup_cat_temp", "setup_problem_temp_cold",
                "setup_rc_temp_cold", "setup_rec_temp_cold",
                "setup_detail_temp_cold", "setup_solves_temp_cold",
                gain_lo=0.04, gain_hi=0.12, priority="media", lang=lang,
                pos=pos, axle=axle, side=lado, t=f"{mean_t:.0f}",
                t_min=f"{T_MIN:.0f}", t_max=f"{T_MAX:.0f}"
            ))

        # Camber diagnosis from inner/outer gradient
        camber_grad = t.get("camber_gradient")
        if camber_grad is not None and abs(camber_grad) > 18:
            if camber_grad > 0:
                recs.append(_rec_t(
                    "setup_cat_camber_specific", "setup_problem_camber_excess",
                    "setup_rc_camber_excess_rc", "setup_rec_camber_excess",
                    "setup_detail_camber_excess", "setup_solves_camber_excess",
                    gain_lo=0.03, gain_hi=0.10, priority="media", lang=lang,
                    pos=pos, grad=f"{camber_grad:.0f}",
                    inner=f"{t.get('inner_mean', 0):.1f}",
                    outer=f"{t.get('outer_mean', 0):.1f}"
                ))
            else:
                recs.append(_rec_t(
                    "setup_cat_camber_specific", "setup_problem_camber_insufficient",
                    "setup_rc_camber_insufficient_rc", "setup_rec_camber_insufficient",
                    "setup_detail_camber_insufficient", "setup_solves_camber_insufficient",
                    gain_lo=0.03, gain_hi=0.10, priority="media", lang=lang,
                    pos=pos, grad=f"{abs(camber_grad):.0f}",
                    inner=f"{t.get('inner_mean', 0):.1f}",
                    outer=f"{t.get('outer_mean', 0):.1f}"
                ))

        # Brake temperature (if available)
        btemp = t.get("brake_temp_mean")
        if btemp and btemp > 750:
            recs.append(_rec_t(
                "setup_cat_brake_temp", "setup_problem_brake_temp",
                "setup_rc_brake_temp", "setup_rec_brake_temp",
                "setup_detail_brake_temp", "setup_solves_brake_temp",
                gain_lo=0.05, gain_hi=0.20,
                priority="alta" if btemp > 900 else "media", lang=lang,
                pos=pos, btemp=f"{btemp:.0f}", bmax=f"{t.get('brake_temp_max', 0):.0f}"
            ))

    # Front/rear thermal balance
    fr_delta = tyre.get("front_rear_delta")
    if fr_delta is not None and abs(fr_delta) > 14:
        if fr_delta > 0:
            recs.append(_rec_t(
                "setup_cat_thermal_axle", "setup_problem_front_hotter",
                "setup_rc_front_hotter", "setup_rec_front_hotter",
                "setup_detail_front_hotter", "setup_solves_front_hotter",
                gain_lo=0.08, gain_hi=0.25, priority="media", lang=lang,
                delta=f"{fr_delta:.0f}"
            ))
        else:
            recs.append(_rec_t(
                "setup_cat_thermal_axle", "setup_problem_rear_hotter",
                "setup_rc_rear_hotter", "setup_rec_rear_hotter",
                "setup_detail_rear_hotter", "setup_solves_rear_hotter",
                gain_lo=0.06, gain_hi=0.20, priority="media", lang=lang,
                delta=f"{abs(fr_delta):.0f}"
            ))

    # Left/right asymmetry
    lr_delta = tyre.get("left_right_delta")
    if lr_delta is not None and abs(lr_delta) > 12:
        lado = "izquierdo" if lr_delta > 0 else "derecho"
        recs.append(_rec_t(
            "setup_cat_lateral_asymmetry", "setup_problem_lateral_asymmetry",
            "setup_rc_lateral_asymmetry", "setup_rec_lateral_asymmetry",
            "setup_detail_lateral_asymmetry", "setup_solves_lateral_asymmetry",
            gain_lo=0.02, gain_hi=0.08, priority="baja", lang=lang,
            side=lado, delta=f"{abs(lr_delta):.0f}"
        ))

    return recs


def _analyse_frenos_sesion(tel: dict, lang: str = "es") -> list:
    """Brake fade analysis from session telemetry aggregates."""
    brake = tel.get("brake") or {}
    if not brake:
        return []
    recs = []

    eff     = brake.get("mean_efficiency",    0)
    min_eff = brake.get("min_efficiency",     0)
    sev     = brake.get("mean_fade_severity", 0)
    fade_p  = brake.get("mean_fade_pct",      0)

    if sev > 0.25 or (eff > 0 and eff < 0.70):
        priority = "alta" if sev > 0.35 else "media"
        recs.append(_rec_t(
            "setup_cat_brake_fade_thermal", "setup_problem_brake_fade",
            "setup_rc_brake_fade", "setup_rec_brake_fade_thermal",
            "setup_detail_brake_fade", "setup_solves_brake_fade",
            gain_lo=0.08, gain_hi=0.30, priority=priority, lang=lang,
            sev=f"{sev*100:.0f}",
            eff=f"{eff:.2f}", min_eff=f"{min_eff:.2f}",
            sev_pct=f"{sev*100:.1f}", fade_pct=f"{fade_p:.1f}"
        ))
    elif sev > 0.10:
        recs.append(_rec_t(
            "setup_cat_brake_thermal_mgmt", "setup_problem_brake_fade_light",
            "setup_rc_brake_fade_light", "setup_rec_brake_fade_light",
            "setup_detail_brake_fade_light", "setup_solves_brake_fade_light",
            gain_lo=0.03, gain_hi=0.10, priority="baja", lang=lang,
            sev=f"{sev*100:.0f}",
            eff=f"{eff:.2f}", sev_pct=f"{sev*100:.1f}"
        ))

    return recs


def _analyse_suspension_sesion(tel: dict, lang: str = "es") -> list:
    """Suspension setup recommendations from session aggregates."""
    susp = tel.get("suspension") or {}
    if not susp:
        return []
    recs = []

    roll_f     = susp.get("mean_roll_f")    or 0
    roll_r     = susp.get("mean_roll_r")    or 0
    roll_ratio = susp.get("roll_ratio")     or 1.0
    pitch      = susp.get("mean_pitch")     or 0
    bev_mean   = susp.get("mean_bottoming_events") or 0
    bev_max    = susp.get("max_bottoming_events")  or 0
    cb         = susp.get("corner_bottoming_pct") or {}

    # Bottoming
    severe_bottoming = {pos: pct for pos, pct in cb.items() if pct > 3.0}
    if severe_bottoming or bev_mean > 0.5:
        priority = "alta" if bev_mean > 1.5 or any(v > 8 for v in severe_bottoming.values()) else "media"
        recs.append(_rec_t(
            "setup_cat_ride_height_bottoming", "setup_problem_bottoming_session",
            "setup_rc_bottoming_session", "setup_rec_bottoming_session",
            "setup_detail_bottoming_session", "setup_solves_bottoming_session",
            gain_lo=0.05, gain_hi=0.25, priority=priority, lang=lang,
            bev=f"{bev_mean:.1f}", bev_max=f"{bev_max}", corners=f"{list(severe_bottoming.keys())}"
        ))

    # ARB balance from roll ratio
    if roll_f and roll_r:
        if roll_ratio > 1.40:
            recs.append(_rec_t(
                "setup_cat_arb_front", "setup_problem_roll_front_excess",
                "setup_rc_roll_front_session", "setup_rec_roll_front_session",
                "setup_detail_roll_front_session", "setup_solves_roll_front_session",
                gain_lo=0.05, gain_hi=0.18, priority="media", lang=lang,
                ratio=f"{roll_ratio:.2f}", roll_f=f"{roll_f:.1f}", roll_r=f"{roll_r:.1f}"
            ))
        elif roll_ratio < 0.70:
            recs.append(_rec_t(
                "setup_cat_arb_rear", "setup_problem_roll_rear_excess",
                "setup_rc_roll_rear_session", "setup_rec_roll_rear_session",
                "setup_detail_roll_rear_session", "setup_solves_roll_rear_session",
                gain_lo=0.05, gain_hi=0.18, priority="media", lang=lang,
                ratio=f"{roll_ratio:.2f}", roll_f=f"{roll_f:.1f}", roll_r=f"{roll_r:.1f}"
            ))

    # Pitch (longitudinal weight transfer)
    if pitch and pitch > 15:
        recs.append(_rec_t(
            "setup_cat_pitch", "setup_problem_pitch_session",
            "setup_rc_pitch_session", "setup_rec_pitch_session",
            "setup_detail_pitch_session", "setup_solves_pitch_session",
            gain_lo=0.03, gain_hi=0.12, priority="baja", lang=lang,
            pitch=f"{pitch:.1f}"
        ))

    return recs


def _analyse_inputs_sesion(tel: dict, lang: str = "es") -> list:
    """Driver inputs / damper diagnosis from session aggregates."""
    inp = tel.get("inputs") or {}
    if not inp:
        return []
    recs = []

    nerv   = inp.get("mean_nervousness") or 0
    fft_h  = inp.get("mean_fft_high")   or 0
    fft_m  = inp.get("mean_fft_mid")    or 0
    ov_pct = inp.get("mean_overlap_pct")

    if nerv > 0.65:
        if fft_h > 0.28:
            recs.append(_rec_t(
                "setup_cat_damper_rebound", "setup_problem_high_freq_steer",
                "setup_rc_high_freq_steer", "setup_rec_high_freq_steer",
                "setup_detail_damper_rebound_session", "setup_solves_damper_rebound_session",
                gain_lo=0.04, gain_hi=0.15, priority="media", lang=lang,
                fft_h=f"{fft_h:.2f}", nerv=f"{nerv:.2f}"
            ))
        if fft_m > 0.38:
            recs.append(_rec_t(
                "setup_cat_springs", "setup_problem_mid_freq_steer",
                "setup_rc_mid_freq_steer", "setup_rec_mid_freq_steer",
                "setup_detail_springs_session", "setup_solves_springs_session",
                gain_lo=0.03, gain_hi=0.10, priority="baja", lang=lang,
                fft_m=f"{fft_m:.2f}"
            ))
    elif nerv > 0.40:
        recs.append(_rec_t(
            "setup_cat_mechanical", "setup_problem_medium_nervous",
            "setup_rc_medium_nervous", "setup_rec_medium_nervous",
            "setup_detail_medium_nervous", "setup_solves_mechanical_session",
            gain_lo=0.02, gain_hi=0.08, priority="baja", lang=lang,
            nerv=f"{nerv:.2f}"
        ))

    if ov_pct is not None and ov_pct < 4.0:
        recs.append(_rec_t(
            "setup_cat_technique", "setup_problem_low_overlap_session",
            "setup_rc_low_overlap_session", "setup_rec_low_overlap_session",
            "setup_detail_low_overlap_session", "setup_solves_trail_braking_session",
            gain_lo=0.04, gain_hi=0.12, priority="baja", lang=lang,
            ov=f"{ov_pct:.1f}"
        ))

    return recs


def _analyse_balance_sesion(tel: dict, lang: str = "es") -> list:
    """Aero/mechanical balance from session LateralG + YawRate aggregates."""
    bal = tel.get("balance") or {}
    if not bal:
        return []
    recs = []

    us_pct = bal.get("mean_understeer_pct") or 0
    os_pct = bal.get("mean_oversteer_pct")  or 0
    bm     = bal.get("balance_mean")        or 0

    if us_pct > 60:
        recs.append(_rec_t(
            "setup_cat_aero_balance", "setup_problem_understeer_session",
            "setup_rc_understeer_session", "setup_rec_understeer_session",
            "setup_detail_understeer_session", "setup_solves_understeer_session",
            gain_lo=0.12, gain_hi=0.40, priority="alta", lang=lang,
            us_pct=f"{us_pct:.0f}", os_pct=f"{os_pct:.0f}", bm=f"{bm:+.3f}"
        ))
    elif os_pct > 30:
        recs.append(_rec_t(
            "setup_cat_aero_balance", "setup_problem_oversteer_session",
            "setup_rc_oversteer_session", "setup_rec_oversteer_session",
            "setup_detail_oversteer_session", "setup_solves_oversteer_session",
            gain_lo=0.10, gain_hi=0.35, priority="alta", lang=lang,
            os_pct=f"{os_pct:.0f}", us_pct=f"{us_pct:.0f}", bm=f"{bm:+.3f}"
        ))
    elif us_pct > 40:
        recs.append(_rec_t(
            "setup_cat_aero_fine", "setup_problem_mild_understeer_session",
            "setup_rc_mild_understeer_session", "setup_rec_mild_understeer_session",
            "setup_detail_mild_understeer_session", "setup_solves_mild_understeer_session",
            gain_lo=0.05, gain_hi=0.15, priority="baja", lang=lang,
            us_pct=f"{us_pct:.0f}", bm=f"{bm:+.3f}"
        ))

    return recs


def analizar_setup_sesion(curvas_sesion: dict, degradacion: dict,
                           telemetria_sesion: dict | None = None,
                           lang: str = "es") -> dict:
    """
    Session-level setup advisor.

    Combines corner-pattern analysis, degradation trend, and full telemetry
    signals (tyre temps, brake fade, suspension, driver inputs, aero balance)
    from session_telemetry_analysis.analizar_telemetria_sesion().

    Args:
        curvas_sesion:     Output of analizar_curvas_sesion().
        degradacion:       Output of analizar_degradacion_stint().
        telemetria_sesion: Output of analizar_telemetria_sesion() — optional but
                           greatly enriches the recommendations.

    Returns:
        Same structure as analizar_setup() — compatible with SetupRecommendations.
    """
    if not curvas_sesion.get("available"):
        return {"available": False}

    pseudo_result = {"corners": curvas_sesion.get("corners", [])}
    tel = telemetria_sesion or {}

    recs: list = []
    recs += _analyse_corners(pseudo_result, lang=lang)
    recs += _analyse_consistency_sesion(curvas_sesion, lang=lang)
    recs += _analyse_degradacion_ritmo(degradacion or {}, lang=lang)
    recs += _analyse_tyres_sesion(tel, lang=lang)
    recs += _analyse_frenos_sesion(tel, lang=lang)
    recs += _analyse_suspension_sesion(tel, lang=lang)
    recs += _analyse_inputs_sesion(tel, lang=lang)
    recs += _analyse_balance_sesion(tel, lang=lang)

    # De-duplicate
    seen: dict = {}
    for r in recs:
        key = (r["category"], r["problem"][:40])
        if key not in seen or (
            _PRIORITY_RANK.get(r["priority"], 9) < _PRIORITY_RANK.get(seen[key]["priority"], 9)
        ):
            seen[key] = r
    recs = sorted(seen.values(), key=lambda r: _PRIORITY_RANK.get(r["priority"], 9))

    gain_lo = round(sum(r["gain_lo"] for r in recs), 2)
    gain_hi = round(sum(r["gain_hi"] for r in recs), 2)

    logger.info(
        "Setup advisor sesión: %d recomendaciones, ganancia estimada %.2f–%.2f s/v "
        "[curvas=%s tyres=%s brake=%s susp=%s inputs=%s balance=%s]",
        len(recs), gain_lo, gain_hi,
        bool(pseudo_result["corners"]),
        bool(tel.get("tyre")), bool(tel.get("brake")),
        bool(tel.get("suspension")), bool(tel.get("inputs")), bool(tel.get("balance")),
    )
    return {
        "available":        bool(recs),
        "recommendations":  recs,
        "corner_priority":  _corner_priority(pseudo_result),
        "total_gain_lo":    gain_lo,
        "total_gain_hi":    gain_hi,
        "total_gain_range": f"{gain_lo:.2f}–{gain_hi:.2f}",
    }
