"""Regresion visual a 1440x900 contra tests/e2e/baseline/*.png (ver tests/e2e/README.md).

Baselines: dependen de fuentes y del renderer (Edge/Chromium en Windows). En otra maquina
pueden requerir regenerarse:  E2E=1 E2E_UPDATE_BASELINE=1 python -m pytest tests/e2e -k visual
"""
from __future__ import annotations

import re

import pytest

from tests.e2e.conftest import open_app, settle, upload_and_analyze
from tests.e2e.visual import check_screenshot

pytestmark = pytest.mark.e2e


def _to_top(pg, selector: str):
    pg.locator(selector).first.evaluate("e => e.scrollIntoView({block: 'start', behavior: 'instant'})")
    settle(pg, 900)


def test_visual_landing(page):
    open_app(page, "en")
    settle(page)
    check_screenshot(page, "landing_en")


@pytest.fixture
def analyzed_stable(analyzed):
    settle(analyzed, 2500)
    return analyzed


def test_visual_overview(analyzed_stable):
    pg = analyzed_stable
    _to_top(pg, "#section-overview")
    check_screenshot(pg, "overview_en")


def test_visual_data_quality(analyzed_stable):
    pg = analyzed_stable
    _to_top(pg, "#data-quality")
    check_screenshot(pg, "data_quality_en")


def test_visual_optimal_lap(analyzed_stable):
    pg = analyzed_stable
    pg.locator("#optimal-lap").get_by_text(re.compile(r"\d:\d{2}\.\d{3}")).first.wait_for(timeout=60000)
    _to_top(pg, "#optimal-lap")
    check_screenshot(pg, "optimal_lap_en")


def test_visual_stint(analyzed_stable):
    pg = analyzed_stable
    _to_top(pg, "#section-stint")
    check_screenshot(pg, "stint_en")


def test_visual_library_with_masked_dates(analyzed_stable):
    pg = analyzed_stable
    pg.locator("button[aria-haspopup='dialog']").click()
    dialog = pg.get_by_role("dialog")
    dialog.locator("input").first.fill("Baseline session")
    dialog.locator("button[type=submit]").click()
    pg.wait_for_function("() => !document.querySelector('[role=dialog]')", timeout=30000)
    pg.locator(".shell-appbar nav .ui-seg__item").nth(1).click()
    pg.locator("table.ui-table tbody tr").first.wait_for(timeout=30000)
    settle(pg, 800)
    check_screenshot(pg, "library_en", mask=[pg.locator("table.ui-table tbody td[class*='nowrap']")])
