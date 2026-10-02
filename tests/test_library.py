"""Biblioteca de sesiones: modelos, CRUD, dedupe, comparacion, validacion y limites (SQLite en memoria)."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.analytics import session_compare as sc
from src.api import library
from src.db import Base, LibrarySession, get_db
from src.db.session import init_db, make_engine, normalize_url


@pytest.fixture()
def client():
    engine = make_engine("sqlite://")
    init_db(engine, use_migrations=False)
    Maker = sessionmaker(bind=engine, expire_on_commit=False)

    def _db():
        db = Maker()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(library.router)
    app.dependency_overrides[get_db] = _db
    c = TestClient(app)
    c.maker = Maker
    return c


def make_payload(times, corner_losses=None, deg=0.05, fuel=2.0, with_apex=False):
    laps = [{"lap_number": i + 1, "lap_time_s": t, "is_pit_lap": False} for i, t in enumerate(times)]
    laps.append({"lap_number": len(times) + 1, "lap_time_s": 200.0, "is_pit_lap": True})
    corners = [
        {"corner_number": i + 1, "time_loss_seconds": v, **({"apex_distance_m": 100.0 * (i + 1)} if with_apex else {})}
        for i, v in enumerate(corner_losses or [])
    ]
    return {
        "session": {"laps": [{"lap_number": i + 1, "lap_time": t, "is_pit_lap": False} for i, t in enumerate(times)],
                    "fastest_lap": {"lap_number": 1, "lap_time": min(times)}, "total_laps": len(times)},
        "stint": {
            "n_laps": len(laps), "laps": laps,
            "degradacion": {"available": True, "tasa_s_per_lap": deg},
            "combustible": {"available": True, "consumo_medio_l": fuel},
            "curvas_sesion": {"available": bool(corners), "corners": corners},
        },
        "extras": {"optimal_lap": {"time": 98.1}},
    }


def save(client, payload, **meta):
    body = {"title": "S", "venue": "Imola", "vehicle": "GT4", "file_sha256": uuid.uuid4().hex * 2, "payload": payload}
    body.update(meta)
    return client.post("/api/library", json=body)


# ── Modelo ────────────────────────────────────────────────────────────────────
def test_model_roundtrip_and_owner_nullable():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    Maker = sessionmaker(bind=engine)
    with Maker() as db:
        row = LibrarySession(title="x", payload={"a": [1, 2, {"b": None}]})
        db.add(row)
        db.commit()
        rid = row.id
    with Maker() as db:
        got = db.get(LibrarySession, rid)
        assert isinstance(got.id, uuid.UUID)
        assert got.owner_id is None and got.payload == {"a": [1, 2, {"b": None}]}
        assert got.created_at is not None and got.updated_at is not None


def test_init_db_idempotent_with_migrations(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    engine = make_engine()
    init_db(engine)       # alembic upgrade head
    init_db(engine)       # segunda vez: no falla
    Base.metadata.create_all(engine)  # create_all tras alembic tampoco falla
    from sqlalchemy import inspect
    assert "library_sessions" in inspect(engine).get_table_names()


def test_normalize_url():
    assert normalize_url("postgresql://u:p@h:5432/d").startswith("postgresql+psycopg://")
    assert normalize_url("postgresql+psycopg://u:p@h/d").startswith("postgresql+psycopg://")
    assert normalize_url("sqlite://") == "sqlite://"


# ── CRUD ──────────────────────────────────────────────────────────────────────
def test_crud_flow(client):
    r = save(client, make_payload([100.0, 101.0, 100.5]), title="Mi sesion", notes="n1")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "created" and data["duplicate"] is False
    sid = data["session"]["id"]
    assert data["session"]["best_lap_s"] == 100.0 and data["session"]["n_laps"] == 3

    lst = client.get("/api/library").json()
    assert lst["total"] == 1 and "payload" not in lst["items"][0]

    full = client.get(f"/api/library/{sid}").json()
    assert full["payload"]["extras"]["optimal_lap"]["time"] == 98.1
    assert full["payload"]["stint"]["laps"][0]["lap_time_s"] == 100.0

    p = client.patch(f"/api/library/{sid}", json={"title": "Renombrada", "notes": None})
    assert p.status_code == 200 and p.json()["title"] == "Renombrada" and p.json()["notes"] is None
    assert client.patch(f"/api/library/{sid}", json={"title": "  "}).status_code in (422, 400)
    assert client.patch(f"/api/library/{sid}", json={"bogus": 1}).status_code == 422

    assert client.delete(f"/api/library/{sid}").json()["status"] == "deleted"
    assert client.get(f"/api/library/{sid}").status_code == 404
    assert client.delete(f"/api/library/{sid}").status_code == 404
    assert client.get("/api/library/not-a-uuid").status_code == 422


def test_dedupe_by_sha_and_venue(client):
    sha = "ab" * 32
    r1 = save(client, make_payload([100.0, 101.0]), file_sha256=sha, title="Primera")
    r2 = save(client, make_payload([99.0, 101.0]), file_sha256=sha, title="Otra")
    assert r2.json()["status"] == "updated" and r2.json()["duplicate"] is True
    assert r2.json()["session"]["id"] == r1.json()["session"]["id"]
    assert r2.json()["session"]["title"] == "Primera"          # conserva el titulo
    assert r2.json()["session"]["best_lap_s"] == 99.0           # pero actualiza los resultados
    # mismo archivo en otro circuito = otra sesion
    r3 = save(client, make_payload([99.0, 101.0]), file_sha256=sha, venue="Spa")
    assert r3.json()["status"] == "created"
    assert client.get("/api/library").json()["total"] == 2


def test_dedupe_without_sha_uses_content_fingerprint(client):
    p = make_payload([100.0, 101.0])
    body = {"venue": "Imola", "payload": p}
    assert client.post("/api/library", json=body).json()["status"] == "created"
    assert client.post("/api/library", json=body).json()["status"] == "updated"


def test_list_filters_and_pagination(client):
    save(client, make_payload([100.0, 101.0]), title="Quali Imola", venue="Imola", vehicle="GT4")
    save(client, make_payload([140.0, 141.0]), title="Race Spa", venue="Spa", vehicle="GT4", notes="lluvia")
    save(client, make_payload([90.0, 91.0]), title="Otro", venue="Imola", vehicle="GT3")
    g = lambda **q: client.get("/api/library", params=q).json()
    assert g()["total"] == 3
    assert g(venue="imola")["total"] == 2
    assert g(venue="Imola", vehicle="gt3")["total"] == 1
    assert g(q="lluvia")["items"][0]["title"] == "Race Spa"
    assert g(q="100%")["total"] == 0                      # comodines escapados
    assert len(g(limit=2)["items"]) == 2 and g(limit=2, offset=2)["items"].__len__() == 1
    assert g(date_from="2999-01-01")["total"] == 0
    assert g(date_to="2999-01-01")["total"] == 3
    assert client.get("/api/library", params={"limit": 0}).status_code == 422
    f = client.get("/api/library/facets").json()
    assert {v["value"] for v in f["venues"]} == {"Imola", "Spa"}
    assert {v["value"]: v["count"] for v in f["vehicles"]}["GT4"] == 2


# ── Validacion y limites ──────────────────────────────────────────────────────
def test_validation(client):
    assert client.post("/api/library", json={"payload": {}}).status_code == 422     # sin session ni stint
    assert client.post("/api/library", json={"title": "x"}).status_code == 422      # sin payload
    assert client.post("/api/library", json={"payload": {"session": {"laps": []}}, "file_sha256": "zz"}).status_code == 422
    assert client.post("/api/library", content=b"{not json", headers={"content-type": "application/json"}).status_code == 422
    assert client.post("/api/library", json={"title": "x" * 201, "payload": {"session": {}}}).status_code == 422


def test_nan_is_sanitized(client):
    p = make_payload([100.0, 101.0])
    p["stint"]["laps"][0]["x"] = float("nan")
    body = '{"venue":"I","payload":' + __import__("json").dumps(p) + "}"
    r = client.post("/api/library", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 200
    sid = r.json()["session"]["id"]
    assert client.get(f"/api/library/{sid}").json()["payload"]["stint"]["laps"][0]["x"] is None


def test_payload_size_limit(client, monkeypatch):
    monkeypatch.setattr(library, "MAX_PAYLOAD_BYTES", 2000)
    big = {"session": {"laps": [{"lap_number": i, "lap_time": 100.0} for i in range(500)]}}
    r = client.post("/api/library", json={"payload": big})
    assert r.status_code == 413
    assert "MB" in r.json()["detail"]


# ── Comparacion ───────────────────────────────────────────────────────────────
def test_compare_pure_functions():
    a = make_payload([100.0, 101.0, 102.0], [0.2, 0.1, 0.3])
    b = make_payload([99.5, 100.0, 100.5], [0.1, 0.1, 0.5], deg=0.02, fuel=2.5)
    out = sc.compare_sessions(a, b, "en")
    assert out["kpis"]["best"]["delta"] == -0.5
    assert out["kpis"]["mean"]["a"] == pytest.approx(101.0) and out["kpis"]["mean"]["delta"] == pytest.approx(-1.0)
    assert out["kpis"]["median"]["delta"] == pytest.approx(-1.0)
    assert out["kpis"]["std"]["a"] == pytest.approx(1.0) and out["kpis"]["std"]["delta"] == pytest.approx(-0.5)
    assert [c["delta"] for c in out["corners"]["items"]] == [-0.1, 0.0, 0.2]
    assert out["corners"]["matched_by"] == "corner_number"
    assert out["degradation"]["delta"] == pytest.approx(-0.03)
    assert out["fuel"]["delta"] == pytest.approx(0.5)
    assert len(out["series"]["laps"]) == 3          # el pit lap no cuenta
    assert any("faster" in s for s in out["summary"])
    es = sc.compare_sessions(a, b, "es")
    assert any("más rápida" in s for s in es["summary"])


def test_corner_matching_by_apex_distance():
    ca = [{"corner_number": 1, "time_loss_seconds": 0.1, "apex_distance_m": 100},
          {"corner_number": 2, "time_loss_seconds": 0.2, "apex_distance_m": 500}]
    cb = [{"corner_number": 1, "time_loss_seconds": 0.3, "apex_distance_m": 510},   # B numera distinto
          {"corner_number": 2, "time_loss_seconds": 0.0, "apex_distance_m": 1500}]  # sin pareja (>60 m)
    pairs, how = sc.match_corners(ca, cb)
    assert how == "apex_distance" and len(pairs) == 1
    assert pairs[0][0]["corner_number"] == 2 and pairs[0][1]["time_loss_seconds"] == 0.3


def test_compare_handles_missing_data():
    out = sc.compare_sessions({"session": {"laps": []}}, {"stint": {}}, "en")
    assert out["kpis"]["best"]["delta"] is None and out["corners"]["available"] is False
    assert out["summary"] == ["Not enough data to compare these sessions."]


def test_compare_endpoint_and_compat(client):
    a = save(client, make_payload([100.0, 101.0, 102.0], [0.2, 0.1]), title="A").json()["session"]["id"]
    b = save(client, make_payload([99.0, 100.0, 101.0], [0.1, 0.3]), title="B").json()["session"]["id"]
    r = client.post("/api/library/compare?lang=en", json={"a": a, "b": b})
    assert r.status_code == 200
    d = r.json()
    assert d["kpis"]["best"]["delta"] == -1.0 and d["a"]["id"] == a and d["forced"] is False
    assert d["compatibility"]["compatible"] is True
    assert len(d["corners"]["items"]) == 2

    spa = save(client, make_payload([140.0, 141.0, 142.0]), venue="Spa").json()["session"]["id"]
    bad = client.post("/api/library/compare?lang=en", json={"a": a, "b": spa})
    assert bad.status_code == 400 and "circuit" in bad.json()["detail"]
    assert client.post("/api/library/compare?lang=es", json={"a": a, "b": spa}).json()["detail"].count("circuito") == 1
    forced = client.post("/api/library/compare", json={"a": a, "b": spa, "force": True})
    assert forced.status_code == 200 and forced.json()["forced"] is True

    assert client.post("/api/library/compare", json={"a": a, "b": a}).status_code == 400
    assert client.post("/api/library/compare", json={"a": a, "b": str(uuid.uuid4())}).status_code == 404
    assert client.post("/api/library/compare", json={"a": "x", "b": a}).status_code == 422


def test_compare_unknown_venue_is_compatible_with_warning(client):
    a = save(client, make_payload([100.0, 101.0, 102.0]), venue=None).json()["session"]["id"]
    b = save(client, make_payload([99.0, 100.0, 101.0]), venue="Imola").json()["session"]["id"]
    r = client.post("/api/library/compare?lang=en", json={"a": a, "b": b})
    assert r.status_code == 200 and r.json()["warnings"]


def test_sniff_pretty_names(client):
    csv = b'"Format","MoTeC CSV File"\n"Venue","fn_imola"\n"Vehicle","ks_porsche_cayman_gt4_clubsport"\n"Driver","Ana Perez"\n'
    r = client.post("/api/library/sniff", files={"head": ("h.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.json() == {"venue": "Imola", "vehicle": "Porsche Cayman GT4 Clubsport", "driver": "Ana Perez",
                        "raw": {"driver": "Ana Perez", "vehicle": "ks_porsche_cayman_gt4_clubsport", "venue": "fn_imola"}}
