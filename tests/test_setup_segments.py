"""Setup changes inside a session: laps ranges with their own pace and Setup Advisor (src/analytics/setup_segments.py)."""
import gzip
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from src.analytics.setup_segments import SegmentError, parse_splits, ranges

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_splits_accepts_the_usual_spellings():
    assert parse_splits("12, 25", 30) == [12, 25]
    assert parse_splits("[25;12;12]", 30) == [12, 25]
    assert parse_splits([3.0, "5"], 8) == [3, 5]
    assert parse_splits("", 10) == [] and parse_splits(None, 10) == []


@pytest.mark.parametrize("raw,code", [("x", "not_numeric"), ("1", "out_of_range"), ("32", "out_of_range"),
                                      ("2,3,4,5,6,7,8,9,10", "too_many")])
def test_parse_splits_rejects_bad_laps(raw, code):
    with pytest.raises(SegmentError) as e:
        parse_splits(raw, 31)
    assert e.value.code == code


def test_ranges_cover_every_lap_once():
    assert ranges([], 5) == [(1, 5)]
    assert ranges([3], 5) == [(1, 2), (3, 5)]
    assert ranges([2, 4], 6) == [(1, 1), (2, 3), (4, 6)]


@pytest.fixture(scope="module")
def imola(tmp_path_factory):
    src = FIXTURES / "imola_5laps.csv.gz"
    if not src.exists():
        pytest.skip("real fixture missing")
    dst = tmp_path_factory.mktemp("seg") / "imola.csv"
    with gzip.open(src, "rb") as a, open(dst, "wb") as b:
        shutil.copyfileobj(a, b)
    return dst


def _post(client, path, splits, lang="en"):
    with open(path, "rb") as fh:
        return client.post(f"/api/stint/segments?lang={lang}", files={"session_file": ("imola.csv", fh, "text/csv")},
                           data={"splits": splits})


def test_segments_endpoint_splits_the_session(imola):
    c = TestClient(main.app)
    r = _post(c, imola, "3")
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["n_laps"] == 5 and d["splits"] == [3]
    a, b = d["segments"]
    assert (a["from_lap"], a["to_lap"], a["n_laps"]) == (1, 2, 2)
    assert (b["from_lap"], b["to_lap"], b["n_laps"]) == (3, 5, 3)
    assert a["pace"]["median_s"] and b["pace"]["median_s"]
    assert "vs_previous" not in a and set(b["vs_previous"]) == {"median_delta_s", "best_delta_s", "std_delta_s"}
    assert a["advisor_reason"] == "few_laps" and a["setup_advisor"] == {"available": False}   # 2 laps: pace only
    assert b["advisor_reason"] in (None, "few_laps", "no_data")
    # no split -> the whole session is one range
    one = _post(c, imola, "").json()["segments"]
    assert len(one) == 1 and (one[0]["from_lap"], one[0]["to_lap"]) == (1, 5)


def test_segments_endpoint_validates_the_laps_in_both_languages(imola):
    c = TestClient(main.app)
    r = _post(c, imola, "1")
    assert r.status_code == 422 and "between 2 and 5" in r.json()["detail"]
    r = _post(c, imola, "99", lang="es")
    assert r.status_code == 422 and "entre 2 y 5" in r.json()["detail"]
    assert _post(c, imola, "abc").status_code == 422


def test_segment_texts_exist_in_both_languages():
    import json
    root = Path(__file__).resolve().parent.parent / "src/locales/extra"
    en = json.loads((root / "setup_segments.en.json").read_text(encoding="utf-8"))
    es = json.loads((root / "setup_segments.es.json").read_text(encoding="utf-8"))
    assert set(en) == set(es) == {"seg_err_not_numeric", "seg_err_out_of_range", "seg_err_too_many"}
