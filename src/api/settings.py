"""Folders the user points the app to (see src/analytics/user_settings.py): GET / PUT /api/settings/paths."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import subprocess
import sys

from fastapi import APIRouter, Body, HTTPException, Query, Request

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


_PICKER = "; ".join([
    "import sys, tkinter as tk",
    "from tkinter import filedialog",
    "r = tk.Tk()",
    "r.withdraw()",
    "r.attributes('-topmost', True)",
    "print(filedialog.askdirectory(initialdir=sys.argv[1] or None, title=sys.argv[2], mustexist=True) or '')",
])
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _in_container() -> bool:
    return os.path.exists("/.dockerenv") or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))


def picker_available() -> bool:
    """A native folder dialog only makes sense when the backend runs on the user's own desktop."""
    if _in_container():
        return False
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def pick_folder_dialog(initial: str, title: str) -> str:
    """Opens the OS folder dialog in a child process (Tk must not run inside the server's threads)."""
    proc = subprocess.run([sys.executable, "-c", _PICKER, initial or "", title],
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip()[-200:] or "dialog failed")
    out = (proc.stdout or "").strip()
    return str(Path(out)) if out else ""


@router.post("/pick-folder")
def pick_folder(request: Request, payload: dict = Body(...), lang: str = Query("en")):
    """Native "choose folder" dialog on the machine running the backend. 501 when there is no desktop
    (Docker, Kubernetes, headless), 403 when the request does not come from the same computer."""
    lang = _lang(lang)
    key = payload.get("key")
    if key not in us.KEYS:
        raise HTTPException(status_code=400, detail=_l(lang, "settings_err_unknown_key", name=key))
    if not picker_available():
        raise HTTPException(status_code=501, detail=_l(lang, "settings_err_picker_unavailable"))
    host = request.client.host if request.client else ""
    if host not in _LOOPBACK or request.headers.get("x-forwarded-for"):
        raise HTTPException(status_code=403, detail=_l(lang, "settings_err_picker_remote"))
    start = str(payload.get("path") or "") or (us.get(key) or "")
    if not start or not os.path.isdir(start):
        start = ""
    try:
        chosen = pick_folder_dialog(start, _l(lang, f"settings_pick_title_{key}"))
    except (RuntimeError, OSError, subprocess.SubprocessError):
        raise HTTPException(status_code=501, detail=_l(lang, "settings_err_picker_unavailable"))
    return {"path": chosen or None, "cancelled": not chosen}


@router.get("/paths")
def get_paths():
    return _all()


@router.get("/capabilities")
def capabilities():
    return {"folder_picker": picker_available()}


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
