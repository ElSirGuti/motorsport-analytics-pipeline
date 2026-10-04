"""scripts/circuit_apexes.py: herramienta para encontrar los ápices que se ponen en circuits.json.

Usa los fixtures reales anonimizados (tests/fixtures): Imola (5 vueltas, circuito con tabla) y una vuelta
suelta del Red Bull Ring (circuito sin curvas con nombre, caso de uso real al añadir un circuito).
"""
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "circuit_apexes.py"
FIXTURES = ROOT / "tests" / "fixtures"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=300)


@pytest.fixture(scope="module")
def csvs(tmp_path_factory):
    out = tmp_path_factory.mktemp("apexes")
    paths = {}
    for name in ("imola_5laps", "rbr_fast"):
        src = FIXTURES / f"{name}.csv.gz"
        if not src.exists():
            pytest.skip(f"falta el fixture {src.name}")
        dst = out / f"{name}.csv"
        with gzip.open(src, "rb") as a, open(dst, "wb") as b:
            shutil.copyfileobj(a, b)
        paths[name] = str(dst)
    return paths


def test_known_circuit_apexes_match_the_table(csvs):
    """En Imola recupera los ápices y los nombra con la tabla existente (consenso entre vueltas)."""
    r = _run([csvs["imola_5laps"]])
    assert r.returncode == 0, r.stderr[-300:]
    assert "reconocido" in r.stdout
    for name in ("Tamburello", "Villeneuve", "Tosa", "Piratella"):
        assert name in r.stdout, name


def test_single_lap_file_is_accepted_with_a_warning(csvs):
    r = _run([csvs["rbr_fast"], "--json"])
    assert r.returncode == 0, r.stderr[-300:]
    assert "una sola vuelta" in r.stdout
    block = r.stdout[r.stdout.index("["):]
    corners = json.loads(block)
    assert len(corners) >= 4
    fracs = [c["apex_fraction"] for c in corners]
    assert fracs == sorted(fracs) and all(0 < f < 1 for f in fracs)
    assert all(c["name"] == "?" for c in corners)  # sin tabla: los nombres los pone la persona


def test_flat_out_bend_is_not_invented(csvs):
    """Variante Bassa (fracción ~0.94 en Imola) es plana para un GT4: no debe aparecer como ápice."""
    r = _run([csvs["imola_5laps"], "--json"])
    corners = json.loads(r.stdout[r.stdout.index("["):])
    assert not any(0.92 <= c["apex_fraction"] <= 0.97 for c in corners)
