"""Regresion visual: captura -> comparacion con PIL contra tests/e2e/baseline/<name>.png.

* Las zonas dinamicas (fechas, relojes, etc.) se enmascaran con `mask=[locators]` de Playwright
  (se pintan de color solido, igual en baseline y captura).
* Se compara pixel a pixel con una tolerancia por canal y un % maximo de pixeles distintos.
* E2E_UPDATE_BASELINE=1 regenera las baselines en lugar de comparar.
* Si falla, deja baseline/actual/diff en tests/e2e/_artifacts/ (ignorado por git).
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline"
ARTIFACTS = HERE / "_artifacts"

CHANNEL_TOL = 24        # diferencia maxima por canal (0-255) para considerar iguales dos pixeles
MAX_DIFF_PCT = 1.5      # % maximo de pixeles distintos
UPDATE = os.environ.get("E2E_UPDATE_BASELINE", "").strip().lower() in ("1", "true", "yes")


def _optimize(png: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def diff_stats(a_png: bytes, b_png: bytes, tol: int = CHANNEL_TOL):
    """(pct_distintos, imagen_diff) entre dos PNG del mismo tamano."""
    from PIL import Image, ImageChops
    a = Image.open(io.BytesIO(a_png)).convert("RGB")
    b = Image.open(io.BytesIO(b_png)).convert("RGB")
    if a.size != b.size:
        return 100.0, None
    d = ImageChops.difference(a, b)
    # maximo de los 3 canales por pixel
    r, g, bl = d.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    mask = mx.point(lambda v: 255 if v > tol else 0)
    n_diff = sum(1 for v in mask.getdata() if v)
    pct = 100.0 * n_diff / (a.size[0] * a.size[1])
    return pct, mask


def check_screenshot(pg, name: str, *, mask=None, max_diff_pct: float = MAX_DIFF_PCT) -> None:
    """Captura el viewport y lo compara con la baseline `name` (o la regenera)."""
    BASELINE.mkdir(parents=True, exist_ok=True)
    png = pg.screenshot(animations="disabled", caret="hide", mask=mask or [], mask_color="#ff00ff")
    png = _optimize(png)
    base_path = BASELINE / f"{name}.png"
    if UPDATE or not base_path.exists():
        if not UPDATE:
            pytest.fail(f"missing baseline {base_path.name}; generate it with E2E_UPDATE_BASELINE=1")
        base_path.write_bytes(png)
        return
    base = base_path.read_bytes()
    pct, mask_img = diff_stats(base, png)
    if pct > max_diff_pct:
        ARTIFACTS.mkdir(exist_ok=True)
        (ARTIFACTS / f"{name}.actual.png").write_bytes(png)
        (ARTIFACTS / f"{name}.baseline.png").write_bytes(base)
        if mask_img is not None:
            mask_img.save(ARTIFACTS / f"{name}.diff.png")
        pytest.fail(f"visual regression in {name}: {pct:.2f}% pixels differ (max {max_diff_pct}%). "
                    f"See tests/e2e/_artifacts/. If the change is intended, regenerate with E2E_UPDATE_BASELINE=1")
