"""Folders configured from the UI: validation, persistence and precedence over env / auto detection."""
import json

import pytest
from fastapi.testclient import TestClient

import main
from src.analytics import ac_setups, user_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.delenv("AC_SETUPS_DIR", raising=False)
    return TestClient(main.app)


def _setups_tree(root):
    (root / "ks_car" / "monza").mkdir(parents=True)
    (root / "ks_car" / "monza" / "mine.ini").write_text("[FRONT_BIAS]\nVALUE=60\n", encoding="utf-8")
    return root


def test_save_and_use_setups_folder(client, tmp_path):
    folder = _setups_tree(tmp_path / "my setups")
    r = client.put("/api/settings/paths", json={"ac_setups_dir": str(folder)})
    assert r.status_code == 200
    st = r.json()["paths"]["ac_setups_dir"]
    assert st["source"] == "settings" and st["exists"] and st["details"]["n_cars"] == 1
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["ac_setups_dir"] == str(folder)
    found = client.get("/api/setups/candidates", params={"vehicle": "ks_car", "venue": "monza"}).json()
    assert found["state"] == "track_setups" and found["ac_setups_dir"] == str(folder)


def test_settings_beat_env_and_clearing_goes_back(client, tmp_path, monkeypatch):
    env_dir = tmp_path / "from_env"
    env_dir.mkdir()
    monkeypatch.setenv("AC_SETUPS_DIR", str(env_dir))
    assert client.get("/api/settings/paths").json()["paths"]["ac_setups_dir"]["source"] == "env"
    mine = _setups_tree(tmp_path / "mine")
    client.put("/api/settings/paths", json={"ac_setups_dir": str(mine)})
    assert ac_setups.resolve_setups_dir()[0] == mine
    r = client.put("/api/settings/paths", json={"ac_setups_dir": None})
    assert r.json()["paths"]["ac_setups_dir"]["source"] == "env"
    assert ac_setups.resolve_setups_dir()[0] == env_dir


@pytest.mark.parametrize("value,msg", [
    ("", None), ("relative/path", "full path"), ("Z:\definitely\not\here", "cannot find"),
])
def test_invalid_paths_are_rejected_with_a_message(client, value, msg):
    r = client.put("/api/settings/paths", json={"ac_setups_dir": value}) if value else None
    if r is None:
        # an empty value clears the setting (back to automatic), it is not an error
        assert client.put("/api/settings/paths", json={"ac_setups_dir": ""}).status_code == 200
        return
    assert r.status_code == 400 and msg in r.json()["detail"]


def test_file_instead_of_folder_and_unknown_key(client, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert client.put("/api/settings/paths", json={"ac_setups_dir": str(f)}).status_code == 400
    assert client.put("/api/settings/paths", json={"nope": str(tmp_path)}).status_code == 400
    assert not (tmp_path / "settings.json").exists()


def test_check_does_not_save_and_describes_the_install(client, tmp_path):
    root = tmp_path / "assettocorsa"
    (root / "content" / "cars" / "a").mkdir(parents=True)
    (root / "content" / "tracks").mkdir(parents=True)
    r = client.post("/api/settings/paths/check", json={"key": "ac_install_dir", "path": str(root)}).json()
    assert r["ok"] and r["details"] == {"has_cars": True, "has_tracks": True, "n_cars": 1, "n_tracks": 0}
    assert user_settings.get("ac_install_dir") is None
    client.put("/api/settings/paths", json={"ac_install_dir": str(root)})
    assert ac_setups._ac_roots()[0] == root


def test_spanish_error_text(client):
    r = client.put("/api/settings/paths?lang=es", json={"ac_setups_dir": "relative"})
    assert "ruta completa" in r.json()["detail"]
