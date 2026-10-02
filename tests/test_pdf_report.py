"""PDF report: i18n completeness, bilingual purity, robustness to missing modules, endpoint."""
import json
import re

import pytest

fitz = pytest.importorskip("pymupdf")

from src.io import pdf_charts, pdf_exporter  # noqa: E402
from src.io.pdf_exporter import (  # noqa: E402
    build_report_filename, export_report_pdf, export_session_report_pdf, parse_log_date, prettify_name,
)

ES_ONLY = re.compile(r"\b(el|los|las|una|para|con|por|que|del|vuelta|curva|frenada|sesión|mejor|ritmo)\b", re.I)
EN_ONLY = re.compile(r"\b(the|and|with|for|of|lap|corner|braking|session|best|pace|is|are)\b", re.I)


def _session():
    laps = []
    times = [140.0, 101.2, 100.8, 100.5, 100.9, 101.1, 100.7, 100.6]
    for i, tm in enumerate(times, start=1):
        laps.append({"lap_number": i, "lap_time": tm, "is_pit_lap": i == 1, "is_fastest": False})
    return {"laps": laps, "fastest_lap": laps[3], "total_laps": len(laps),
            "metadata": {"venue": "fn_imola", "vehicle": "ks_porsche_cayman_gt4_clubsport",
                         "driver": "A. Driver", "log_date": "11/6/2026", "log_time": "8:39:00 p. m.",
                         "session_type": "PRACTICE", "file": "x.csv"}}


def _stint():
    laps = [{"lap_number": i + 1, "lap_time_s": tm, "is_pit_lap": i == 0, "is_outlier": False,
             "mean_speed_kmh": 140.0, "max_speed_kmh": 240.0, "fuel_burned": 1.7}
            for i, tm in enumerate([140.0, 101.2, 100.8, 100.5, 100.9, 101.1, 100.7, 100.6])]
    return {
        "n_laps": 8, "laps": laps,
        "degradacion": {"available": True, "tasa_s_per_lap": 0.02, "degradation_s_per_lap": 0.02,
                        "slope_ci": [-0.05, 0.09], "confidence": "medium", "low_confidence": False,
                        "n_laps_used": 7, "actual_laps": [], "trend_laps": [2, 8], "trend_times": [101, 100.8]},
        "curvas_sesion": {"available": True, "reference_lap": 4, "n_laps_compared": 7, "corners": [
            {"corner_number": 2, "time_loss_seconds": 0.12, "std_loss_seconds": 0.2, "braking_delta_meters": 10,
             "apex_speed_delta_kmh": -2, "throttle_delta_meters": 5},
            {"corner_number": 1, "time_loss_seconds": -0.05, "std_loss_seconds": 0.1, "braking_delta_meters": -3,
             "apex_speed_delta_kmh": 1, "throttle_delta_meters": 0}]},
        "combustible": {"available": False},
        "thermal_analysis": {"available": True, "water_temp": {"available": False, "reason": "x"}},
        "health_summary": {"thermal": "ok", "slip": "unavailable"},
    }


def _text(pdf: bytes) -> str:
    doc = fitz.open(stream=pdf, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


def test_all_keys_exist_in_both_languages():
    keys = set()
    for mod in (pdf_exporter, pdf_charts):
        keys |= set(re.findall(r"""["'](pdf_[a-z0-9_]+)["']""", open(mod.__file__, encoding="utf8").read()))
    for lang in ("es", "en"):
        from src.i18n import get_locale
        loc = get_locale(lang)
        missing = sorted(k for k in keys if k not in loc)
        assert not missing, f"{lang}: {missing}"
    es = json.load(open("src/locales/extra/pdf.es.json", encoding="utf8"))
    en = json.load(open("src/locales/extra/pdf.en.json", encoding="utf8"))
    assert set(es) == set(en)


@pytest.mark.parametrize("lang,bad", [("es", EN_ONLY), ("en", ES_ONLY)])
def test_session_pdf_is_monolingual(lang, bad):
    text = _text(export_session_report_pdf(_session(), _stint(), lang=lang))
    # file names / venue are data, not language: strip them before checking
    text = text.replace("x.csv", "")
    assert not bad.findall(text), bad.findall(text)
    for token in ("None", "nan", "NaN"):
        assert not re.search(rf"\b{token}\b", text)


def test_comparison_pdf_signature_and_missing_modules():
    comp = {"summary": {"total_time_delta": 1.2, "worst_corner": 2, "worst_corner_loss": 0.4,
                        "num_corners_analyzed": 2},
            "corners": [{"corner_number": 2, "time_loss_seconds": 0.4, "apex_speed_delta_kmh": -3,
                         "braking_delta_meters": 8, "throttle_delta_meters": 4},
                        {"corner_number": 1, "time_loss_seconds": -0.1, "apex_speed_delta_kmh": 1}],
            "metadata": {"label_a": "V3", "label_b": "V5", "distance_synthetic": True},
            "tyre_analysis": {"available": False}}
    for lang in ("es", "en"):
        pdf = export_report_pdf(comp, lang=lang)
        assert pdf.startswith(b"%PDF")
        txt = _text(pdf)
    assert export_report_pdf({}, lang="en").startswith(b"%PDF")


def test_corners_in_corner_order():
    txt = _text(export_session_report_pdf(_session(), _stint(), lang="en"))
    sect = txt[txt.index("Corner detail"):]
    assert sect.index("-0.050") < sect.index("+0.120") or sect.index("-0.05") < sect.index("+0.12")


def test_helpers():
    assert prettify_name("ks_porsche_cayman_gt4_clubsport") == "Porsche Cayman GT4 Clubsport"
    assert prettify_name("fn_imola") == "Imola"
    assert str(parse_log_date("11/6/2026", "8:39:00 p. m.")) == "2026-06-11"
    assert str(parse_log_date("9/29/2026", "9:14:00 PM")) == "2026-09-29"
    assert build_report_filename({"venue": "spa", "vehicle": "ks_porsche_cayman_gt4_clubsport",
                                  "date_iso": "2026-09-29"}) == "motorsport_spa_porsche-cayman-gt4-clubsport_2026-09-29.pdf"


def test_session_pdf_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    r = client.post("/api/report/session-pdf-from-json?lang=es",
                    json={"session": _session(), "stint": _stint(), "comparison": None})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "motorsport_imola_porsche-cayman-gt4-clubsport_2026-06-11.pdf" in r.headers["content-disposition"]
    bad = client.post("/api/report/session-pdf-from-json", json={"stint": {}})
    assert bad.status_code == 422
