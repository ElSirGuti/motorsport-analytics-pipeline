"""Selector de tema: aplica data-theme, persiste y cambiar no dispara peticiones ni pierde estado."""
from __future__ import annotations

import pytest

from tests.e2e.conftest import i18n

pytestmark = pytest.mark.e2e


def _theme(pg):
    return pg.evaluate("document.documentElement.dataset.theme")


def test_theme_switch_keeps_state_and_persists(analyzed):
    pg = analyzed
    api_calls = []
    pg.on("request", lambda r: api_calls.append(r.url) if "/api/" in r.url else None)
    laps_before = pg.locator("table.ui-table tbody tr.shell-laprow").count()

    pg.get_by_role("button", name=i18n("en", "themeLight"), exact=True).click()
    assert _theme(pg) == "light"
    bg_light = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    pg.get_by_role("button", name=i18n("en", "themeDark"), exact=True).click()
    assert _theme(pg) == "dark"
    # The background may still be mid-transition right after the click: wait for it to settle.
    pg.wait_for_function(
        "bg => getComputedStyle(document.body).backgroundColor !== bg", arg=bg_light, timeout=5000
    )

    assert api_calls == [], f"theme change fired requests: {api_calls}"
    assert pg.locator("#section-overview").is_visible()
    assert pg.locator("table.ui-table tbody tr.shell-laprow").count() == laps_before
    assert pg.evaluate("localStorage.getItem('ma-theme')") == "dark"

    pg.reload()
    assert _theme(pg) == "dark"
    assert pg.errors == [], "\n".join(pg.errors)
