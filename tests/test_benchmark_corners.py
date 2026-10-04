"""scripts/benchmark_corners.py: banco de pruebas de la deteccion de curvas.

Usa solo los fixtures del repo (Imola 5 vueltas y Spa 3 vueltas), nunca las carpetas personales.
"""
import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.analytics.circuits import get_circuit

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "benchmark_corners.py"
FIXTURES = ROOT / "tests" / "fixtures"
DETECTORS = ("speed", "geometry", "segmenter", "union")


@pytest.fixture(scope="module")
def csvs(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    paths = {}
    for name in ("imola_5laps", "spa_3laps"):
        src = FIXTURES / f"{name}.csv.gz"
        if not src.exists():
            pytest.skip(f"falta el fixture {src.name}")
        dst = out / f"{name}.csv"
        with gzip.open(src, "rb") as a, open(dst, "wb") as b:
            shutil.copyfileobj(a, b)
        paths[name] = str(dst)
    return paths


@pytest.fixture(scope="module")
def bench(csvs, tmp_path_factory):
    out = tmp_path_factory.mktemp("bench_out")
    js, md = out / "r.json", out / "r.md"
    r = subprocess.run([sys.executable, str(SCRIPT), *csvs.values(), "--out", str(js), "--md", str(md)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    return json.loads(js.read_text(encoding="utf-8")), md.read_text(encoding="utf-8")


def test_json_structure_and_recall_range(bench):
    data, _ = bench
    for key in ("generated", "detectors", "files_used", "files_skipped", "circuits", "total"):
        assert key in data
    assert set(data["circuits"]) == {"imola", "spa_francorchamps"}
    assert data["total"]["n_laps"] >= 6
    for cid, c in data["circuits"].items():
        for key in ("n_laps", "n_tabulated", "tolerance_m", "never_detected", "cars", "detectors"):
            assert key in c, (cid, key)
        for det in DETECTORS:
            s = c["detectors"][det]
            assert 0.0 <= s["recall"] <= 1.0
            assert s["extras_per_lap"] >= 0
            assert 0.0 <= s["appearance_pct"] <= 100.0
            assert set(s["per_corner"]) == {k["name"] for k in get_circuit(cid)["corners"]}
    # La union nunca puede recuperar menos que el mejor detector individual
    imola = data["circuits"]["imola"]["detectors"]
    assert imola["union"]["recall"] >= max(imola[d]["recall"] for d in DETECTORS[:3]) - 1e-9


def test_markdown_report_sections(bench):
    _, md = bench
    for heading in ("## Total", "## Curvas nunca detectadas", "## Archivos utilizados", "## Limitaciones"):
        assert heading in md
    assert str(ROOT) not in md  # sin rutas personales


def test_variante_bassa_is_absent_from_detections(csvs):
    """Variante Bassa (fraccion ~0.94 en Imola) es plana para un GT4: ningun detector da un apice ahi."""
    spec = importlib.util.spec_from_file_location("benchmark_corners", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from src.io.loaders import load_telemetry_data

    laps = mod.clean_laps(load_telemetry_data(csvs["imola_5laps"]))
    assert len(laps) >= 3
    for lap in laps:
        dists, _errs, length = mod.detect_all(lap)
        for det, ds in dists.items():
            assert not [d for d in ds if 0.92 <= d / length <= 0.97], (det, ds)
    circuit = mod.C.get_circuit("imola")
    assert "Variante Bassa" not in [k["name"] for k in circuit["corners"]]
