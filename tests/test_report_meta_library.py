"""Comparison-PDF metadata + compact length, .ibt/.ld header metadata, library source-file link, robustness."""
import glob
import hashlib
import io
import json
import os

import pytest

from tests.test_library import client, make_payload, save  # noqa: F401  (fixtures/helpers)

IBT_DIR = r"C:\Users\elgut\Documents\iRacing\Telemetry"
real_ibt = sorted(glob.glob(os.path.join(IBT_DIR, "*.ibt")))[:1]
real_ld = sorted(glob.glob(os.path.join(IBT_DIR, "*.ld")))[:1]


# -- PDF ----------------------------------------------------------------------
def _comp():
    corners = [{"corner_number": i, "corner_name": f"Name{i}", "time_loss_seconds": 0.1 * (i % 3 - 1),
                "apex_speed_delta_kmh": -2.0, "braking_delta_meters": 5} for i in range(1, 12)]
    return {"summary": {"total_time_delta": 1.234, "worst_corner": 1, "worst_corner_loss": 0.9},
            "corners": corners,
            "circuit": {"matched": True, "name": "Autodromo Test (Imola)"},
            "metadata": {"label_a": "L3", "label_b": "L7", "venue": "fn_imola", "vehicle": "ks_porsche_cayman_gt4",
                         "driver": "A. Pilot", "date_iso": "2026-06-11", "session_file": "x.csv"},
            "data_quality": {"available": True, "score": 77, "level": "good", "lang": "en",
                             "channel_summary": {"ok": 5, "warning": 1, "missing": 2},
                             "module_summary": {"ok": 3, "degraded": 1, "unavailable": 0}}}


@pytest.mark.parametrize("lang,date_txt,dq", [("es", "11 jun 2026", "Calidad de datos: 77/100"),
                                              ("en", "11 Jun 2026", "Data quality: 77/100")])
def test_comparison_pdf_header_and_summary(lang, date_txt, dq):
    pymupdf = pytest.importorskip("pymupdf")
    from src.io.pdf_exporter import export_report_pdf
    d = pymupdf.open(stream=export_report_pdf(_comp(), lang=lang), filetype="pdf")
    first = d[0].get_text()
    for needle in ("Autodromo Test", "Porsche Cayman GT4", "A. Pilot", date_txt, dq):
        assert needle in first, needle
    assert "Exec" in first or "ejecutivo" in first
    assert len(d) <= 8


def test_actions_not_duplicated(monkeypatch):
    import src.io.pdf_exporter as pe
    from src.i18n import LanguageContext
    rec = {"category": "Brakes", "recommendation": "Same advice", "priority": "alta", "expected_gain": "0.1"}
    setup = {"available": True, "recommendations": [rec, dict(rec), dict(rec)]}
    monkeypatch.setattr(pe, "_setup_recs", lambda c: setup)
    with LanguageContext("en"):
        acts = pe._actions(pe.Ctx(None, None, _comp(), None), [])
    assert len([a for a in acts if "Same advice" in a]) == 1


def test_locale_files_match():
    es = json.load(open("src/locales/extra/pdf_compare.es.json", encoding="utf8"))
    en = json.load(open("src/locales/extra/pdf_compare.en.json", encoding="utf8"))
    assert set(es) == set(en)


# -- header metadata ----------------------------------------------------------
@pytest.mark.skipif(not real_ibt, reason="no real .ibt available")
def test_ibt_header_metadata_and_sniff_endpoints():
    from fastapi.testclient import TestClient
    from main import app
    from src.io.header_meta import read_header
    h = read_header(real_ibt[0], os.path.basename(real_ibt[0]))
    assert h["format"] == "ibt" and h["venue"] and h["vehicle"] and h["driver"] and h["date_iso"]
    head = open(real_ibt[0], "rb").read(256 * 1024)
    c = TestClient(app)
    r = c.post("/api/library/sniff", files={"head": ("a.ibt", head)}).json()
    assert r["format"] == "ibt" and r["venue"] and r["vehicle"] and r["driver"] and r["date"]
    r2 = c.post("/api/setups/detect", files={"header": ("a.ibt", head)}).json()
    assert r2["format"] == "ibt" and r2["venue"] == h["venue"]


@pytest.mark.skipif(not real_ld, reason="no real .ld available")
def test_ld_header_metadata_and_sniff():
    from fastapi.testclient import TestClient
    from main import app
    from src.io.header_meta import read_header
    h = read_header(real_ld[0], os.path.basename(real_ld[0]))
    assert h["format"] == "ld" and h["venue"] and h["driver"] and h["date_iso"]
    head = open(real_ld[0], "rb").read(256 * 1024)
    r = TestClient(app).post("/api/library/sniff", files={"head": (os.path.basename(real_ld[0]), head)}).json()
    assert r["format"] == "ld" and r["venue"] and r["date"] == h["date_iso"]


def test_csv_sniff_still_works():
    from fastapi.testclient import TestClient
    from main import app
    csv = (b'"Driver","Ana",,\n"Vehicle","ks_porsche_cayman_gt4_clubsport",,\n"Venue","fn_imola",,\n'
           b'"Log Date","11/6/2026",,\n"Log Time","8:39:00 p. m.",,\n')
    r = TestClient(app).post("/api/library/sniff", files={"head": ("x.csv", csv)}).json()
    assert r["driver"] == "Ana" and "format" not in r and r["date"] == "2026-06-11"
    assert r["vehicle"] == "Porsche Cayman GT4 Clubsport"


# -- library: source file, canonical sha, extras ------------------------------
@pytest.fixture()
def upload_store(tmp_path, monkeypatch):
    from src.io import session_cache as sc
    monkeypatch.setattr(sc, "store", sc.UploadStore(tmp_path))
    return sc.store


def test_library_links_source_file_and_canonical_sha(client, upload_store):
    data = b"hello telemetry" * 100
    stored = upload_store.save_stream(io.BytesIO(data), "s.csv", 10 ** 8)
    full = hashlib.sha256(data).hexdigest()
    assert stored.file_id == full
    partial = "ab" * 32
    payload = make_payload([100.0, 99.0, 99.5])
    first = save(client, payload, file_sha256=partial).json()      # legacy client: partial hash only
    sid = first["session"]["id"]
    assert first["session"]["has_source_file"] is False
    second = save(client, payload, file_sha256=partial, file_id=full).json()
    assert second["status"] == "updated" and second["session"]["id"] == sid
    got = client.get(f"/api/library/{sid}").json()
    assert got["file_sha256"] == full and got["has_source_file"] is True and got["source_file_id"] == full
    assert got["payload"]["extras"] == {"optimal_lap": {"time": 98.1}}
    save(client, payload, file_sha256=partial)                      # no file_id: keeps the link
    assert client.get(f"/api/library/{sid}").json()["has_source_file"] is True
    os.remove(stored.path)                                          # TTL expiry: nothing fails
    got = client.get(f"/api/library/{sid}").json()
    assert got["has_source_file"] is False and got["payload"]["extras"]


def test_library_unknown_file_id_is_ignored(client, upload_store):
    r = save(client, make_payload([100.0, 99.0]), file_id="f" * 64)
    assert r.status_code == 200 and r.json()["session"]["has_source_file"] is False


# -- session_compare robustness -----------------------------------------------
def test_compare_sessions_robust():
    from src.analytics.session_compare import compare_sessions
    for a, b in (({}, {}), ({"stint": []}, {"session": "x"}),
                 ({"stint": {"laps": [None, {"lap_number": "x", "lap_time_s": 90}]}}, {})):
        r = compare_sessions(a, b, "en")
        assert "kpis" in r and r["summary"]
    pa = make_payload([100.0, 99.0], [0.1, 0.2], with_apex=True)
    pb = make_payload([101.0, 100.0], [0.3], with_apex=True)
    r = compare_sessions(pa, pb, "en", venue_a="Imola", venue_b="Spa")
    assert r["corners"]["available"] is False and r["corners"]["reason"] == "different_circuit"


def test_library_compare_different_circuit_forced_no_500(client):
    a = save(client, make_payload([100.0, 99.0], [0.1], with_apex=True), venue="Imola").json()["session"]["id"]
    b = save(client, make_payload([101.0, 100.0], [0.2], with_apex=True), venue="Spa").json()["session"]["id"]
    assert client.post("/api/library/compare", json={"a": a, "b": b}).status_code == 400
    r = client.post("/api/library/compare", json={"a": a, "b": b, "force": True})
    assert r.status_code == 200 and r.json()["corners"]["available"] is False
