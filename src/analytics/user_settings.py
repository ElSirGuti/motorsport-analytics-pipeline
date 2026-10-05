"""
User settings kept by the server: folders the user points the app to (Assetto Corsa setups, AC install).

Stored as JSON in ``SETTINGS_FILE`` > ``STORAGE_DIR/settings.json`` > ``./data/settings.json``.
Resolution order for every folder: this file (set from the UI) > environment variable > automatic detection.

Security: a folder is only ever stored if it is an existing directory, and the readers that use it keep
their own limits (setups: only ``.ini`` / ``.sp`` files <= 256 KB, names matched against the real listing).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

KEYS = ("ac_setups_dir", "ac_install_dir")
_lock = threading.Lock()


class SettingsError(ValueError):
    """Invalid value (not a folder, not found...). ``code`` is the i18n suffix."""

    def __init__(self, code: str, **kw):
        super().__init__(code)
        self.code, self.kw = code, kw


def settings_path() -> Path:
    explicit = os.getenv("SETTINGS_FILE", "").strip()
    if explicit:
        return Path(explicit)
    storage = os.getenv("STORAGE_DIR", "").strip() or "./data"
    return Path(storage) / "settings.json"


def _read() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str) -> Optional[str]:
    """The configured folder for ``key`` or None."""
    v = _read().get(key)
    return v.strip() if isinstance(v, str) and v.strip() else None


def validate_dir(value: str) -> Path:
    v = (value or "").strip().strip('"')
    if not v:
        raise SettingsError("empty")
    if len(v) > 1024 or "\0" in v:
        raise SettingsError("invalid")
    p = Path(v).expanduser()
    if not p.is_absolute():
        raise SettingsError("not_absolute")
    try:
        if not p.exists():
            raise SettingsError("not_found")
        if not p.is_dir():
            raise SettingsError("not_a_dir")
        os.listdir(p)
    except PermissionError:
        raise SettingsError("no_permission")
    except OSError:
        raise SettingsError("not_found")
    return p


def save(updates: dict) -> dict:
    """Apply ``{key: path | None}``. None / '' clears the key (back to automatic). Atomic write."""
    for k in updates:
        if k not in KEYS:
            raise SettingsError("unknown_key", name=k)
    cleaned = {}
    for k, v in updates.items():
        cleaned[k] = None if v is None or not str(v).strip() else str(validate_dir(str(v)))
    with _lock:
        data = _read()
        for k, v in cleaned.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
        path = settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("settings not saved: %s", exc)
            raise SettingsError("not_writable")
    return data
