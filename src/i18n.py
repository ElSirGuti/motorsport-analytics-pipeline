"""
Lightweight i18n module for the motorsport analytics pipeline.

Uses JSON locale files and a context variable for thread-safe language switching.
"""

import json
import os
from contextvars import ContextVar

DEFAULT_LANG = "en"
from typing import Optional

_current_lang: ContextVar[str] = ContextVar("current_lang", default="es")

_locales: dict[str, dict[str, str]] = {}
_LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


def _load_locale(lang: str) -> dict[str, str]:
    path = os.path.join(_LOCALE_DIR, f"{lang}.json")
    if not os.path.exists(path):
        path = os.path.join(_LOCALE_DIR, "es.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_locale(lang: Optional[str] = None) -> dict[str, str]:
    lang = lang or _current_lang.get()
    if lang not in _locales:
        _locales[lang] = _load_locale(lang)
    return _locales[lang]


def set_language(lang: str) -> None:
    _current_lang.set(lang)


def get_language() -> str:
    return _current_lang.get()


def _(key: str, **kwargs) -> str:
    """Translate a key using the current language's locale, formatting with kwargs."""
    locale = get_locale()
    template = locale.get(key)
    if template is None:
        return key
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


def _l(lang: str, key: str, **kwargs) -> str:
    """Translate a key using a specific language."""
    locale = get_locale(lang)
    template = locale.get(key)
    if template is None:
        return key
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


class LanguageContext:
    """Context manager for temporary language switching."""

    def __init__(self, lang: str):
        self.lang = lang
        self._token = None

    def __enter__(self):
        self._token = _current_lang.set(self.lang)
        return self

    def __exit__(self, *args):
        if self._token is not None:
            _current_lang.reset(self._token)
