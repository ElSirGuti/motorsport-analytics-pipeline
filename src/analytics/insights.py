"""
Módulo de Extracción de Insights Automatizados.

Este módulo actúa como el "Ingeniero de Pista de IA". Analiza la telemetría
alineada en ventanas alrededor de cada curva (Apex) para identificar errores
críticos de conducción mediante reglas heurísticas de competición.

Métricas doradas extraídas:
  1. Braking Point Delta: Diferencia en metros del punto inicial de frenada.
  2. V-Min Delta: Diferencia en la velocidad mínima de paso por curva.
  3. Throttle Application Delta: Diferencia en metros para volver al 100% de gas.
"""

import logging
import pandas as pd
import numpy as np
from src.i18n import _ as t

logger = logging.getLogger(__name__)

# Corner window around each apex (metres). The exit is long because most of the
# time lost in a corner is lost on the acceleration phase after the apex.
CORNER_WINDOW_BEFORE_M = 100.0
CORNER_WINDOW_AFTER_M = 200.0

def _insights_from_map(df_alineado: pd.DataFrame, corner_map: dict, lang: str = "es") -> list[dict]:
    """
    Same report as ``analizar_errores_por_curva`` but for the corners of the unified corner map: the
    window of each corner is the map's ``start_m`` .. ``end_m`` (disjoint by construction), the number and
    the name are the map's, and corners of kind flat_out / kink report the time lost in their window but
    no braking point, apex speed or throttle application (``*_available`` False, values 0.0).
    All the fields of the classic report are kept; the map fields are added.
    """
    from src.analytics.corner_metrics import first_onset, is_flat, neighbours
    corners = corner_map["corners"]
    reporte: list[dict] = []
    if not corners or df_alineado.empty:
        return reporte
    has_brake = 'Brake_Fast' in df_alineado.columns and 'Brake_Slow' in df_alineado.columns
    has_throttle = 'Throttle_Fast' in df_alineado.columns and 'Throttle_Slow' in df_alineado.columns
    dist_all = df_alineado['Distance'].values
    bf = bs = tf = ts = None
    if has_brake:
        bf = pd.to_numeric(df_alineado['Brake_Fast'], errors='coerce').fillna(0).values
        bs = pd.to_numeric(df_alineado['Brake_Slow'], errors='coerce').fillna(0).values
    if has_throttle:
        tf = pd.to_numeric(df_alineado['Throttle_Fast'], errors='coerce').fillna(0).values
        ts = pd.to_numeric(df_alineado['Throttle_Slow'], errors='coerce').fillna(0).values
    delta = df_alineado['Delta_Time'].values
    sp_f = df_alineado['Speed_Fast'].values
    sp_s = df_alineado['Speed_Slow'].values
    for c, (prev_apex, next_apex) in zip(corners, neighbours(corners)):
        apex = float(c["apex_distance_m"])
        w_start, w_end = float(c["start_m"]), float(c["end_m"])
        sel = np.where((dist_all >= w_start) & (dist_all <= w_end))[0]
        if len(sel) < 10:
            continue
        flat = is_flat(c)
        delta_entrada = float(delta[sel[-1]] - delta[sel[0]])
        v_delta = float(sp_f[sel].min() - sp_s[sel].min())
        brake_delta_m, brake_available = 0.0, False
        throttle_delta_m, throttle_available = 0.0, False
        if not flat:
            if has_brake:
                lo = max(apex - 300.0, prev_apex) if prev_apex is not None else apex - 300.0
                pos = np.where((dist_all >= lo) & (dist_all <= apex))[0]
                i_f, i_s = first_onset(bf, pos, 5.0), first_onset(bs, pos, 5.0)
                if i_f is not None and i_s is not None:
                    # positive if Slow brakes EARLIER (further from the apex)
                    brake_delta_m = float((apex - dist_all[i_s]) - (apex - dist_all[i_f]))
                    brake_available = True
            if has_throttle:
                hi = min(apex + 300.0, next_apex) if next_apex is not None else apex + 300.0
                pos = np.where((dist_all >= apex) & (dist_all <= hi))[0]
                gf, gs = pos[tf[pos] > 95.0], pos[ts[pos] > 95.0]
                if len(gf) and len(gs):
                    # positive if Slow gets back to full throttle LATER
                    throttle_delta_m = float(dist_all[gs[0]] - dist_all[gf[0]])
                    throttle_available = True
        is_loss = delta_entrada > 0.05
        if flat:
            if is_loss:
                diagnostico = t("insight_flat_out_loss", lang=lang, delta=f"{delta_entrada:.3f}")
            elif delta_entrada < -0.05:
                diagnostico = t("insight_excellent", lang=lang, delta=f"{abs(delta_entrada):.3f}")
            else:
                diagnostico = t("insight_optimal", lang=lang)
        elif is_loss:
            if v_delta > 3.0 and brake_delta_m > 10.0:
                diagnostico = t("insight_brake_early", lang=lang, brake_delta=f"{brake_delta_m:.1f}", v_delta=f"{v_delta:.1f}")
            elif brake_delta_m < -5.0 and throttle_delta_m > 10.0:
                diagnostico = t("insight_overdriving", lang=lang, brake_delta=f"{abs(brake_delta_m):.1f}", throttle_delta=f"{throttle_delta_m:.1f}")
            elif v_delta > 5.0:
                diagnostico = t("insight_slow_apex", lang=lang, v_delta=f"{v_delta:.1f}")
            elif throttle_delta_m > 15.0:
                diagnostico = t("insight_late_throttle", lang=lang, throttle_delta=f"{throttle_delta_m:.1f}")
            else:
                diagnostico = t("insight_general_loss", lang=lang, delta=f"{delta_entrada:.3f}")
        elif delta_entrada < -0.05:
            diagnostico = t("insight_excellent", lang=lang, delta=f"{abs(delta_entrada):.3f}")
        else:
            diagnostico = t("insight_optimal", lang=lang)
        reporte.append({
            'corner_number': int(c["number"]),
            'start_distance': round(w_start, 1),
            'end_distance': round(w_end, 1),
            'apex_distance': apex,
            'time_loss_seconds': round(delta_entrada, 3),
            'apex_speed_delta_kmh': 0.0 if flat else round(-v_delta, 1),
            'braking_delta_meters': round(brake_delta_m, 1),
            'throttle_delta_meters': round(throttle_delta_m, 1),
            'braking_delta_available': bool(brake_available),
            'throttle_delta_available': bool(throttle_available),
            'apex_delta_available': not flat,
            'description': diagnostico,
            # unified corner map fields (additive)
            'number': int(c["number"]), 'name': c.get("name"), 'corner_name': c.get("name"),
            'kind': c.get("kind"), 'direction': c.get("direction"), 'min_radius_m': c.get("min_radius_m"),
            'flat_out_share': c.get("flat_out_share"), 'confidence': c.get("confidence"),
            'is_complex': bool(c.get("is_complex")),
        })
    logger.info(f"  ✓ {len(reporte)} insights generados (corner map)")
    return reporte


def analizar_errores_por_curva(df_alineado: pd.DataFrame, df_apexes: pd.DataFrame, lang: str = "es",
                               corner_map: dict | None = None) -> list[dict]:
    """
    Analiza la telemetría en ventanas alrededor de cada Apex para generar
    diagnósticos técnicos automatizados sobre el rendimiento en cada curva.

    Args:
        df_alineado: DataFrame con telemetría de ambas vueltas alineada por distancia.
                     Requiere: Distance, Speed_Fast, Speed_Slow, Delta_Time,
                               Brake_Fast, Brake_Slow, Throttle_Fast, Throttle_Slow.
        df_apexes: DataFrame con las ubicaciones de los Apex (Distance, Curvature).
        corner_map: mapa unificado de curvas (``corner_map.build_corner_map``, con las posiciones ya
                    escaladas a esta vuelta). Si se da, las curvas, su numeración, nombres y ventanas son
                    las del mapa (ver ``_insights_from_map``); si no, el camino clásico por apexes.

    Returns:
        Lista de diccionarios con los insights y métricas de cada curva.
    """
    if corner_map and corner_map.get("corners"):
        return _insights_from_map(df_alineado, corner_map, lang)
    reporte_insights = []
    
    if df_apexes.empty or df_alineado.empty:
        return reporte_insights

    logger.info("🧠 Generando insights automatizados por curva...")

    # Asegurarnos de que las columnas de pedales existan (pueden faltar en algunos CSVs)
    has_brake = 'Brake_Fast' in df_alineado.columns and 'Brake_Slow' in df_alineado.columns
    has_throttle = 'Throttle_Fast' in df_alineado.columns and 'Throttle_Slow' in df_alineado.columns

    apex_dists = sorted(float(d) for d in df_apexes['Distance'].values)
    dist_all = df_alineado['Distance'].values
    brake_thr = 5.0
    gas_thr = 95.0

    def _first_onset(series, mask_idx, thr):
        """Start of the main braking zone: walk back from the peak brake sample while
        the pedal stays above `thr`. None if there is no braking or it began before
        the search window (censored)."""
        if len(mask_idx) < 2:
            return None
        vals = series[mask_idx]
        j = int(np.argmax(vals))
        if vals[j] <= thr:
            return None
        while j > 0 and vals[j - 1] > thr:
            j -= 1
        if j == 0 and vals[0] > thr:
            return None
        return int(mask_idx[j])

    for idx, d_apex in enumerate(apex_dists):
        curva_num = idx + 1
        metro_apex = d_apex
        prev_apex = apex_dists[idx - 1] if idx > 0 else None
        next_apex = apex_dists[idx + 1] if idx + 1 < len(apex_dists) else None

        # Ventana de análisis: 100 m antes y 200 m después del apex, recortada en el
        # punto medio con los apexes vecinos para que las ventanas NO se solapen
        # (si no, la pérdida de tiempo de curvas cercanas se contaría dos veces).
        w_start = metro_apex - CORNER_WINDOW_BEFORE_M
        w_end = metro_apex + CORNER_WINDOW_AFTER_M
        if prev_apex is not None:
            w_start = max(w_start, (prev_apex + metro_apex) / 2.0)
        if next_apex is not None:
            w_end = min(w_end, (metro_apex + next_apex) / 2.0)
        ventana = df_alineado[(df_alineado['Distance'] >= w_start) &
                              (df_alineado['Distance'] <= w_end)]

        if len(ventana) < 10:
            continue

        # 1. Delta de tiempo específico perdido SOLO en esta curva
        delta_entrada = ventana['Delta_Time'].iloc[-1] - ventana['Delta_Time'].iloc[0]

        # 2. Velocidad mínima en vértice (V-Min Delta)
        v_min_fast = ventana['Speed_Fast'].min()
        v_min_slow = ventana['Speed_Slow'].min()
        v_delta = v_min_fast - v_min_slow  # Positivo si Fast fue más rápido en curva

        # 3. Punto de Frenada (Braking Point Delta)
        # La búsqueda usa una ventana más amplia que la de pérdida de tiempo (hasta
        # 300 m antes del apex, acotada por el apex anterior) y localiza el INICIO de
        # la zona de frenada principal (el pico de freno antes del apex). Antes se tomaba la primera
        # muestra con freno dentro de 100 m: si la frenada empezaba antes, ambas
        # vueltas daban 100 m y el delta salía artificialmente 0.
        brake_delta_m = 0.0
        brake_available = False
        if has_brake:
            lo = max(metro_apex - 300, prev_apex) if prev_apex is not None else metro_apex - 300
            pos = np.where((dist_all >= lo) & (dist_all <= metro_apex))[0]
            bf = pd.to_numeric(df_alineado['Brake_Fast'], errors='coerce').fillna(0).values
            bs = pd.to_numeric(df_alineado['Brake_Slow'], errors='coerce').fillna(0).values
            i_f = _first_onset(bf, pos, brake_thr)
            i_s = _first_onset(bs, pos, brake_thr)
            if i_f is not None and i_s is not None:
                # Positivo si Slow frena ANTES (más lejos del apex), Negativo si frena DESPUÉS
                brake_delta_m = float((metro_apex - dist_all[i_s]) - (metro_apex - dist_all[i_f]))
                brake_available = True

        # 4. Fase de Retorno al Gas (Throttle Application Delta)
        # Metros tras el apex hasta el gas a fondo (> 95 %), buscando hasta el apex
        # siguiente (o 300 m); 0 m si ya se iba a fondo en el apex.
        throttle_delta_m = 0.0
        throttle_available = False
        if has_throttle:
            hi = min(metro_apex + 300, next_apex) if next_apex is not None else metro_apex + 300
            pos = np.where((dist_all >= metro_apex) & (dist_all <= hi))[0]
            tf = pd.to_numeric(df_alineado['Throttle_Fast'], errors='coerce').fillna(0).values
            ts = pd.to_numeric(df_alineado['Throttle_Slow'], errors='coerce').fillna(0).values
            gf = pos[tf[pos] > gas_thr]
            gs = pos[ts[pos] > gas_thr]
            if len(gf) and len(gs):
                # Positivo si Slow da gas DESPUÉS (más lejos del apex), Negativo si da gas ANTES
                throttle_delta_m = float(dist_all[gs[0]] - dist_all[gf[0]])
                throttle_available = True

        # 5. Lógica predictiva / Heurística de coaching
        diagnostico = ""
        is_loss = delta_entrada > 0.05
        
        if is_loss:
            if v_delta > 3.0 and brake_delta_m > 10.0:
                diagnostico = t("insight_brake_early", lang=lang, brake_delta=f"{brake_delta_m:.1f}", v_delta=f"{v_delta:.1f}")
            elif brake_delta_m < -5.0 and throttle_delta_m > 10.0:
                diagnostico = t("insight_overdriving", lang=lang, brake_delta=f"{abs(brake_delta_m):.1f}", throttle_delta=f"{throttle_delta_m:.1f}")
            elif v_delta > 5.0:
                diagnostico = t("insight_slow_apex", lang=lang, v_delta=f"{v_delta:.1f}")
            elif throttle_delta_m > 15.0:
                diagnostico = t("insight_late_throttle", lang=lang, throttle_delta=f"{throttle_delta_m:.1f}")
            else:
                diagnostico = t("insight_general_loss", lang=lang, delta=f"{delta_entrada:.3f}")
        elif delta_entrada < -0.05:
             diagnostico = t("insight_excellent", lang=lang, delta=f"{abs(delta_entrada):.3f}")
        else:
            diagnostico = t("insight_optimal", lang=lang)
            
        reporte_insights.append({
            'corner_number': curva_num,
            'start_distance': round(float(w_start), 1),
            'end_distance': round(float(w_end), 1),
            'apex_distance': metro_apex,
            'time_loss_seconds': round(delta_entrada, 3),
            'apex_speed_delta_kmh': round(-v_delta, 1), # Invertido para que + signifique que Slow es más rápido, o ajustado
            'braking_delta_meters': round(brake_delta_m, 1) if has_brake else 0.0,
            'throttle_delta_meters': round(throttle_delta_m, 1) if has_throttle else 0.0,
            'braking_delta_available': bool(brake_available),
            'throttle_delta_available': bool(throttle_available),
            'description': diagnostico
        })
        
    logger.info(f"  ✓ {len(reporte_insights)} insights generados")
    return reporte_insights
