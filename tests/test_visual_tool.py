"""La herramienta de comparacion visual de tests/e2e/visual.py (no necesita navegador)."""
import io

import pytest

PIL = pytest.importorskip("PIL.Image")

from tests.e2e.visual import diff_stats  # noqa: E402


def _png(im):
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def test_diff_stats_detects_changes_and_ignores_noise():
    base = PIL.new("RGB", (200, 100), (30, 30, 30))
    same = PIL.new("RGB", (200, 100), (35, 33, 30))      # ruido bajo la tolerancia por canal
    other = base.copy()
    for x in range(100):
        for y in range(100):
            other.putpixel((x, y), (250, 250, 250))       # 50 % de la imagen
    assert diff_stats(_png(base), _png(same))[0] == 0.0
    assert diff_stats(_png(base), _png(other))[0] == pytest.approx(50.0)
    assert diff_stats(_png(base), _png(PIL.new("RGB", (10, 10))))[0] == 100.0
