"""Flujos e2e en navegador real (Edge via Playwright) contra backend + vite levantados por conftest.

Se omiten salvo E2E=1. Los selectores usan roles, ids estables (#section-*, #data-quality,
#optimal-lap) y textos leidos de frontend/src/i18n por clave, no cadenas escritas a mano.
"""
from __future__ import annotations

import os
import re
import sqlite3

import pytest

from tests.e2e.conftest import i18n, open_app, set_lang, settle, upload_and_analyze

pytestmark = pytest.mark.e2e


def _no_errors(pg):
    assert pg.errors == [], "browser errors:\n" + "\n".join(pg.errors)


def _nav(pg, idx: int):
    """Botones de la barra superior: 0 Analisis, 1 Biblioteca, 2 Comparar sesiones."""
    pg.locator(".shell-appbar nav .ui-seg__item").nth(idx).click()


def _pick_laps(pg, a: int, b: int):
    for n in (a, b):
        pg.get_by_role("button", name=f"{i18n('en', 'lapCol')} {n}", exact=True).click()


# 1 ── humo ───────────────────────────────────────────────────────────────────
def test_smoke_upload_analyze(analyzed):
    pg = analyzed
    assert pg.locator("#section-overview").is_visible()
    assert pg.locator("#section-stint").count() == 1
    assert pg.locator("#data-quality").is_visible(), "data quality panel missing"
    assert pg.locator("#optimal-lap").count() == 1, "optimal lap panel missing"
    # el panel de vuelta optima termina de cargar: aparece al menos un tiempo con formato m:ss.mmm
    pg.locator("#optimal-lap").get_by_text(re.compile(r"\d:\d{2}\.\d{3}")).first.wait_for(timeout=60000)
    # tabla de vueltas: 5 vueltas (un boton de seleccion por vuelta)
    rows = pg.locator("table.ui-table tbody tr.shell-laprow")
    assert rows.count() == 5
    assert pg.locator("button.shell-pick").count() == 5
    _no_errors(pg)


# 2 ── comparacion de dos vueltas ─────────────────────────────────────────────
def test_compare_two_laps(analyzed):
    pg = analyzed
    _pick_laps(pg, 4, 3)
    pg.locator(".shell-lapbar__actions .ui-btn--primary").click()
    pg.locator("#section-core-lap").wait_for(timeout=120000)
    settle(pg)
    for sid in ("section-core-lap", "section-strategy"):
        assert pg.locator(f"#{sid}").count() == 1, sid
    assert pg.locator(".shell-cmphead__title").inner_text().strip()
    _no_errors(pg)


# 3 ── idioma ─────────────────────────────────────────────────────────────────
def test_language_switch_without_reload(analyzed):
    pg = analyzed
    pg.evaluate("window.__no_reload_marker = 42")
    head = pg.locator("#section-overview h2, #section-overview h3").first
    en_title = i18n("en", "secOverview")
    assert en_title in head.inner_text()
    set_lang(pg, "es")
    assert i18n("es", "secOverview") in pg.locator("#section-overview h2, #section-overview h3").first.inner_text()
    assert pg.evaluate("window.__no_reload_marker") == 42, "language switch reloaded the page"
    assert pg.locator("#section-overview").is_visible() and pg.locator("#section-stint").count() == 1
    set_lang(pg, "en")
    assert en_title in pg.locator("#section-overview h2, #section-overview h3").first.inner_text()
    _no_errors(pg)


EN_STOP = {"the", "and", "with", "for", "of", "is", "are", "to", "your", "this", "that", "from", "than",
           "more", "less", "not", "you", "was", "were", "has", "have", "be", "by", "on", "in", "at", "or",
           "but", "which", "when", "while", "during", "between", "per", "lap", "laps", "corner", "braking",
           "best", "pace", "session", "no", "data"}
ES_STOP = {"el", "la", "los", "las", "un", "una", "de", "del", "en", "con", "para", "por", "que", "es",
           "son", "tu", "tus", "se", "al", "más", "menos", "no", "y", "o", "como", "esta", "este", "sin",
           "entre", "vuelta", "vueltas", "curva", "frenada", "mejor", "ritmo", "sesión", "datos", "se"}
# Terminos tecnicos / nombres propios que se dejan en ingles a proposito (sin traducir).
ALLOWED = re.compile(
    r"Monte Carlo|P10|P25|P50|P75|P90|Setup|setup|Brake bias|Brake Bias|ABS|TC|G-G|GG|Pit|pit|RPM|ACTI|MoTeC|"
    r"Assetto Corsa|iRacing|CSV|PDF|JSON|\.ibt|\.ld|Slick|Hard|PRACTICE|HOTLAP|RACE|QUALIFY|v\d+\.\d+\.\d+|"
    r"Motorsport Analytics|The Automated Analyst|km/h|OK|IA|AI|RL|R²|Delta|delta|Slip|slip|Throttle|Brake|"
    r"Speed|Gear|Fuel|fuel|Online|Offline",
)
VERBOSE = bool(os.environ.get("E2E_LANG_VERBOSE"))
_TEXT_JS = """() => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, t = n.textContent.trim();
    const el = n.parentElement;
    if (!t || !el || ['SCRIPT','STYLE','NOSCRIPT','CODE'].includes(el.tagName)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    out.push(t);
  }
  document.querySelectorAll('[aria-label],[title]').forEach(e => {
    ['aria-label','title'].forEach(a => { const v = e.getAttribute(a); if (v) out.push(v); });
  });
  return out;
}"""


def english_leaks(texts):
    """Textos que parecen ingles dentro de una pagina en espanol (heuristica de stopwords)."""
    leaks = []
    for raw in texts:
        t = ALLOWED.sub(" ", raw)
        t = re.sub(r"[\w.-]*_[\w.-]*", " ", t)          # identificadores (ks_porsche..., imola_5laps.csv)
        words = re.findall(r"[a-záéíóúñü]+", t.lower())
        if len(words) < 3:
            continue
        en = sum(w in EN_STOP for w in words)
        es = sum(w in ES_STOP for w in words)
        if en >= 2 and en > es:
            leaks.append(raw)
        elif VERBOSE and en >= 1 and es == 0:
            print(f"[lang sweep] near miss: {raw[:120]!r}")
    return leaks


def test_english_leak_heuristic_itself():
    assert english_leaks(["Braking too early in the corner"])
    assert not english_leaks(["Frenaste demasiado pronto en la curva"])
    assert not english_leaks(["Monte Carlo P10 – P90 Setup Brake bias"])


def test_no_residual_english_in_spanish(page, imola_csv):
    open_app(page, "es")
    upload_and_analyze(page, imola_csv)
    page.locator("#optimal-lap").get_by_text(re.compile(r"\d:\d{2}\.\d{3}")).first.wait_for(timeout=60000)
    settle(page)
    # recorre la pagina para montar los graficos perezosos
    for sid in ("#section-stint", "#section-setup"):
        if page.locator(sid).count():
            page.locator(sid).scroll_into_view_if_needed()
            page.wait_for_timeout(600)
    texts = page.evaluate(_TEXT_JS)
    assert len(texts) > 100, "page produced suspiciously little text"
    leaks = english_leaks(texts)
    print(f"[lang sweep] {len(texts)} text nodes scanned, {len(leaks)} flagged")
    assert not leaks, "English text found in the Spanish UI:\n  " + "\n  ".join(sorted(set(leaks))[:25])
    _no_errors(page)


# 4 ── modo piloto ────────────────────────────────────────────────────────────
def test_pilot_mode_hides_technical_sections(analyzed):
    pg = analyzed
    _pick_laps(pg, 4, 3)
    pg.locator(".shell-lapbar__actions .ui-btn--primary").click()
    pg.locator("#section-core-lap").wait_for(timeout=120000)
    group = pg.get_by_role("group", name=i18n("en", "viewModeAria"))
    engineer, pilot = group.get_by_role("button").nth(0), group.get_by_role("button").nth(1)

    assert pg.locator("#section-dynamics").count() == 1 and pg.locator("#section-inputs").count() == 1
    pilot.click()
    pg.wait_for_function("() => !document.querySelector('#section-dynamics')")
    assert pg.locator("#section-dynamics").count() == 0
    assert pg.locator("#section-inputs").count() == 0
    assert pg.locator("#section-core-lap").count() == 1 and pg.locator("#section-strategy").count() == 1
    assert pilot.get_attribute("aria-pressed") == "true"
    engineer.click()
    pg.locator("#section-dynamics").wait_for()
    assert pg.locator("#section-inputs").count() == 1
    _no_errors(pg)


# 5 ── biblioteca: guardar -> listar -> abrir -> borrar ───────────────────────
def test_library_save_list_open_delete(analyzed, servers):
    pg = analyzed
    pg.locator("button[aria-haspopup='dialog']").click()
    dialog = pg.get_by_role("dialog")
    dialog.wait_for()
    title = "E2E regression session"
    dialog.locator("input").first.fill(title)
    dialog.locator("button[type=submit]").click()
    pg.wait_for_function("() => !document.querySelector('[role=dialog]')", timeout=30000)

    # persistio en la BD temporal del servidor de prueba (no en la del usuario)
    con = sqlite3.connect(servers["db"])
    try:
        n = con.execute("select count(*) from library_sessions").fetchone()[0]
    finally:
        con.close()
    assert n == 1

    _nav(pg, 1)
    row = pg.locator("table.ui-table tbody tr", has_text=title)
    row.wait_for(timeout=30000)
    assert row.count() == 1

    row.locator("button.ui-btn--primary").click()          # Abrir
    pg.locator("#section-overview").wait_for(timeout=60000)
    assert pg.locator(".shell-chip", has_text=title).count() == 1
    assert pg.locator("#section-overview").is_visible()

    _nav(pg, 1)
    row = pg.locator("table.ui-table tbody tr", has_text=title)
    row.wait_for()
    row.get_by_role("button", name=re.compile(re.escape(i18n("en", "libDelete")))).first.click()
    pg.locator("[class*='danger']").first.click()           # confirmar
    pg.wait_for_function("t => ![...document.querySelectorAll('table.ui-table tbody tr')]"
                         ".some(r => r.textContent.includes(t))", arg=title, timeout=30000)
    con = sqlite3.connect(servers["db"])
    try:
        assert con.execute("select count(*) from library_sessions").fetchone()[0] == 0
    finally:
        con.close()
    _no_errors(pg)


# 6 ── CSV vacio: error visible y traducido ───────────────────────────────────
@pytest.mark.parametrize("lang", ["en", "es"])
def test_empty_csv_shows_translated_error(page, tmp_path, lang):
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    open_app(page, lang)
    page.set_input_files("input[type=file]", str(empty))
    page.locator(".shell-actions button.ui-btn--primary").first.click()
    alert = page.get_by_role("alert").first
    alert.wait_for(timeout=60000)
    text = alert.inner_text()
    assert i18n(lang, "errorTitle") in text
    body = text.replace(i18n(lang, "errorTitle"), "").strip()
    assert body, "error message is empty"
    assert "Request failed with status code" not in body and "undefined" not in body and "[object" not in body
    other = "es" if lang == "en" else "en"
    assert i18n(other, "errorTitle") not in text
    assert page.locator("#section-overview").count() == 0
    # el mensaje del backend esta en el idioma activo
    page.evaluate("1")  # no-op: mantiene el estado
    if lang == "es":
        assert not english_leaks([body]), body
    # los unicos errores de consola admitidos son los 4xx del propio analisis fallido
    unexpected = [e for e in page.errors if "pageerror" in e]
    assert not unexpected, unexpected


# 7 ── accesibilidad basica ───────────────────────────────────────────────────
_A11Y_JS = """() => {
  const name = el => (el.getAttribute('aria-label') || '').trim()
    || (el.getAttribute('aria-labelledby') ? [...el.getAttribute('aria-labelledby').split(' ')]
        .map(i => (document.getElementById(i) || {}).textContent || '').join(' ').trim() : '')
    || (el.innerText || el.textContent || '').trim() || (el.getAttribute('title') || '').trim()
    || (el.querySelector('img[alt]') ? el.querySelector('img[alt]').getAttribute('alt').trim() : '');
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const unnamed = [...document.querySelectorAll('button, [role=button], a[href], [role=tab], [role=switch]')]
    .filter(visible).filter(el => !name(el)).map(el => el.outerHTML.slice(0, 160));
  const noAlt = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).map(i => i.outerHTML.slice(0, 160));
  const svgNoName = [...document.querySelectorAll('svg[role=img]')].filter(s => !(s.getAttribute('aria-label') || s.querySelector('title'))).length;
  const unlabeledInputs = [...document.querySelectorAll('input:not([type=hidden]):not([hidden]), select, textarea')]
    .filter(visible).filter(i => !(i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || i.closest('label')
        || (i.id && document.querySelector(`label[for="${i.id}"]`)))).map(i => i.outerHTML.slice(0, 120));
  return {unnamed, noAlt, svgNoName, unlabeledInputs};
}"""


def test_a11y_names_and_alt_after_analysis(analyzed):
    r = analyzed.evaluate(_A11Y_JS)
    assert r["noAlt"] == [], f"<img> without alt: {r['noAlt']}"
    assert r["unnamed"] == [], f"controls without accessible name: {r['unnamed']}"
    assert r["svgNoName"] == 0
    assert r["unlabeledInputs"] == [], r["unlabeledInputs"]


def test_a11y_a11y_names_on_landing(page):
    open_app(page, "en")
    r = page.evaluate(_A11Y_JS)
    assert r["noAlt"] == [] and r["unnamed"] == [] and r["unlabeledInputs"] == [], r


_FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const cs = getComputedStyle(el);
  const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 && cs.outlineColor !== 'rgba(0, 0, 0, 0)';
  const shadow = cs.boxShadow && cs.boxShadow !== 'none';
  return {tag: el.tagName, text: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
          visible: outline || !!shadow, outline: cs.outline, shadow: cs.boxShadow,
          inHeader: !!el.closest('.shell-appbar')};
}"""


def test_a11y_visible_focus_in_top_bar(page):
    open_app(page, "en")
    page.evaluate("document.activeElement && document.activeElement.blur()")
    seen = []
    for _ in range(14):
        page.keyboard.press("Tab")
        info = page.evaluate(_FOCUS_JS)
        if info is None:
            continue
        if info["inHeader"]:
            seen.append(info)
    assert len(seen) >= 5, f"expected to tab through the top bar controls, got {seen}"
    invisible = [s for s in seen if not s["visible"]]
    assert not invisible, f"focus indicator not visible on: {invisible}"


# ── comparación de DOS archivos de una vuelta (modo 'Comparar') ──────────────────────────────
_DIFFERENT_VEHICLES = re.compile("Vehículos distintos|Different vehicles")


def _compare_two_files(pg, a: str, b: str, timeout_s: int = 150) -> None:
    pg.set_input_files("input[type=file]", [a, b])
    pg.locator(".shell-actions button.ui-btn--primary").first.click()
    pg.locator("#section-core-lap").wait_for(timeout=timeout_s * 1000)
    settle(pg)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_compare_two_single_lap_files_same_car(page, single_laps, lang):
    """Mismo coche: identidad de ambas vueltas rellena y SIN aviso de vehículos distintos.

    Regresión: la UI fusiona la respuesta de /compare-laps con la de /telemetry/analyze y el metadata
    de la segunda reemplazaba al de la primera (tarjetas vacías y 'undefined vs undefined').
    """
    open_app(page, lang)
    _compare_two_files(page, single_laps["rbr_fast"], single_laps["rbr_slow"])
    text = page.locator("body").inner_text()
    assert "undefined" not in text and "[object Object]" not in text
    assert "cayman" in text.lower()  # coche visible en las tarjetas de identidad
    assert page.get_by_role("status").filter(has_text=_DIFFERENT_VEHICLES).count() == 0
    assert page.locator("#section-core-lap").is_visible()
    _no_errors(page)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_compare_two_single_lap_files_different_cars(page, single_laps, lang):
    """Coches distintos: aviso visible con los DOS nombres y sin 'undefined'."""
    open_app(page, lang)
    _compare_two_files(page, single_laps["rbr_fast"], single_laps["rbr_other_car"])
    warn = page.get_by_role("status").filter(has_text=_DIFFERENT_VEHICLES)
    assert warn.count() >= 1
    msg = warn.first.inner_text().lower()
    assert "undefined" not in msg
    assert "cayman" in msg and "maserati" in msg
    _no_errors(page)


# ── mapa de curvas unificado: curvas a fondo, sin cifras de frenada, modo legacy ─────────────
_NEW_CORNER_KEYS = {"kind", "direction", "min_radius_m", "flat_out_share", "confidence", "is_complex",
                    "sub_apexes", "start_m", "end_m", "number", "name", "braking_available",
                    "apex_available", "throttle_available", "apex_delta_available",
                    "braking_delta_available", "throttle_delta_available", "corner_kind"}


def _strip_new_fields(o):
    """Simula la respuesta con CORNER_DETECTION=legacy: sin `corner_map` ni campos nuevos."""
    if isinstance(o, dict):
        return {k: _strip_new_fields(v) for k, v in o.items() if k != "corner_map" and k not in _NEW_CORNER_KEYS}
    if isinstance(o, list):
        return [_strip_new_fields(v) for v in o]
    return o


def _corner_rows(pg):
    """Filas de la tabla 'todas las curvas' como listas de celdas."""
    t = pg.locator("[data-testid=all-corners]")
    t.wait_for(timeout=60000)
    return [[c.strip() for c in r.locator("td").all_inner_texts()] for r in t.locator("tbody tr").all()]


@pytest.mark.parametrize("lang", ["en", "es"])
def test_flat_out_corner_named_and_without_braking_figures(page, imola_csv, lang):
    open_app(page, lang)
    upload_and_analyze(page, imola_csv)
    flat = i18n(lang, "cmKind_flat_out")
    table = page.locator("[data-testid=all-corners]")
    table.scroll_into_view_if_needed()
    row = table.locator("tbody tr").filter(has_text="Variante Bassa")
    assert row.count() == 1
    assert flat in row.inner_text()
    cells = [c.strip() for c in row.locator("td").all_inner_texts()]
    assert cells[2:] == ["—", "—", "—"], f"flat-out corner must not show braking/apex/throttle figures: {cells}"
    # ninguna curva sin frenada medida (a fondo o ligera) muestra 0 m en esa columna
    for r in _corner_rows(page):
        if "—" in r[2]:
            assert not re.search(r"\b0(\.0)?\s*m\b", r[2]), r
    # marcas sobre el mapa de pista: circulos numerados con el nombre al pasar el cursor
    markers = page.locator("[data-testid=corner-markers] g[role=img]")
    assert markers.count() >= 9
    named = page.locator("[data-testid=corner-markers] g[role=img][aria-label*='Variante Bassa']")
    assert named.count() >= 1
    named.first.hover()
    assert page.locator("[data-testid=corner-markers] text", has_text="Variante Bassa").count() >= 1
    _no_errors(page)


def test_legacy_corner_detection_ui_still_works(page, imola_csv):
    """Con CORNER_DETECTION=legacy no hay corner_map ni campos nuevos: la UI sigue igual, sin errores."""
    import json as _json

    def handler(route):
        resp = route.fetch()
        try:
            body = _strip_new_fields(resp.json())
        except Exception:
            return route.fulfill(response=resp)
        route.fulfill(response=resp, body=_json.dumps(body), headers={**resp.headers, "content-type": "application/json"})

    page.route(re.compile(r".*/api/(analyze-session|stint/analyze|optimal-lap)"), handler)
    open_app(page, "en")
    upload_and_analyze(page, imola_csv)
    rows = _corner_rows(page)
    assert len(rows) >= 7
    assert all("—" not in r[2] for r in rows), "legacy corners have braking figures"
    assert page.locator("[data-testid=corner-map-notice]").count() == 0
    _no_errors(page)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_incidents_panel_shows_spin_and_cause(page, spin_csv, lang):
    """A spin in lap 2 appears in the incidents panel with its probable cause, evidence and advice."""
    open_app(page, lang)
    upload_and_analyze(page, spin_csv)
    panel = page.locator("#incidents")
    panel.scroll_into_view_if_needed()
    panel.wait_for(timeout=30000)
    assert i18n(lang, "incTitle") in panel.inner_text()
    cards = panel.locator("[data-testid=incident-card]")
    assert cards.count() == 1
    assert i18n(lang, "incKind_spin") in cards.first.inner_text()
    body = panel.inner_text().lower()
    assert ("acelerador" if lang == "es" else "throttle") in body
    assert panel.locator("svg.recharts-surface").count() >= 2        # the two small charts around the incident
    _no_errors(page)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_settings_view_saves_and_clears_a_setups_folder(page, tmp_path, lang):
    """Settings view: check, save and reset the setups folder; an invalid path shows the backend message."""
    folder = tmp_path / "my setups"
    (folder / "some_car").mkdir(parents=True)
    open_app(page, lang)
    page.get_by_role("button", name=i18n(lang, "libNavSettings"), exact=True).click()
    box = page.locator("[data-testid=path-ac_setups_dir]")
    box.wait_for(timeout=15000)
    box.fill(str(folder))
    page.get_by_role("button", name=i18n(lang, "setCheck")).first.click()
    page.get_by_text(i18n(lang, "setValid")).wait_for(timeout=10000)
    page.get_by_role("button", name=i18n(lang, "setSave")).first.click()
    page.get_by_text(i18n(lang, "setSaved")).wait_for(timeout=10000)
    status = page.locator("[data-testid=status-ac_setups_dir]")
    assert str(folder) in status.inner_text()
    assert i18n(lang, "setSource_settings") in status.inner_text()
    page.get_by_role("button", name=i18n(lang, "setUseAuto")).first.click()
    page.get_by_text(i18n(lang, "setReset")).wait_for(timeout=10000)
    assert str(folder) not in page.locator("[data-testid=status-ac_setups_dir]").inner_text()
    box.fill("relative/path")
    page.get_by_role("button", name=i18n(lang, "setCheck")).first.click()
    page.get_by_role("alert").filter(has_text="ruta completa" if lang == "es" else "full path").first.wait_for(timeout=10000)
    assert all("400" in e for e in page.errors), page.errors      # only the deliberate invalid-path request



@pytest.mark.parametrize("lang", ["en", "es"])
def test_setup_change_mid_session_splits_the_analysis(page, imola_csv, tmp_path, lang):
    """The setup changed at lap 3: the section shows one card per range, with the uploaded setup in the second."""
    ini = tmp_path / "second_setup.ini"
    ini.write_text("[FRONT_BIAS]\nVALUE=58\n[WING_1]\nVALUE=7\n", encoding="utf-8")
    open_app(page, lang)
    upload_and_analyze(page, imola_csv)
    add = page.locator("[data-testid=setup-change-add]")
    add.scroll_into_view_if_needed()
    add.click()
    page.locator("[data-testid=setup-change-lap]").select_option("3")
    page.locator("[data-testid=setup-change-form] input[type=file]").set_input_files(str(ini))
    segs = page.locator("[data-testid=setup-segment]")
    segs.nth(1).wait_for(timeout=90000)
    assert segs.count() == 2
    assert "second_setup.ini" in segs.nth(1).inner_text()
    assert "second_setup.ini" in page.locator("[data-testid=setup-changes]").inner_text()
    page.get_by_role("button", name=i18n(lang, "ssRemove")).first.click()
    page.locator("[data-testid=setup-segments]").wait_for(state="detached", timeout=10000)
    _no_errors(page)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_reloading_an_analysed_file_is_recognised(page, imola_csv, servers, lang):
    """Save a session, load the same file again: the app says it was already analysed and opens the saved one."""
    import json
    import urllib.request

    title = f"E2E duplicate {lang}"
    open_app(page, lang)
    upload_and_analyze(page, imola_csv)
    page.locator("button[aria-haspopup='dialog']").click()
    dialog = page.get_by_role("dialog")
    dialog.wait_for()
    dialog.locator("input").first.fill(title)
    dialog.locator("button[type=submit]").click()
    page.wait_for_function("() => !document.querySelector('[role=dialog]')", timeout=30000)
    try:
        page.goto(page.base_url, wait_until="networkidle")        # a fresh analysis with the same file
        set_lang(page, lang)
        page.set_input_files("input[type=file]", imola_csv)
        notice = page.locator("[data-testid=saved-match]")
        notice.wait_for(timeout=90000)
        assert title in notice.inner_text()
        assert i18n(lang, "libDupTitle") in notice.inner_text()
        page.locator("[data-testid=saved-match-open]").click()
        page.locator("#section-overview").wait_for(timeout=60000)
        assert page.locator(".shell-chip", has_text=title).count() == 1
    finally:
        with urllib.request.urlopen(f"{servers['api']}/api/library?limit=50") as r:
            items = json.load(r)["items"]
        for it in items:
            if it["title"] == title:
                urllib.request.urlopen(urllib.request.Request(f"{servers['api']}/api/library/{it['id']}", method="DELETE"))
