import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _perpendicular_distance(point, line_start, line_end):
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end

    if x1 == x2 and y1 == y2:
        return np.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)

    num = abs((x2 - x1) * (y1 - y0) - (x1 - x0) * (y2 - y1))
    den = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return num / den


def _rdp_mask(points, epsilon=0.05):
    if len(points) <= 2:
        return [True] * len(points)

    dmax = 0.0
    index = 0
    end = len(points) - 1

    for i in range(1, end):
        d = _perpendicular_distance(points[i], points[0], points[end])
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        left = _rdp_mask(points[: index + 1], epsilon)
        right = _rdp_mask(points[index:], epsilon)
        return left[:-1] + right
    else:
        mask = [False] * len(points)
        mask[0] = True
        mask[-1] = True
        return mask


def comprimir_telemetria(
    df_aligned: pd.DataFrame,
    epsilon_delta: float = 0.05,
    epsilon_vel: float = 0.5,
    asegurar_apexes: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if df_aligned.empty:
        return df_aligned

    cols_original = list(df_aligned.columns)

    if "Delta_Time" not in cols_original:
        logger.warning("Columna Delta_Time no disponible, saltando compresión RDP.")
        return df_aligned

    puntos_delta = df_aligned[["Distance", "Delta_Time"]].values
    mask_delta = _rdp_mask(puntos_delta, epsilon=epsilon_delta)

    if "Speed_Fast" in cols_original:
        puntos_vel = df_aligned[["Distance", "Speed_Fast"]].values
        mask_vel = _rdp_mask(puntos_vel, epsilon=epsilon_vel)
        mask_combinada = [a or b for a, b in zip(mask_delta, mask_vel)]
    else:
        mask_combinada = mask_delta

    if asegurar_apexes is not None and not asegurar_apexes.empty:
        for _, apex in asegurar_apexes.iterrows():
            d_apex = apex["Distance"]
            idx = (df_aligned["Distance"] - d_apex).abs().idxmin()
            if idx not in mask_combinada or not mask_combinada[idx]:
                mask_combinada[idx] = True

    df_comp = df_aligned[mask_combinada].copy()

    logger.info(f"Compresión RDP: {len(df_aligned)} → {len(df_comp)} filas "
                f"({(1 - len(df_comp)/len(df_aligned))*100:.0f}% reducción)")
    return df_comp
