"""Folders the user points the app to (see src/analytics/user_settings.py): GET / PUT /api/settings/paths."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.analytics import ac_setups as ac
from src.analytics import user_settings as us
from src.i18n import _l

router = APIRouter(prefix="/api/settings", tags=["settings"])

_ENV = {"ac_setups_dir": ("AC_SETUPS_DIR",), "ac_install_dir": ("AC_ROOT", "AC_INSTALL_DIR")}


def _lang(lang: Optional[str]) -> str:
    return lang if lang in ("es", "en") else "en"


def _subdirs(p: Path) -> int:
    try:
        return sum(1 for e in os.scandir(p) if e.is_dir())
    except OSError:
        return 0


def _details(key: str, path: Optional[Path]) -> dict:
    if path is None:
        return {}
    try:
        if key == "ac_setups_dir":
            return {"n_cars": _subdirs(path)}
        cars, tracks = path / "content" / "cars", path / "content" / "tracks"
        return {"has_cars": cars.is_dir(), "has_tracks": tracks.is_dir(),
                "n_cars": _subdirs(cars) if cars.is_dir() else 0,
                "n_tracks": _subdirs(tracks) if tracks.is_dir() else 0}
    except OSError:
        return {}


def _effective(key: str) -> tuple[Optional[Path], bool]:
    if key == "ac_setups_dir":
        return ac.resolve_setups_dir()
    for root in ac._ac_roots():
        try:
            if (root / "content").is_dir():
                return root, True
        except OSError:
            continue
    return None, False


def _status(key: str) -> dict:
    configured = us.get(key)
    env = next((os.environ.get(e, "").strip() for e in _ENV[key] if os.environ.get(e, "").strip()), "")
    path, exists = _effective(key)
    source = "settings" if configured else ("env" if env else ("auto" if exists else None))
    return {"key": key, "configured": configured, "env": env or None, "effective": str(path) if path else None,
            "exists": bool(exists), "source": source, "details": _details(key, path if exists else None)}


def _all() -> dict:
    return {"paths": {k: _status(k) for k in us.KEYS}, "settings_file": str(us.settings_path())}


def _fail(exc: us.SettingsError, lang: str):
    return HTTPException(status_code=400, detail=_l(lang, f"settings_err_{exc.code}", **exc.kw))


@router.get("/paths")
def get_paths():
    return _all()


@router.post("/paths/check")
def check_path(payload: dict = Body(...), lang: str = Query("en")):
    """Validate a folder without saving it and say what it contains."""
    key = payload.get("key")
    if key not in us.KEYS:
        raise HTTPException(status_code=400, detail=_l(_lang(lang), "settings_err_unknown_key", name=key))
    try:
        p = us.validate_dir(str(payload.get("path") or ""))
    except us.SettingsError as exc:
        raise _fail(exc, _lang(lang))
    return {"key": key, "path": str(p), "ok": True, "details": _details(key, p)}


@router.put("/paths")
def put_paths(payload: dict = Body(...), lang: str = Query("en")):
    """Set (a path) or clear (null / empty) one or more folders."""
    try:
        us.save(dict(payload))
    except us.SettingsError as exc:
        raise _fail(exc, _lang(lang))
    return _all()
