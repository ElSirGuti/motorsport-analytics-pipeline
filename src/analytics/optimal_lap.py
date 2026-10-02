"""
Vuelta óptima por microsectores.

Responde a "¿cuál sería la vuelta óptima combinando los mejores microsectores de
todas las vueltas?" con DOS estimaciones y explicando la diferencia:

  (a) optimal_theoretical  Suma de los mínimos de cada microsector. Es una COTA
      INFERIOR optimista: ignora que la velocidad con la que sales de un microsector
      es la velocidad con la que entras al siguiente (un microsector rápido a la
      salida de una curva solo es posible porque esa vuelta llegó con más velocidad).

  (b) optimal_realistic    Programación dinámica que solo permite cambiar de vuelta
      donde la velocidad de las dos vueltas coincide (tolerancia en km/h) y exige un
      mínimo de microsectores consecutivos con la misma vuelta (no se "salta" de una
      vuelta a otra cada 25 m). Mantiene la continuidad cinemática.

Pipeline: vueltas -> excluir pit/outlier/parciales -> normalizar la distancia de
cada vuelta a la longitud mediana del circuito -> t(d) y v(d) por interpolación ->
tiempo por microsector = t(d_fin) - t(d_ini) -> mínimos / DP.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.i18n import _l
from src.analytics.stint import (
    extraer_metricas_por_vuelta, _format_laptime, _TIME_CHANNELS,
)

logger = logging.getLogger(__name__)

MIN_LAPS = 3
DEFAULT_MICROSECTOR_M = 25.0
DEFAULT_SPEED_TOL_KMH = 3.0
DEFAULT_MIN_RUN_M = 75.0          # tramo mínimo con la misma vuelta antes de poder cambiar
LENGTH_TOLERANCE = 0.04           # |L_i - L| / L por encima -> vuelta parcial / distinta
MAX_LAP_RATIO = 1.08              # vueltas > 108 % de la mejor no aportan microsectores
GLITCH_FACTOR = 0.75              # un microsector no puede ser < 75 % de la mediana (artefacto)
ZONE_WINDOW_M = 100.0             # ventana de las "zonas de pérdida"
TOP_ZONES = 10
PROFILE_STEP_M = 5.0
SWITCH_PENALTY_S = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Perfil de cada vuelta
# ─────────────────────────────────────────────────────────────────────────────
def _lap_profile(df: pd.DataFrame) -> Optional[dict]:
    """
    Devuelve el perfil de la vuelta: (d, t, v) con distancia creciente, tiempo relativo
    al inicio (s) y velocidad (km/h), más las mismas series en orden de muestreo y las
    coordenadas. None si no es usable.
    """
    if "Distance" not in df.columns or "Speed" not in df.columns or len(df) < 30:
        return None
    d = pd.to_numeric(df["Distance"], errors="coerce").to_numpy(dtype=float)
    v = pd.to_numeric(df["Speed"], errors="coerce").to_numpy(dtype=float)

    t = None
    for c in _TIME_CHANNELS:
        if c in df.columns:
            tt = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(tt)
            if ok.sum() < 30:
                continue
            tt_ok = tt[ok]
            if tt_ok[-1] - tt_ok[0] <= 1.0:
                continue
            if np.mean(np.diff(tt_ok) < 0) > 0.01:
                continue                      # no monótono: no es un reloj
            t = tt
            break
    time_synth = t is None

    keep = np.isfinite(d) & np.isfinite(v)
    if time_synth:
        # Sin reloj fiable: dt = ds / v (consistente con una distancia integrada).
        ds = np.clip(np.diff(d, prepend=d[0]), 0, 20.0)
        dt = ds / np.clip(v / 3.6, 1.0, None)
        t = np.cumsum(dt)
    else:
        keep &= np.isfinite(t)
    d, v, t = d[keep], v[keep], t[keep]
    if len(d) < 30:
        return None

    # Coordenadas (plano horizontal) en orden de muestreo: permiten alinear por posición
    # real en pista, inmune a la deriva de una distancia integrada desde la velocidad.
    xy_row = None
    try:
        from src.telemetry.session_analyzer import _auto_select_map_axes
        xc, yc = _auto_select_map_axes(df)
        if xc and yc and xc in df.columns and yc in df.columns:
            x = pd.to_numeric(df[xc], errors="coerce").to_numpy(dtype=float)[keep]
            y = pd.to_numeric(df[yc], errors="coerce").to_numpy(dtype=float)[keep]
            if np.isfinite(x).all() and np.isfinite(y).all() and np.ptp(x) + np.ptp(y) > 100:
                xy_row = (x, y)
    except Exception as exc:                      # pragma: no cover - mapa opcional
        logger.debug("optimal_lap: sin coordenadas (%s)", exc)
    t_row, v_row = np.maximum.accumulate(t - t[0]), v.copy()

    order = np.argsort(d, kind="stable")
    d, v, t = d[order], v[order], t[order]
    d_u, idx = np.unique(d, return_index=True)
    v, t = v[idx], t[idx]
    t = np.maximum.accumulate(t - t[0])
    d_u = d_u - d_u[0]
    if d_u[-1] < 300.0 or t[-1] <= 0:
        return None

    return {"d": d_u, "t": t, "v": v, "time_synthetic": bool(time_synth),
            "t_row": t_row, "v_row": v_row, "xy_row": xy_row}


def _project_laps_on_reference(cand: list, ref_pos: int) -> Optional[float]:
    """
    Alinea cada vuelta por POSICIÓN en pista: proyecta sus coordenadas sobre la polilínea
    de la vuelta de referencia (distancia de arco real). Rellena p['ax_s/ax_t/ax_v'] y
    devuelve la longitud del circuito, o None si no hay coordenadas en todas las vueltas.
    Las vueltas que no cubren el circuito completo se marcan con p['partial']=True.
    """
    if any(c[3]["xy_row"] is None for c in cand):
        return None
    from scipy.spatial import cKDTree
    rx, ry = cand[ref_pos][3]["xy_row"]
    seg = np.hypot(np.diff(rx), np.diff(ry))
    s_ref = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(s_ref[-1])
    if L < 300.0:
        return None
    s_dense = np.arange(0.0, L, 0.5)
    ref_pts = np.column_stack([np.interp(s_dense, s_ref, rx), np.interp(s_dense, s_ref, ry)])
    tree = cKDTree(ref_pts)
    for c in cand:
        p = c[3]
        x, y = p["xy_row"]
        _, idx = tree.query(np.column_stack([x, y]))
        s = s_dense[idx]
        s = np.unwrap(s, period=L)
        s = s - L * np.round(s[0] / L)
        s = np.maximum.accumulate(s)
        p["partial"] = bool(s[0] > 0.05 * L or s[-1] < 0.95 * L or np.max(np.diff(s)) > 0.1 * L)
        p["ax_s"], p["ax_t"], p["ax_v"] = s, p["t_row"], p["v_row"]
    return L


def _interp_nan(x_new, x, y):
    ok = np.isfinite(y)
    if ok.sum() < 2:
        return np.full_like(x_new, np.nan, dtype=float)
    return np.interp(x_new, x[ok], y[ok])


# ─────────────────────────────────────────────────────────────────────────────
# Programación dinámica con continuidad de velocidad
# ─────────────────────────────────────────────────────────────────────────────
def _dp_realistic(tau: np.ndarray, v_edge: np.ndarray, tol_kmh: float,
                  min_run: int, penalty: float) -> np.ndarray:
    """
    tau[i, k]    tiempo de la vuelta i en el microsector k (n x K)
    v_edge[i, k] velocidad (km/h) de la vuelta i en el borde de ENTRADA del microsector k
    Cambiar de la vuelta i a la j al entrar en k exige |v_i - v_j| <= tol en ese borde y
    que i lleve al menos `min_run` microsectores seguidos. Devuelve la vuelta elegida
    por microsector (K,).
    """
    n, K = tau.shape
    R = max(1, int(min_run))
    INF = np.inf
    dp = np.full((n, R), INF)
    dp[:, 0] = tau[:, 0]
    back_i = np.zeros((K, n, R), dtype=np.int32)
    back_r = np.zeros((K, n, R), dtype=np.int32)

    for k in range(1, K):
        new = np.full((n, R), INF)
        # seguir con la misma vuelta: r -> min(r+1, R-1)
        for r in range(R):
            nr = min(r + 1, R - 1)
            cand = dp[:, r] + tau[:, k]
            better = cand < new[:, nr]
            new[better, nr] = cand[better]
            back_i[k][better, nr] = np.arange(n)[better]
            back_r[k][better, nr] = r
        # cambiar de vuelta (solo si la actual ya cumple el tramo mínimo)
        src = dp[:, R - 1]
        compat = np.abs(v_edge[:, k][:, None] - v_edge[:, k][None, :]) <= tol_kmh
        np.fill_diagonal(compat, False)
        cost = np.where(compat, src[:, None], INF)       # [i, j]
        i_best = np.argmin(cost, axis=0)
        c_best = cost[i_best, np.arange(n)] + tau[:, k] + penalty
        better = c_best < new[:, 0]
        new[better, 0] = c_best[better]
        back_i[k][better, 0] = i_best[better]
        back_r[k][better, 0] = R - 1
        dp = new

    j, r = np.unravel_index(np.argmin(dp), dp.shape)
    sel = np.zeros(K, dtype=np.int32)
    for k in range(K - 1, -1, -1):
        sel[k] = j
        if k == 0:
            break
        j, r = back_i[k][j, r], back_r[k][j, r]
    return sel


# ─────────────────────────────────────────────────────────────────────────────
# Curvas / zonas
# ─────────────────────────────────────────────────────────────────────────────
def _corner_apexes(df_best: pd.DataFrame, d: np.ndarray, v: np.ndarray, length: float) -> np.ndarray:
    """Distancias de apex (orden de vuelta) usando la geometría; si falla, mínimos de velocidad."""
    apex_d = np.array([])
    try:
        from src.analytics.geometry import procesar_geometria_pista_perfecta, detectar_apexes_perfectos
        geo = procesar_geometria_pista_perfecta(df_best)
        apexes = detectar_apexes_perfectos(geo)
        apex_d = np.sort(apexes["Distance"].to_numpy(dtype=float))
    except Exception as exc:
        logger.debug("optimal_lap: geometría no disponible (%s)", exc)
    if len(apex_d) < 3:
        from scipy.signal import find_peaks
        grid = np.arange(0, length, 5.0)
        vs = np.interp(grid, d, v)
        k = max(1, int(round(50 / 5)))
        vs = np.convolve(vs, np.ones(k) / k, mode="same")
        pk, _ = find_peaks(-vs, prominence=15.0, distance=int(80 / 5))
        apex_d = grid[pk]
    return apex_d[(apex_d > 0) & (apex_d < length)]


def _assign_corner(mid: np.ndarray, apex_d: np.ndarray) -> np.ndarray:
    """Zona de cada microsector: la curva cuyo apex es el más cercano (1-based)."""
    if len(apex_d) == 0:
        return np.zeros(len(mid), dtype=int)
    bounds = (apex_d[:-1] + apex_d[1:]) / 2.0
    return np.searchsorted(bounds, mid) + 1


# ─────────────────────────────────────────────────────────────────────────────
# API principal
# ─────────────────────────────────────────────────────────────────────────────
def _unavailable(lang: str, key: str, **kw) -> dict:
    return {"available": False, "reason": _l(lang, key, **kw)}


def calcular_vuelta_optima(
    dfs: list,
    df_laps: Optional[pd.DataFrame] = None,
    microsector_m: float = DEFAULT_MICROSECTOR_M,
    speed_tol_kmh: float = DEFAULT_SPEED_TOL_KMH,
    min_run_m: float = DEFAULT_MIN_RUN_M,
    lang: str = "es",
    distance_synthetic: bool = False,
) -> dict:
    """
    Calcula la vuelta óptima teórica y realista a partir de las vueltas segmentadas.

    Args:
        dfs:           lista de DataFrames por vuelta (salida de segmentar_vueltas_desde_csv).
        df_laps:       métricas por vuelta (extraer_metricas_por_vuelta); se calcula si es None.
        microsector_m: longitud del microsector en metros.
        speed_tol_kmh: tolerancia de velocidad para permitir un cambio de vuelta.
        min_run_m:     tramo mínimo (m) con la misma vuelta antes de poder cambiar.
        lang:          "es" | "en".
        distance_synthetic: la distancia fue integrada de la velocidad (menos precisa).
    """
    microsector_m = float(np.clip(microsector_m, 5.0, 200.0))
    if df_laps is None:
        df_laps = extraer_metricas_por_vuelta(dfs)

    # ── 1. Candidatas y perfiles ──────────────────────────────────────────────
    excluded = []
    cand = []   # (idx, lap_number, lap_time_s, profile)

    def _excl(num, code, **kw):
        excluded.append({"lap_number": int(num), "code": code,
                         "reason": _l(lang, f"optlap_excl_{code}", **kw)})

    for i, df in enumerate(dfs):
        row = df_laps.iloc[i]
        num = int(row.get("lap_number", i + 1))
        lt = row.get("lap_time_s")
        if bool(row.get("is_pit_lap", False)):
            _excl(num, "pit")
            continue
        if lt is None or not np.isfinite(lt) or lt <= 10:
            _excl(num, "data")
            continue
        prof = _lap_profile(df)
        if prof is None:
            _excl(num, "data")
            continue
        cand.append((i, num, float(lt), prof))

    if len(cand) < MIN_LAPS:
        return _unavailable(lang, "optlap_reason_few_laps", min=MIN_LAPS, n=len(cand))

    best_time_all = min(c[2] for c in cand)
    kept = []
    for c in cand:
        if c[2] > best_time_all * MAX_LAP_RATIO:
            _excl(c[1], "slow", pct=f"{c[2] / best_time_all * 100:.0f}")
        else:
            kept.append(c)
    cand = kept

    # Alineación espacial: por coordenadas (posición real en pista) si todas las vueltas las
    # tienen; si no, por distancia normalizada a la longitud mediana del circuito.
    ref_pos = int(np.argmin([c[2] for c in cand]))
    L = _project_laps_on_reference(cand, ref_pos)
    alignment = "position"
    if L is None:
        alignment = "distance"
        L = float(np.median([c[3]["d"][-1] for c in cand]))
        for c in cand:
            p = c[3]
            p["partial"] = abs(p["d"][-1] - L) / L > LENGTH_TOLERANCE
            p["ax_s"], p["ax_t"], p["ax_v"] = p["d"] * (L / p["d"][-1]), p["t"], p["v"]
    kept = []
    for c in cand:
        if c[3]["partial"]:
            _excl(c[1], "length", m=f"{L:.0f}")
        else:
            kept.append(c)
    cand = kept
    if len(cand) < MIN_LAPS:
        return _unavailable(lang, "optlap_reason_few_laps", min=MIN_LAPS, n=len(cand))

    # ── 2. Microsectores ──────────────────────────────────────────────────────
    K = max(2, int(round(L / microsector_m)))
    edges = np.linspace(0.0, L, K + 1)
    mid = (edges[:-1] + edges[1:]) / 2
    n = len(cand)

    t_edge = np.zeros((n, K + 1))
    v_edge = np.zeros((n, K + 1))
    grid_pts = np.arange(0.0, L, max(PROFILE_STEP_M, L / 1000.0))
    v_grid = np.zeros((n, len(grid_pts)))
    for a, (_, _, _, p) in enumerate(cand):
        ds = p["ax_s"]
        t_edge[a] = np.interp(edges, ds, p["ax_t"])
        v_edge[a] = _interp_nan(edges, ds, p["ax_v"])
        v_grid[a] = _interp_nan(grid_pts, ds, p["ax_v"])
    v_edge = np.nan_to_num(v_edge, nan=0.0)
    tau = np.diff(t_edge, axis=1)                # n x K
    tau = np.where(np.isfinite(tau) & (tau > 0), tau, np.nan)
    med = np.nanmedian(tau, axis=0)
    # microsectores sin dato -> mediana (nunca serán el mínimo salvo artefacto);
    # y se limita lo imposiblemente rápido (artefactos del reloj/distancia).
    tau = np.where(np.isnan(tau), med[None, :], tau)
    n_glitch = int((tau < GLITCH_FACTOR * med[None, :]).sum())
    tau = np.maximum(tau, GLITCH_FACTOR * med[None, :])

    lap_nums = np.array([c[1] for c in cand])
    lap_times = np.array([c[2] for c in cand])
    b = int(np.argmin(lap_times))               # índice (local) de la mejor vuelta real
    best_num, best_time = int(lap_nums[b]), float(lap_times[b])

    # ── 3. Teórica y realista ─────────────────────────────────────────────────
    theo_sel = np.argmin(tau, axis=0)
    tau_theo = tau[theo_sel, np.arange(K)]
    min_run = max(1, int(round(min_run_m / microsector_m)))
    real_sel = _dp_realistic(tau, v_edge[:, :K], speed_tol_kmh, min_run, SWITCH_PENALTY_S)
    tau_real = tau[real_sel, np.arange(K)]
    tau_best = tau[b]

    base = float(tau_best.sum())
    gain_theo = base - float(tau_theo.sum())
    gain_real = base - float(tau_real.sum())
    gain_real = max(0.0, min(gain_real, gain_theo))          # por construcción, defensivo
    t_theo = best_time - gain_theo
    t_real = best_time - gain_real
    n_switches = int(np.count_nonzero(np.diff(real_sel)))

    # ── 4. Curvas ─────────────────────────────────────────────────────────────
    p_best = cand[b][3]
    df_best = dfs[cand[b][0]]
    apex_d = _corner_apexes(df_best, p_best["ax_s"], p_best["ax_v"], L)
    corner_of = _assign_corner(mid, apex_d)
    corners = []
    for cn in sorted(set(corner_of.tolist())):
        m = corner_of == cn
        if cn == 0:
            continue
        d0, d1 = float(edges[:-1][m].min()), float(edges[1:][m].max())
        g_real = float((tau_best[m] - tau_real[m]).sum())
        g_theo = float((tau_best[m] - tau_theo[m]).sum())
        donors = pd.Series(lap_nums[real_sel[m]]).value_counts()
        corners.append({
            "corner_number": int(cn),
            "label": _l(lang, "optlap_corner", n=int(cn)),
            "d_start": round(d0, 1), "d_end": round(d1, 1),
            "apex_distance": round(float(apex_d[cn - 1]), 1) if cn - 1 < len(apex_d) else None,
            "best_time_s": round(float(tau_best[m].sum()), 3),
            "gain_realistic_s": round(g_real, 3),
            "gain_theoretical_s": round(g_theo, 3),
            "donor_lap": int(donors.index[0]) if len(donors) else best_num,
            "n_microsectors": int(m.sum()),
        })

    # perfil de velocidad: mejor vuelta / construida realista / construida teórica
    k_of = np.clip(np.searchsorted(edges, grid_pts, side="right") - 1, 0, K - 1)
    ar = np.arange(len(grid_pts))
    sp_real = v_grid[real_sel[k_of], ar]
    sp_theo = v_grid[theo_sel[k_of], ar]
    sp_best = v_grid[b]
    r1 = lambda a: [None if not np.isfinite(x) else round(float(x), 1) for x in a]


    # ── 5. Zonas de pérdida (ventanas no solapadas) ───────────────────────────
    W = max(1, int(round(ZONE_WINDOW_M / microsector_m)))
    loss_real = tau_best - tau_real
    loss_theo = tau_best - tau_theo
    csum = np.concatenate([[0.0], np.cumsum(loss_real)])
    win = csum[W:] - csum[:-W] if K >= W else np.array([csum[-1]])
    if K < W:
        W = K
    taken = np.zeros(K, dtype=bool)
    zones = []
    for start in np.argsort(-win):
        if len(zones) >= TOP_ZONES or win[start] <= 0.0005:
            break
        s, e = int(start), int(start) + W
        if taken[s:e].any():
            continue
        taken[s:e] = True
        sl = slice(s, e)
        donors = pd.Series(lap_nums[real_sel[sl]]).value_counts()
        donor = int(donors.index[0])
        # velocidades: mejor vuelta vs construida (realista) dentro de la zona
        gm = (grid_pts >= edges[s]) & (grid_pts < edges[e])
        vb = v_grid[b][gm]
        vo = sp_real[gm]
        hint_key, hint_kw = "optlap_hint_spread", {"lap": donor}
        if len(vb) and len(vo):
            dmin = float(vo.min() - vb.min())
            dend = float(vo[-1] - vb[-1])
            if dmin >= 2.0:
                hint_key, hint_kw = "optlap_hint_min", {"lap": donor, "dv": f"{dmin:.1f}"}
            elif dend >= 2.0:
                hint_key, hint_kw = "optlap_hint_exit", {"lap": donor, "dv": f"{dend:.1f}"}
        c_idx = int(corner_of[(s + e - 1) // 2])
        zones.append({
            "d_start": round(float(edges[s]), 1), "d_end": round(float(edges[e]), 1),
            "loss_realistic_s": round(float(loss_real[sl].sum()), 3),
            "loss_theoretical_s": round(float(loss_theo[sl].sum()), 3),
            "corner_number": c_idx if c_idx > 0 else None,
            "corner_label": _l(lang, "optlap_corner", n=c_idx) if c_idx > 0 else None,
            "donor_lap": donor,
            "hint": _l(lang, hint_key, **hint_kw),
        })
    for rnk, z in enumerate(zones, 1):
        z["rank"] = rnk

    # ── 6. Qué vuelta aporta más ──────────────────────────────────────────────
    contrib = []
    for a in range(n):
        m_real = real_sel == a
        m_theo = theo_sel == a
        contrib.append({
            "lap_number": int(lap_nums[a]),
            "lap_time_s": round(float(lap_times[a]), 3),
            "microsectors_realistic": int(m_real.sum()),
            "microsectors_theoretical": int(m_theo.sum()),
            "pct_realistic": round(float(m_real.mean() * 100), 1),
            "gain_realistic_s": round(float((tau_best[m_real] - tau_real[m_real]).sum()), 3),
            "gain_theoretical_s": round(float((tau_best[m_theo] - tau_theo[m_theo]).sum()), 3),
            "is_best": bool(a == b),
        })
    contrib.sort(key=lambda r: (-r["microsectors_realistic"], r["lap_number"]))

    # ── 7. Series para gráficas ───────────────────────────────────────────────
    cum_real = np.concatenate([[0.0], np.cumsum(loss_real)])
    cum_theo = np.concatenate([[0.0], np.cumsum(loss_theo)])

    track = []
    if p_best["xy_row"] is not None:
        x = np.interp(edges, p_best["ax_s"], p_best["xy_row"][0])
        y = np.interp(edges, p_best["ax_s"], p_best["xy_row"][1])
        track = [{"x": round(float(a), 2), "y": round(float(c), 2), "distance": round(float(dd), 1)}
                 for a, c, dd in zip(x, y, edges)]

    micro = [{
        "index": k,
        "d_start": round(float(edges[k]), 1), "d_end": round(float(edges[k + 1]), 1),
        "best_lap_time_s": round(float(tau_best[k]), 4),
        "gain_realistic_s": round(float(loss_real[k]), 4),
        "gain_theoretical_s": round(float(loss_theo[k]), 4),
        "lap_realistic": int(lap_nums[real_sel[k]]),
        "lap_theoretical": int(lap_nums[theo_sel[k]]),
        "corner_number": int(corner_of[k]) if corner_of[k] > 0 else None,
    } for k in range(K)]

    warnings = []
    if distance_synthetic:
        warnings.append(_l(lang, "optlap_warn_synth"))
    if n < 5:
        warnings.append(_l(lang, "optlap_warn_few", n=n))
    if any(c[3]["time_synthetic"] for c in cand):
        warnings.append(_l(lang, "optlap_warn_time_synth"))

    explanation = _l(
        lang, "optlap_explain",
        theo=f"{gain_theo:.3f}", real=f"{gain_real:.3f}",
        gap=f"{gain_theo - gain_real:.3f}", switches=n_switches,
        tol=f"{speed_tol_kmh:g}", run=f"{min_run * microsector_m:.0f}",
    )

    def _tstr(s):
        return _format_laptime(float(s))

    logger.info("optimal_lap: %d vueltas, %d microsectores, mejor=%.3f teórica=%.3f realista=%.3f",
                n, K, best_time, t_theo, t_real)
    return {
        "available": True,
        "params": {
            "microsector_m": round(float(microsector_m), 1),
            "speed_tol_kmh": float(speed_tol_kmh),
            "min_run_m": round(min_run * microsector_m, 1),
        },
        "track_length_m": round(L, 1),
        "alignment": alignment,
        "n_microsectors": K,
        "n_laps_used": n,
        "laps_used": [int(x) for x in lap_nums],
        "laps_excluded": excluded,
        "distance_synthetic": bool(distance_synthetic),
        "n_glitch_clipped": n_glitch,
        "best_lap": {"lap_number": best_num, "time_s": round(best_time, 3), "time_str": _tstr(best_time)},
        "optimal_theoretical": {"time_s": round(t_theo, 3), "time_str": _tstr(t_theo),
                                "gain_s": round(gain_theo, 3)},
        "optimal_realistic": {"time_s": round(t_real, 3), "time_str": _tstr(t_real),
                              "gain_s": round(gain_real, 3), "n_switches": n_switches},
        "realism_gap_s": round(gain_theo - gain_real, 3),
        "explanation": explanation,
        "warnings": warnings,
        "corners": corners,
        "top_zones": zones,
        "lap_contributions": contrib,
        "microsectors": micro,
        "track": track,
        "series": {
            "cumulative": {
                "distance": [round(float(x), 1) for x in edges],
                "gain_realistic_s": [round(float(x), 4) for x in cum_real],
                "gain_theoretical_s": [round(float(x), 4) for x in cum_theo],
            },
            "speed_profile": {
                "distance": [round(float(x), 1) for x in grid_pts],
                "best_lap": r1(sp_best),
                "optimal_realistic": r1(sp_real),
                "optimal_theoretical": r1(sp_theo),
            },
        },
    }


def calcular_vuelta_optima_desde_df(df: pd.DataFrame, **kwargs) -> dict:
    """Atajo para otros módulos: segmenta la sesión y calcula la vuelta óptima."""
    from src.analytics.stint import segmentar_vueltas_desde_csv
    lang = kwargs.get("lang", "es")
    kwargs.setdefault("distance_synthetic", bool(df.attrs.get("distance_synthetic", False)))
    try:
        dfs = segmentar_vueltas_desde_csv(df)
    except ValueError:
        return _unavailable(lang, "optlap_reason_few_laps", min=MIN_LAPS, n=0)
    return calcular_vuelta_optima(dfs, **kwargs)
