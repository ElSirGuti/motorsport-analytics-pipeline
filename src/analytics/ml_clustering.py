"""
Clasificación de Estilos de Conducción — K-Means

Agrupa el paso por cada curva en clusters de perfil de conducción usando
vectores de features extraídos del pipeline: delta de apex, punto de frenada,
eficiencia de grip y varianza del volante.
"""
import logging
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Número de clusters por defecto (se reduce si hay pocas curvas)
DEFAULT_CLUSTERS = 4


def clasificar_curvas(
    df_aligned: pd.DataFrame,
    corners: list[dict],
    n_clusters: int = DEFAULT_CLUSTERS,
) -> list[dict]:
    """
    Asigna un perfil de conducción a cada curva mediante K-Means.

    Returns:
        Lista de {corner_number, cluster, perfil, features}
    """
    if not corners:
        return []

    vectors, refs = _build_feature_matrix(df_aligned, corners)
    if len(vectors) < 2:
        logger.warning("K-Means: menos de 2 curvas con features completos — omitiendo.")
        return []

    X = np.array(vectors, dtype=float)
    k = min(n_clusters, len(vectors))

    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)

    model = KMeans(n_clusters=k, random_state=42, n_init=12)
    labels = model.fit_predict(X_sc)
    centroids_orig = scaler.inverse_transform(model.cluster_centers_)

    perfiles = _interpretar_centroides(centroids_orig, k)

    results = []
    for corner_num, label, feat in zip(refs, labels, vectors):
        results.append({
            "corner_number": int(corner_num),
            "cluster": int(label),
            "perfil": perfiles[int(label)],
            "features": {
                "apex_speed_delta_kmh": round(feat[0], 2),
                "braking_delta_m":      round(feat[1], 1),
                "throttle_delta_m":     round(feat[2], 1),
                "time_loss_s":          round(feat[3], 3),
                "g_efficiency_pct":     round(feat[4], 1),
                "steer_variance":       round(feat[5], 2),
            },
        })

    logger.info(f"K-Means: {k} clusters para {len(results)} curvas — perfiles: {set(perfiles.values())}")
    return results


def _build_feature_matrix(
    df_aligned: pd.DataFrame,
    corners: list[dict],
) -> tuple[list[list[float]], list[int]]:
    vectors = []
    refs = []

    for corner in corners:
        cn   = corner.get("corner_number")
        start = corner.get("start_distance")
        end   = corner.get("end_distance")
        if cn is None or start is None or end is None:
            continue

        window = df_aligned[
            (df_aligned["Distance"] >= start) & (df_aligned["Distance"] <= end)
        ]
        if len(window) < 4:
            continue

        apex_delta   = float(corner.get("apex_speed_delta_kmh") or 0.0)
        brake_delta  = float(corner.get("braking_delta_meters") or 0.0)
        throttle_d   = float(corner.get("throttle_delta_meters") or 0.0)
        time_loss    = float(corner.get("time_loss_seconds") or 0.0)

        g_eff = 0.0
        if "G_Efficiency_Fast" in window.columns:
            g_eff = float(window["G_Efficiency_Fast"].mean())

        steer_var = 0.0
        if "SteerAngle_Fast" in window.columns:
            steer_var = float(window["SteerAngle_Fast"].var())

        vectors.append([apex_delta, brake_delta, throttle_d, time_loss, g_eff, steer_var])
        refs.append(int(cn))

    return vectors, refs


def _interpretar_centroides(centroids: np.ndarray, k: int) -> dict[int, str]:
    """
    Asigna etiquetas legibles a cada centroide basándose en su posición en el espacio de features.

    Columnas del centroide:
      [0] apex_speed_delta (+= referencia más rápida)
      [1] braking_delta_m  (- = frena más tarde / agresivo)
      [2] throttle_delta_m (- = abre gas antes / mejor)
      [3] time_loss_s
      [4] g_efficiency_pct
      [5] steer_variance
    """
    labels: dict[int, str] = {}

    for i in range(k):
        c = centroids[i]
        apex_d  = c[0]  # + = pilot is faster at apex
        brake_d = c[1]  # - = more aggressive braking (brakes later)
        thr_d   = c[2]  # - = throttle earlier (good)
        loss    = c[3]
        g_eff   = c[4]
        steer_v = c[5]

        if apex_d > 3 and thr_d < -5 and loss < 0.2:
            label = "Ataque Limpio — Apex veloz y salida temprana"
        elif brake_d < -8 and loss > 0.3:
            label = "Entrada Agresiva — Frena tarde, salida comprometida"
        elif apex_d < -3 and g_eff < 65:
            label = "Conservador — Subutilización del grip disponible"
        elif thr_d > 8:
            label = "Salida Tardía — Aceleración retrasada"
        elif steer_v > 60:
            label = "Conducción Errática — Volante inestable en el vértice"
        elif abs(apex_d) < 1 and loss < 0.15:
            label = "Ejecución Consistente — Réplica fiel de la referencia"
        else:
            label = f"Perfil Mixto — Clúster {i + 1}"

        labels[i] = label

    return labels
