"""
Professional, fully bilingual (ES/EN) PDF report.

Two entry points:

* ``export_report_pdf(comparison_result, filepath=None, lang="es")``  — lap comparison
  (the original API, signature unchanged).
* ``export_session_report_pdf(session_result, stint_result=None, comparison_result=None,
  metadata=None, filepath=None, lang="es")`` — whole-session report built from the JSON
  the frontend already holds (session + stint, optionally a lap comparison).

Design goals: printable (white page, graphite text, one blue accent), a one-page executive
summary, corners always in corner order, tabular right-aligned numbers, an explicit data
quality / limitations section, and page numbers + version in the footer. Every user-visible
string is an i18n key (``pdf_*`` in ``src/locales/extra/pdf.<lang>.json``); texts that the
analysis modules generate are regenerated in the report language from the numeric data, so
the document never mixes languages. Missing modules are skipped or explained in one line;
``None`` / ``nan`` are never printed.
"""

from __future__ import annotations

import io
import logging
import math
import os
import re
import statistics
from datetime import date, datetime
from typing import Any, Optional
from xml.sax.saxutils import escape as _xml_escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

from src.i18n import LanguageContext, get_language, _ as t
from src.io import pdf_charts as charts
from src.io.pdf_charts import Chart, fmt_laptime, num_str

logger = logging.getLogger(__name__)

REPORT_VERSION = "1.2.0"
PRODUCT_NAME = "Motorsport Analytics Pipeline"

# ── Palette (aligned with the app's pit-wall identity, darkened for paper) ────
C_INK = colors.HexColor(charts.INK)
C_INK2 = colors.HexColor(charts.INK_2)
C_INK3 = colors.HexColor(charts.INK_3)
C_ACCENT = colors.HexColor(charts.ACCENT)
C_BAD = colors.HexColor(charts.BAD)
C_OK = colors.HexColor(charts.OK)
C_WARN = colors.HexColor(charts.WARN)
C_LINE = colors.HexColor("#D5DBE3")
C_BAND = colors.HexColor("#F2F5F9")
C_ZEBRA = colors.HexColor("#F7F9FB")

PAGE_W, PAGE_H = A4
MARGIN_X = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_X          # 17.4 cm
CONTENT_CM = CONTENT_W / cm

# ── Fonts (DejaVu ships with matplotlib: covers Δ β α σ ° in every deployment) ─
_FONTS_READY = False
F_REG, F_BOLD, F_ITAL = "RP-Sans", "RP-Sans-Bold", "RP-Sans-Italic"


def _ensure_fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    ttf_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pdfmetrics.registerFont(TTFont(F_REG, os.path.join(ttf_dir, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(F_BOLD, os.path.join(ttf_dir, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(F_ITAL, os.path.join(ttf_dir, "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("RP-Sans-BoldItalic", os.path.join(ttf_dir, "DejaVuSans-BoldOblique.ttf")))
    pdfmetrics.registerFontFamily(F_REG, normal=F_REG, bold=F_BOLD, italic=F_ITAL,
                                  boldItalic="RP-Sans-BoldItalic")
    _FONTS_READY = True


# ── Small helpers ─────────────────────────────────────────────────────────────

def _fin(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def esc(v: Any) -> str:
    return _xml_escape("" if v is None else str(v))


def N(v: Any, decimals: int = 1, signed: bool = False, unit: str = "") -> str:
    """Locale-aware number; an en dash-like placeholder for missing / non-finite values."""
    if not _fin(v):
        return "—"
    r = round(float(v), decimals)
    s = num_str(0.0 if r == 0 else r, decimals, signed and r != 0)
    return f"{s}{unit}"


def _colored(text: str, color: str) -> str:
    return f'<font color="{color}">{text}</font>'


def _loss_markup(v: Any, decimals: int = 3, thr: float = 0.02, unit: str = "") -> str:
    """Signed loss/gain with semantic colour (+ loses, - gains)."""
    s = N(v, decimals, True, unit)
    if not _fin(v):
        return s
    if v > thr:
        return _colored(s, charts.BAD)
    if v < -thr:
        return _colored(s, charts.OK)
    return s


def _get(d: Any, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


def _avail(d: Any) -> bool:
    return isinstance(d, dict) and bool(d.get("available"))


def _clean_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s)).strip() if s is not None else ""


def _rec_text(v: Any) -> str:
    return _loc_numbers(_clean_text(v))


def _loc_numbers(s: str) -> str:
    """Decimal comma for numbers inside text produced by the analysis modules (Spanish only)."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", s) if charts.decimal_comma() else s


def _join(parts, sep=" · ") -> str:
    return sep.join(p for p in parts if p)


# ── Metadata (circuit, car, driver, date) ─────────────────────────────────────

_ACRONYM = re.compile(r"^(gt\d?|gte|gtd|gtp|lmp\d?|tcr|dtm|f\d|fia|wrc|ai|ac|bmw|amg|mx\d?|rs\d?|ssc)$", re.I)
_FILE_EXT = re.compile(r"\.(csv|ibt|ld|ldx|xlsx?|txt|json|zip)$", re.I)
_GENERIC_LAP = re.compile(r"^\s*(vuelta|lap|v|l)\s*\d+\s*$", re.I)


def prettify_name(raw: Any) -> str:
    """'ks_porsche_cayman_gt4_clubsport' -> 'Porsche Cayman GT4 Clubsport', 'fn_imola' -> 'Imola'."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = re.sub(r"^(ks|fn|acc|rf2|ams2|iracing)[_\-]", "", s, flags=re.I)
    if "_" not in s and " " in s and any(c.isupper() for c in s) and any(c.islower() for c in s):
        return s    # already a display name ("BMW M2 Racing (G87)", "Oran Park Raceway (Grand Prix)")
    if "_" not in s and " " in s:
        tokens = s.split()
    else:
        tokens = [x for x in re.split(r"[_\-\s]+", s) if x]
    out = []
    for tok in tokens:
        if _ACRONYM.match(tok) or (re.fullmatch(r"[a-z]{1,3}\d+", tok, re.I) and len(tok) <= 4):
            out.append(tok.upper())
        elif tok.isupper() and len(tok) > 1:
            out.append(tok)
        else:
            out.append(tok[:1].upper() + tok[1:].lower())
    return " ".join(out)


from src.io.header_meta import parse_log_date  # noqa: E402,F401  (re-exported: public helper)


def read_session_header(path: str, filename: Optional[str] = None) -> dict:
    """
    Read venue / vehicle / driver / date / session type from the header of a CSV (MoTeC-style),
    an iRacing .ibt (SessionInfo YAML) or a MoTeC .ld. Never raises: unknown or unreadable
    files simply yield fewer fields.
    """
    from src.io.header_meta import read_header
    return read_header(path, filename)


def _slug(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s


def build_report_filename(meta: Optional[dict] = None) -> str:
    """motorsport_<circuit>_<car>_<date>.pdf  (missing parts are dropped; date falls back to today)."""
    meta = meta or {}
    venue = _slug(prettify_name(meta.get("venue")))
    car = _slug(prettify_name(meta.get("vehicle")))
    d = str(meta.get("date_iso") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        parsed = parse_log_date(meta.get("log_date"), meta.get("log_time"))
        d = parsed.isoformat() if parsed else date.today().isoformat()
    return "_".join(p for p in ("motorsport", venue, car, d) if p) + ".pdf"


def _resolve_meta(session: Optional[dict], stint: Optional[dict], comp: Optional[dict],
                  extra: Optional[dict]) -> dict:
    merged: dict = {}
    for src in (_get(comp, "metadata"), _get(stint, "metadata"), _get(session, "metadata"), extra):
        if isinstance(src, dict):
            for k, v in src.items():
                if v not in (None, ""):
                    merged[k] = v
    venue = prettify_name(merged.get("venue"))
    for _src in (comp, stint, session):  # recognised circuit (length confirmed) -> its proper name
        _circ = _get(_src, "circuit")
        if isinstance(_circ, dict) and _circ.get("matched") and _circ.get("name"):
            venue = str(_circ["name"])
            break
    vehicle_raw = merged.get("vehicle")
    if not vehicle_raw:
        for k in ("vehicle_a", "vehicle_fast"):
            cand = merged.get(k)
            if cand and not _FILE_EXT.search(str(cand)) and str(cand) != "?":
                vehicle_raw = cand
                break
    vehicle = prettify_name(vehicle_raw) if vehicle_raw and not _FILE_EXT.search(str(vehicle_raw)) else ""
    driver = merged.get("driver") or ""
    if not driver:
        cand = merged.get("driver_a")
        if cand and not _GENERIC_LAP.match(str(cand)) and str(cand) != "?":
            driver = cand
    file_name = merged.get("file") or merged.get("session_file") or ""
    d = None
    if merged.get("date_iso"):
        try:
            d = date.fromisoformat(str(merged["date_iso"]))
        except ValueError:
            d = None
    if d is None:
        d = parse_log_date(merged.get("log_date"), merged.get("log_time"))
    return {
        "venue": venue, "vehicle": vehicle, "driver": str(driver).strip(),
        "date": d, "session_type": str(merged.get("session_type") or "").strip(),
        "file": str(file_name),
        "distance_synthetic": bool(merged.get("distance_synthetic")),
        "raw": merged,
    }


_MONTH_KEYS = ("pdf_month_1", "pdf_month_2", "pdf_month_3", "pdf_month_4", "pdf_month_5", "pdf_month_6",
               "pdf_month_7", "pdf_month_8", "pdf_month_9", "pdf_month_10", "pdf_month_11", "pdf_month_12")


def _fmt_date(d: Optional[date]) -> str:
    if not d:
        return ""
    return f"{d.day} {t(_MONTH_KEYS[d.month - 1])} {d.year}"


_SESSION_TYPES = {
    "PRACTICE": "pdf_sess_practice", "HOTLAP": "pdf_sess_hotlap", "QUALIFY": "pdf_sess_qualify",
    "QUALIFYING": "pdf_sess_qualify", "RACE": "pdf_sess_race", "TIME ATTACK": "pdf_sess_hotlap",
}


def _session_type_label(raw: str) -> str:
    key = _SESSION_TYPES.get(raw.strip().upper())
    return t(key) if key else prettify_name(raw)


# ── Styles ────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    _ensure_fonts()
    base = dict(fontName=F_REG, textColor=C_INK, fontSize=8.6, leading=12.2)
    S = {}
    S["body"] = ParagraphStyle("rp_body", **base)
    S["small"] = ParagraphStyle("rp_small", **{**base, "fontSize": 7.6, "leading": 10.4, "textColor": C_INK2})
    S["caption"] = ParagraphStyle("rp_caption", **{**base, "fontSize": 7.4, "leading": 10.2,
                                                   "textColor": C_INK2, "spaceBefore": 3, "spaceAfter": 6})
    S["kicker"] = ParagraphStyle("rp_kicker", **{**base, "fontName": F_BOLD, "fontSize": 8,
                                                 "textColor": C_ACCENT, "leading": 10, "spaceAfter": 3})
    S["title"] = ParagraphStyle("rp_title", **{**base, "fontName": F_BOLD, "fontSize": 26, "leading": 30})
    S["subtitle"] = ParagraphStyle("rp_subtitle", **{**base, "fontSize": 11.5, "leading": 15, "textColor": C_INK2})
    S["h1"] = ParagraphStyle("rp_h1", **{**base, "fontName": F_BOLD, "fontSize": 13.5, "leading": 17,
                                         "spaceBefore": 14, "spaceAfter": 5, "keepWithNext": 1})
    S["h2"] = ParagraphStyle("rp_h2", **{**base, "fontName": F_BOLD, "fontSize": 9.8, "leading": 13,
                                         "spaceBefore": 9, "spaceAfter": 3, "keepWithNext": 1})
    S["th"] = ParagraphStyle("rp_th", **{**base, "fontName": F_BOLD, "fontSize": 7.4, "leading": 9.4,
                                         "textColor": C_INK})
    S["th_r"] = ParagraphStyle("rp_th_r", parent=S["th"], alignment=TA_RIGHT)
    S["td"] = ParagraphStyle("rp_td", **{**base, "fontSize": 7.8, "leading": 10})
    S["td_r"] = ParagraphStyle("rp_td_r", parent=S["td"], alignment=TA_RIGHT)
    S["td_c"] = ParagraphStyle("rp_td_c", parent=S["td"], alignment=TA_CENTER)
    S["td_b"] = ParagraphStyle("rp_td_b", parent=S["td"], fontName=F_BOLD)
    S["td_s"] = ParagraphStyle("rp_td_s", **{**base, "fontSize": 7, "leading": 9, "textColor": C_INK2})
    S["tile_label"] = ParagraphStyle("rp_tile_l", **{**base, "fontSize": 7.2, "leading": 9, "textColor": C_INK2,
                                                     "fontName": F_BOLD})
    S["tile_value"] = ParagraphStyle("rp_tile_v", **{**base, "fontName": F_BOLD, "fontSize": 17, "leading": 21})
    S["tile_sub"] = ParagraphStyle("rp_tile_s", **{**base, "fontSize": 7.4, "leading": 9.6, "textColor": C_INK2})
    S["item"] = ParagraphStyle("rp_item", **{**base, "fontSize": 8.8, "leading": 12.4})
    S["idx"] = ParagraphStyle("rp_idx", **{**base, "fontName": F_BOLD, "fontSize": 11, "leading": 13,
                                           "textColor": C_ACCENT, "alignment": TA_CENTER})
    S["tag"] = ParagraphStyle("rp_tag", **{**base, "fontName": F_BOLD, "fontSize": 6.8, "leading": 9})
    return S


def _table_style(num_cols=(), header: bool = True, zebra: bool = True, pad: float = 3.2) -> TableStyle:
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, C_LINE),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), C_BAND),
            ("LINEABOVE", (0, 0), (-1, 0), 0.9, C_INK),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_INK),
            ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ]
    if zebra:
        cmds.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, C_ZEBRA]))
    return TableStyle(cmds)


def make_table(S: dict, rows: list, widths_cm: list, num_cols=(), header: bool = True,
               zebra: bool = True, pad: float = 3.2, repeat: bool = True,
               extra_style: Optional[list] = None) -> Table:
    """
    rows: list of lists of str (inline markup allowed) or Flowables. Strings are wrapped in
    Paragraphs so long text wraps instead of being truncated; numeric columns are right-aligned.
    """
    num_cols = set(num_cols)
    out = []
    for ri, row in enumerate(rows):
        r = []
        for ci, cell in enumerate(row):
            if isinstance(cell, str) or cell is None or _fin(cell):
                text = "" if cell is None else str(cell)
                if header and ri == 0:
                    st = S["th_r"] if ci in num_cols else S["th"]
                else:
                    st = S["td_r"] if ci in num_cols else S["td"]
                r.append(Paragraph(text, st))
            else:
                r.append(cell)
        out.append(r)
    total = sum(widths_cm)
    scale = CONTENT_CM / total if total > CONTENT_CM + 0.01 else 1.0
    tbl = Table(out, colWidths=[w * scale * cm for w in widths_cm],
                repeatRows=1 if (header and repeat) else 0, hAlign="LEFT")
    st = _table_style(num_cols, header, zebra, pad)
    if extra_style:
        for cmd in extra_style:
            st.add(*cmd)
    tbl.setStyle(st)
    return tbl


def _img(chart: Optional[Chart], max_w_cm: float = CONTENT_CM) -> Optional[Image]:
    if not chart:
        return None
    w = chart.width_px / charts.DPI * 2.54
    h = chart.height_px / charts.DPI * 2.54
    if w > max_w_cm:
        h *= max_w_cm / w
        w = max_w_cm
    return Image(io.BytesIO(chart.png), width=w * cm, height=h * cm)


# ── Report context ────────────────────────────────────────────────────────────

class Ctx:
    def __init__(self, session, stint, comp, extra_meta):
        self.session = session if isinstance(session, dict) else None
        self.stint = stint if isinstance(stint, dict) else None
        self.comp = comp if isinstance(comp, dict) else None
        self.meta = _resolve_meta(self.session, self.stint, self.comp, extra_meta)
        self.S = _styles()
        self.notes: list[tuple[str, str]] = []     # (level 'warn'|'info', text)
        cm_ = _get(self.comp, "metadata", default={}) or {}
        self.la = self._lap_label(cm_.get("label_a"), "pdf_lap_a")
        self.lb = self._lap_label(cm_.get("label_b"), "pdf_lap_b")
        self.kind = "session" if self.session or self.stint else "comparison"
        # Comparison-only reports are kept short (<= ~8 pages): charts smaller, no repeated tables
        self.compact = self.kind == "comparison"

    @staticmethod
    def _lap_label(raw, fallback_key: str) -> str:
        """Generic 'V11' / 'L11' / 'Vuelta 11' labels are re-rendered in the report language."""
        txt = _clean_text(raw)
        m = re.fullmatch(r"(?:vuelta|lap|v|l)\s*(\d+)", txt, re.I)
        if m:
            return t("pdf_lap_short", n=m.group(1))
        return txt or t(fallback_key)

    def note(self, level: str, text: str) -> None:
        if text and all(text != n[1] for n in self.notes):
            self.notes.append((level, text))


# ── Header / cover block ──────────────────────────────────────────────────────

def _title_for(ctx: Ctx) -> str:
    return t("pdf_title_session") if ctx.kind == "session" else t("pdf_title_compare")


def _header_block(ctx: Ctx) -> list:
    S, m = ctx.S, ctx.meta
    el: list = [Paragraph(esc(_title_for(ctx)).upper(), S["kicker"])]
    headline = m["venue"] or _clean_text(m["file"]) or _title_for(ctx)
    el.append(Paragraph(esc(headline), S["title"]))
    sub = _join([m["vehicle"], m["driver"]])
    if sub:
        el.append(Paragraph(esc(sub), S["subtitle"]))
    el.append(Spacer(1, 7))

    fields = []
    if m["venue"]:
        fields.append((t("pdf_f_circuit"), m["venue"]))
    if m["vehicle"]:
        fields.append((t("pdf_f_car"), m["vehicle"]))
    if m["driver"]:
        fields.append((t("pdf_f_driver"), m["driver"]))
    if m["date"]:
        fields.append((t("pdf_f_date"), _fmt_date(m["date"])))
    if m["session_type"]:
        fields.append((t("pdf_f_session"), _session_type_label(m["session_type"])))
    if m["file"]:
        fields.append((t("pdf_f_file"), m["file"]))
    fields.append((t("pdf_f_generated"), _fmt_date(date.today())))
    if ctx.comp and not ctx.session:
        fields.append((t("pdf_f_laps"), f"{ctx.la} / {ctx.lb}"))

    file_field = next((f for f in fields if f[0] == t("pdf_f_file")), None)
    main_fields = [f for f in fields if f is not file_field]
    per_row = 3
    w = CONTENT_W / per_row

    def cell(f):
        return [Paragraph(esc(f[0]).upper(), S["tile_label"]), Paragraph(esc(f[1]), S["td_b"])]

    rows, spans = [], []
    for i in range(0, len(main_fields), per_row):
        chunk = [cell(f) for f in main_fields[i:i + per_row]]
        chunk += [""] * (per_row - len(chunk))
        rows.append(chunk)
    if file_field:
        rows.append([[Paragraph(esc(file_field[0]).upper(), S["tile_label"]),
                      Paragraph(esc(file_field[1]), S["td_s"])], "", ""])
        spans.append(("SPAN", (0, len(rows) - 1), (-1, len(rows) - 1)))
    if rows:
        tbl = Table(rows, colWidths=[w] * per_row)
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEABOVE", (0, 0), (-1, 0), 1.6, C_ACCENT),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, C_LINE),
        ] + spans))
        el.append(tbl)
    el.append(Spacer(1, 8))
    return el


# ── Session metrics ───────────────────────────────────────────────────────────

def _session_laps(ctx: Ctx) -> list[dict]:
    """Normalised lap list: n, time, kind in {clean, best, pit, outlier}, extras."""
    laps: list[dict] = []
    stint_laps = _get(ctx.stint, "laps", default=None)
    if isinstance(stint_laps, list) and stint_laps:
        for L in stint_laps:
            tm = L.get("lap_time_s")
            laps.append({
                "n": L.get("lap_number"), "time": tm if _fin(tm) else None,
                "pit": bool(L.get("is_pit_lap")), "outlier": bool(L.get("is_outlier")),
                "mean_speed": L.get("mean_speed_kmh"), "max_speed": L.get("max_speed_kmh"),
                "fuel": L.get("fuel_burned") if _fin(L.get("fuel_burned")) and L.get("fuel_burned") > 0 else None,
            })
    else:
        for L in _get(ctx.session, "laps", default=[]) or []:
            tm = L.get("lap_time")
            laps.append({
                "n": L.get("lap_number"), "time": tm if _fin(tm) else None,
                "pit": bool(L.get("is_pit_lap")), "outlier": False,
                "mean_speed": None, "max_speed": L.get("max_speed"), "fuel": None,
            })
    laps = [L for L in laps if L["n"] is not None]
    clean = [L for L in laps if L["time"] and not L["pit"] and not L["outlier"]]
    best_n = min(clean, key=lambda L: L["time"])["n"] if clean else None
    for L in laps:
        if not L["time"]:
            L["kind"] = "pit" if L["pit"] else "outlier"
        elif L["pit"]:
            L["kind"] = "pit"
        elif L["outlier"]:
            L["kind"] = "outlier"
        else:
            L["kind"] = "best" if L["n"] == best_n else "clean"
    return laps


def _pace_stats(laps: list[dict]) -> dict:
    clean = [L["time"] for L in laps if L["kind"] in ("clean", "best")]
    out: dict = {"n_clean": len(clean), "n_total": len(laps)}
    if not clean:
        return out
    best = min(clean)
    out["best"] = best
    out["best_lap"] = next(L["n"] for L in laps if L["kind"] == "best")
    out["median"] = statistics.median(clean)
    out["mean"] = statistics.fmean(clean)
    if len(clean) >= 3:
        out["sigma"] = statistics.stdev(clean)
        # relative to the best lap: <0.5 % tight, <1 % moderate, else wide (indicative only)
        rel = out["sigma"] / best
        out["consistency"] = "pdf_cons_high" if rel < 0.005 else "pdf_cons_mid" if rel < 0.01 else "pdf_cons_low"
    return out


def _corners_session(ctx: Ctx) -> list[dict]:
    cs = _get(ctx.stint, "curvas_sesion", default={}) or {}
    if not _avail(cs):
        return []
    out = []
    for c in cs.get("corners", []) or []:
        out.append({
            "n": c.get("corner_number"), "name": c.get("corner_name"), "loss": c.get("time_loss_seconds"),
            "sigma": c.get("std_loss_seconds"),
            "brake": c.get("braking_delta_meters") if c.get("braking_available", True) else None,
            "apex": c.get("apex_speed_delta_kmh") if c.get("apex_available", True) else None,
            "throttle": c.get("throttle_delta_meters") if c.get("throttle_available", True) else None,
            "kind": c.get("kind"),
        })
    return sorted([c for c in out if c["n"] is not None], key=lambda c: c["n"])


def _corners_compare(ctx: Ctx) -> list[dict]:
    out = []
    for c in _get(ctx.comp, "corners", default=[]) or []:
        out.append({
            "n": c.get("corner_number"), "name": c.get("corner_name"), "loss": c.get("time_loss_seconds"), "sigma": None,
            "brake": c.get("braking_delta_meters") if c.get("braking_delta_available", True) else None,
            "apex": c.get("apex_speed_delta_kmh") if c.get("apex_delta_available", True) else None,
            "throttle": c.get("throttle_delta_meters") if c.get("throttle_delta_available", True) else None,
            "kind": c.get("kind"),
        })
    return sorted([c for c in out if c["n"] is not None], key=lambda c: c["n"])


def _clabel(c: dict, markup: bool = True) -> str:
    """'4 · Tamburello' when the circuit was recognised, otherwise just the number."""
    name = str(c.get("name") or "").strip()
    label = f"{c['n']} · {name}" if name else str(c["n"])
    return esc(label) if markup else label


def _name_of(n, corners: list) -> str:
    """Corner label for a bare corner number, looked up in a corner list."""
    for c in corners or []:
        if c.get("n") == n:
            return _clabel(c, markup=False)
    return str(n)


def _dominant_phase(c: dict) -> Optional[str]:
    """Same weighting as the setup advisor, but language independent."""
    if not _fin(c.get("loss")) or abs(c["loss"]) < 0.005:
        return None
    scores = {
        "pdf_phase_braking": abs(c["brake"]) * 0.015 if _fin(c.get("brake")) else 0.0,
        "pdf_phase_apex": abs(c["apex"]) * 0.012 if _fin(c.get("apex")) else 0.0,
        "pdf_phase_exit": abs(c["throttle"]) * 0.010 if _fin(c.get("throttle")) else 0.0,
    }
    key = max(scores, key=scores.get)
    return key if scores[key] > 0 else None


_PHASE_FOCUS = {
    "pdf_phase_braking": "pdf_focus_braking",
    "pdf_phase_apex": "pdf_focus_apex",
    "pdf_phase_exit": "pdf_focus_exit",
}


_FLAT_KINDS = ("flat_out", "kink")   # unified corner map: nothing to brake, no apex, no throttle phase
_KIND_MARK = {"flat_out": "pdf_kind_flat_out", "kink": "pdf_kind_kink"}
_KIND_READING = {"flat_out": "pdf_read_flat_out", "kink": "pdf_read_kink"}


def _corner_reading(c: dict, with_sigma: bool = True) -> str:
    if c.get("kind") in _FLAT_KINDS:
        return t(_KIND_READING[c["kind"]])
    parts = []
    if _fin(c.get("brake")) and abs(c["brake"]) >= 2:
        parts.append(t("pdf_read_brake_later" if c["brake"] > 0 else "pdf_read_brake_earlier",
                       m=N(abs(c["brake"]), 0)))
    if _fin(c.get("apex")) and abs(c["apex"]) >= 1:
        parts.append(t("pdf_read_apex_faster" if c["apex"] > 0 else "pdf_read_apex_slower",
                       v=N(abs(c["apex"]), 1)))
    if _fin(c.get("throttle")) and abs(c["throttle"]) >= 3:
        parts.append(t("pdf_read_throttle_later" if c["throttle"] > 0 else "pdf_read_throttle_earlier",
                       m=N(abs(c["throttle"]), 0)))
    if with_sigma and _fin(c.get("sigma")) and c["sigma"] >= 0.15:
        parts.append(t("pdf_read_inconsistent", s=N(c["sigma"], 2)))
    return "; ".join(parts) if parts else t("pdf_read_none")


def _setup_recs(ctx: Ctx) -> dict:
    """Setup recommendations regenerated in the report language when possible."""
    try:
        if ctx.stint and _avail(ctx.stint.get("curvas_sesion")):
            from src.analytics.setup_advisor import analizar_setup_sesion
            res = analizar_setup_sesion(ctx.stint["curvas_sesion"], ctx.stint.get("degradacion") or {},
                                        ctx.stint.get("telemetria_sesion") or {}, lang=get_language())
            if _avail(res):
                return res
        elif ctx.comp:
            from src.analytics.setup_advisor import analizar_setup
            res = analizar_setup(ctx.comp, lang=get_language())
            if _avail(res):
                return res
    except Exception as exc:
        logger.warning("setup regeneration failed (%s); using stored recommendations", exc)
    stored = _get(ctx.stint, "setup_sesion") or _get(ctx.comp, "setup_advisor") or {}
    return stored if isinstance(stored, dict) else {}


_PRIO_RANK = {"alta": 0, "media": 1, "baja": 2}


def _sorted_recs(setup: dict) -> list[dict]:
    recs = [r for r in (setup.get("recommendations") or []) if isinstance(r, dict)]
    return sorted(recs, key=lambda r: (_PRIO_RANK.get(r.get("priority"), 3), -(r.get("gain_hi") or 0)))


# ── Executive summary ─────────────────────────────────────────────────────────

def _tile(S: dict, label: str, value: str, sub: str = "") -> list:
    items = [Paragraph(esc(label).upper(), S["tile_label"]), Spacer(1, 2),
             Paragraph(value, S["tile_value"])]
    if sub:
        items.append(Paragraph(sub, S["tile_sub"]))
    return items


def _tiles_row(ctx: Ctx, tiles: list[list]) -> Table:
    n = len(tiles)
    gap = 5
    w = (CONTENT_W - gap * (n - 1)) / n
    cols, row = [], []
    for i, tile in enumerate(tiles):
        row.append(tile)
        cols.append(w)
        if i < n - 1:
            row.append("")
            cols.append(gap)
    tbl = Table([row], colWidths=cols)
    cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    for i in range(0, len(row), 2):
        cmds += [("BACKGROUND", (i, 0), (i, 0), C_BAND), ("LINEABOVE", (i, 0), (i, 0), 1.4, C_ACCENT)]
    for i in range(1, len(row), 2):
        cmds += [("LEFTPADDING", (i, 0), (i, 0), 0), ("RIGHTPADDING", (i, 0), (i, 0), 0)]
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _numbered_list(ctx: Ctx, items: list[str]) -> Table:
    S = ctx.S
    rows = [[Paragraph(str(i + 1), S["idx"]), Paragraph(text, S["item"])] for i, text in enumerate(items)]
    tbl = Table(rows, colWidths=[0.9 * cm, CONTENT_W - 0.9 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, C_LINE),
    ]))
    return tbl


def _top_loss_corners(corners: list[dict], n: int = 3) -> list[dict]:
    return sorted([c for c in corners if _fin(c.get("loss")) and c["loss"] > 0.02],
                  key=lambda c: -c["loss"])[:n]


def _conclusions_session(ctx: Ctx, laps, pace, corners) -> list[str]:
    out: list[str] = []
    if _fin(pace.get("best")):
        txt = t("pdf_c_best_pace", time=fmt_laptime(pace["best"]), lap=pace["best_lap"])
        if _fin(pace.get("median")) and pace["n_clean"] >= 3:
            txt += " " + t("pdf_c_best_pace2", gap=N(pace["median"] - pace["best"], 2),
                           sigma=N(pace.get("sigma"), 2), n=pace["n_clean"])
        out.append(txt)
    top = _top_loss_corners(corners, 3)
    if top:
        parts = []
        for c in top:
            ph = _dominant_phase(c)
            parts.append(t("pdf_c_corner_item", n=_clabel(c), loss=N(c["loss"], 3, True),
                           phase=t(ph).lower() if ph else t("pdf_phase_none")))
        out.append(t("pdf_c_worst_corners", items="; ".join(parts)))
    elif corners:
        out.append(t("pdf_c_no_corner_loss"))
    deg = _get(ctx.stint, "degradacion", default={}) or {}
    if _avail(deg):
        if deg.get("low_confidence"):
            out.append(t("pdf_c_deg_lowconf", n=deg.get("n_laps_used", "?")))
        else:
            slope = deg.get("degradation_s_per_lap", deg.get("tasa_s_per_lap"))
            ci = deg.get("slope_ci")
            if _fin(slope) and isinstance(ci, list) and len(ci) == 2 and ci[0] is not None and ci[1] is not None \
                    and ci[0] <= 0 <= ci[1]:
                out.append(t("pdf_c_deg_none", ci=f"{N(ci[0], 3, True)} / {N(ci[1], 3, True)}"))
            elif _fin(slope):
                out.append(t("pdf_c_deg_rate", rate=N(slope, 3, True)))
    sig_corners = [c for c in corners if _fin(c.get("sigma"))]
    if sig_corners:
        worst = max(sig_corners, key=lambda c: c["sigma"])
        if worst["sigma"] >= 0.15:
            out.append(t("pdf_c_inconsistent_corner", n=_clabel(worst), s=N(worst["sigma"], 2)))
    fuel = _get(ctx.stint, "combustible", default={}) or {}
    if _avail(fuel) and _fin(fuel.get("consumo_medio_l")):
        out.append(t("pdf_c_fuel", rate=N(fuel["consumo_medio_l"], 2),
                     laps=_range_txt(fuel.get("vueltas_restantes_min"), fuel.get("vueltas_restantes_max"))))
    return out


def _range_txt(lo, hi) -> str:
    if _fin(lo) and _fin(hi):
        return N(lo, 0) if round(lo) == round(hi) else f"{N(lo, 0)}–{N(hi, 0)}"
    return N(lo if _fin(lo) else hi, 0)


def _conclusions_compare(ctx: Ctx, corners) -> list[str]:
    out: list[str] = []
    summ = _get(ctx.comp, "summary", default={}) or {}
    d = summ.get("total_time_delta")
    if _fin(d):
        if abs(d) < 0.0005:
            out.append(t("pdf_c_cmp_identical", a=esc(ctx.la), b=esc(ctx.lb)))
        else:
            txt = t("pdf_c_cmp_slower" if d > 0 else "pdf_c_cmp_faster", b=esc(ctx.lb), a=esc(ctx.la),
                    d=N(abs(d), 3))
            if _fin(summ.get("corners_time_delta_s")) and _fin(summ.get("outside_corners_delta_s")):
                txt += " " + t("pdf_c_cmp_split", c=N(summ["corners_time_delta_s"], 3, True),
                               o=N(summ["outside_corners_delta_s"], 3, True))
            out.append(txt)
    top = _top_loss_corners(corners, 3)
    if top:
        parts = []
        for c in top:
            ph = _dominant_phase(c)
            parts.append(t("pdf_c_corner_item", n=_clabel(c), loss=N(c["loss"], 3, True),
                           phase=t(ph).lower() if ph else t("pdf_phase_none")))
        out.append(t("pdf_c_worst_corners", items="; ".join(parts)))
    gains = sorted([c for c in corners if _fin(c.get("loss")) and c["loss"] < -0.02], key=lambda c: c["loss"])[:2]
    if gains:
        out.append(t("pdf_c_cmp_gains", items=", ".join(f"{t('pdf_corner_short', n=_clabel(c))} ({N(c['loss'], 3, True)} s)"
                                                       for c in gains), b=esc(ctx.lb)))
    brake = _get(ctx.comp, "brake_analysis", default={}) or {}
    if _avail(brake):
        za, zb = len(brake.get("fade_zones_a") or []), len(brake.get("fade_zones_b") or [])
        if za or zb:
            out.append(t("pdf_c_cmp_fade", a=esc(ctx.la), za=za, b=esc(ctx.lb), zb=zb))
    slip = _get(ctx.comp, "slip_angle", default={}) or {}
    sa = slip.get("summary_a") or {}
    if _avail(slip) and _fin(sa.get("understeer_pct")) and _fin(sa.get("oversteer_pct")):
        out.append(t("pdf_c_cmp_balance", lap=esc(ctx.la), us=N(sa["understeer_pct"], 1), os_=N(sa["oversteer_pct"], 1)))
    return out


def _actions(ctx: Ctx, corners: list[dict]) -> list[str]:
    acts: list[str] = []
    seen: set = set()
    setup = _setup_recs(ctx)
    for r in _sorted_recs(setup):
        if len(acts) >= 3:
            break
        rec = _rec_text(r.get("recommendation"))
        cat = _rec_text(r.get("category"))
        if not rec:
            continue
        gain = _rec_text(r.get("expected_gain"))
        txt = f"<b>{esc(cat)}.</b> {esc(rec)}" if cat else esc(rec)
        if gain and gain != "—":
            txt += " " + _colored(t("pdf_a_gain", gain=esc(gain)), charts.INK_2)
        key = (cat, rec)
        if key in seen:           # e.g. the same fade advice for both laps: list it once
            continue
        seen.add(key)
        acts.append(txt)
    if len(acts) < 3:
        for c in _top_loss_corners(corners, 5):
            if len(acts) >= 3:
                break
            ph = _dominant_phase(c)
            if not ph:
                continue
            acts.append(esc(t("pdf_a_corner", n=_clabel(c, markup=False), focus=t(_PHASE_FOCUS[ph]), loss=N(abs(c["loss"]), 3))))
    if len(acts) < 3 and ctx.session and not ctx.stint:
        acts.append(t("pdf_a_run_stint"))
    return acts[:3]


def _dq_line(ctx: Ctx) -> str:
    """One line from the data-quality object (numbers only -> always in the report language)."""
    for src in (ctx.comp, ctx.stint, ctx.session):
        dq = _get(src, "data_quality")
        if not (_avail(dq) and _fin(dq.get("score"))):
            continue
        ch, mo = dq.get("channel_summary") or {}, dq.get("module_summary") or {}
        lvl = dq.get("level") if dq.get("level") in ("good", "fair", "poor") else None
        txt = t("pdf_q_score", score=N(dq["score"], 0), level=t(f"pdf_dq_{lvl}") if lvl else "—",
                ok=N(ch.get("ok"), 0), warn=N(ch.get("warning"), 0), miss=N(ch.get("missing"), 0),
                mok=N(mo.get("ok"), 0), mdeg=N(mo.get("degraded"), 0), mun=N(mo.get("unavailable"), 0))
        # improvement titles are generated in the request language: only reuse them if it matches
        imp = [i for i in (dq.get("improvements") or []) if isinstance(i, dict) and i.get("title")]
        if imp and dq.get("lang") == get_language():
            txt += " " + t("pdf_q_improve", title=_clean_text(imp[0]["title"]).rstrip("."))
        return txt
    return ""


def _quality_box(ctx: Ctx, limit: int = 3) -> list:
    S = ctx.S
    notes = sorted(ctx.notes, key=lambda n: 0 if n[0] == "warn" else 1)[:limit]
    el = [Paragraph(esc(t("pdf_h_quality")), S["h2"])]
    dq = _dq_line(ctx)
    if dq:
        el.append(Paragraph(esc(dq), S["small"]))
        el.append(Spacer(1, 3))
    if not notes:
        if not dq:
            el.append(Paragraph(esc(t("pdf_q_none")), S["small"]))
        return el
    rows = []
    for level, text in notes:
        tag = t("pdf_tag_warn") if level == "warn" else t("pdf_tag_info")
        col = charts.BAD if level == "warn" else charts.INK_2
        rows.append([Paragraph(_colored(esc(tag).upper(), col), S["tag"]), Paragraph(esc(text), S["small"])])
    if len(ctx.notes) > limit:
        rows.append(["", Paragraph(esc(t("pdf_q_more", n=len(ctx.notes) - limit)), S["small"])])
    tbl = Table(rows, colWidths=[2.1 * cm, CONTENT_W - 2.1 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF7EE")),
        ("LINEBEFORE", (0, 0), (0, -1), 2, C_WARN),
    ]))
    el.append(tbl)
    return el


def _exec_summary(ctx: Ctx, laps, pace, corners_s, corners_c) -> list:
    S = ctx.S
    el: list = [Paragraph(esc(t("pdf_h_exec")), S["h1"])]
    tiles = []
    if ctx.kind == "session":
        if _fin(pace.get("best")):
            tiles.append(_tile(S, t("pdf_k_best_lap"), esc(fmt_laptime(pace["best"])),
                               esc(t("pdf_lap_n", n=pace["best_lap"]))))
        else:
            tiles.append(_tile(S, t("pdf_k_best_lap"), "—", esc(t("pdf_k_no_clean"))))
        if _fin(pace.get("median")):
            tiles.append(_tile(S, t("pdf_k_pace"), esc(fmt_laptime(pace["median"], 2)),
                               esc(t("pdf_k_pace_sub", gap=N(pace["median"] - pace["best"], 2)))
                               if _fin(pace.get("best")) else ""))
        else:
            tiles.append(_tile(S, t("pdf_k_pace"), "—"))
        if _fin(pace.get("sigma")):
            tiles.append(_tile(S, t("pdf_k_consistency"), esc(f"σ {N(pace['sigma'], 2)} s"),
                               esc(t(pace["consistency"]))))
        else:
            tiles.append(_tile(S, t("pdf_k_consistency"), "—", esc(t("pdf_k_need_laps"))))
        tiles.append(_tile(S, t("pdf_k_laps"), esc(f"{pace.get('n_clean', 0)} / {pace.get('n_total', 0)}"),
                           esc(t("pdf_k_laps_sub"))))
        corners = corners_s
        concl = _conclusions_session(ctx, laps, pace, corners_s)
    else:
        summ = _get(ctx.comp, "summary", default={}) or {}
        d = summ.get("total_time_delta")
        in_c, out_c = summ.get("corners_time_delta_s"), summ.get("outside_corners_delta_s")
        if not _fin(in_c) and corners_c and _fin(d):      # older / lighter results: derive from the corner list
            in_c = sum(c["loss"] for c in corners_c if _fin(c.get("loss")))
            out_c = d - in_c
        sub = esc(t("pdf_k_delta_sub", b=ctx.lb, a=ctx.la))
        tiles.append(_tile(S, t("pdf_k_delta_total"), _loss_markup(d, 3, 0.0005, " s"), sub))
        tiles.append(_tile(S, t("pdf_k_in_corners"), _loss_markup(in_c, 3, 0.0005, " s"),
                           esc(t("pdf_k_in_corners_sub"))))
        tiles.append(_tile(S, t("pdf_k_outside"), _loss_markup(out_c, 3, 0.0005, " s"),
                           esc(t("pdf_k_outside_sub"))))
        wc = summ.get("worst_corner")
        wl = summ.get("worst_corner_loss")
        top1 = _top_loss_corners(corners_c, 1)
        if top1:                                          # same list the tables use -> numbers always agree
            wc, wl = top1[0]["n"], top1[0]["loss"]
        tiles.append(_tile(S, t("pdf_k_worst_corner"),
                           esc(t("pdf_corner_short", n=_name_of(wc, corners_c))) if wc not in (None, 0, "") else "—",
                           _loss_markup(wl, 3, 0.0005, " s") if wc not in (None, 0, "") else ""))
        corners = corners_c
        concl = _conclusions_compare(ctx, corners_c)
    el.append(_tiles_row(ctx, tiles))
    el.append(Spacer(1, 4))

    el.append(Paragraph(esc(t("pdf_h_conclusions")), S["h2"]))
    concl = concl[:3]
    el.append(_numbered_list(ctx, concl) if concl else Paragraph(esc(t("pdf_no_conclusions")), S["small"]))

    el.append(Paragraph(esc(t("pdf_h_actions")), S["h2"]))
    acts = _actions(ctx, corners)
    el.append(_numbered_list(ctx, acts) if acts else Paragraph(esc(t("pdf_no_actions")), S["small"]))
    el.append(Spacer(1, 4))
    return el


# ── Pace section (session) ────────────────────────────────────────────────────

def _section_pace(ctx: Ctx, laps, pace) -> list:
    if not laps:
        return []
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_pace")), S["h1"])]
    deg = _get(ctx.stint, "degradacion") if ctx.stint else None
    mc = _get(ctx.stint, "montecarlo") if ctx.stint else None
    ch = charts.chart_lap_times([{"n": L["n"], "time": L["time"], "kind": L["kind"]} for L in laps],
                                trend=deg if _avail(deg) else None, montecarlo=mc if _avail(mc) else None)
    if ch:
        el.append(_img(ch))
        el.append(Paragraph(esc(t("pdf_cap_lap_times")), S["caption"]))
    # lap table
    best = pace.get("best")
    head = [t("pdf_th_lap"), t("pdf_th_time"), t("pdf_th_gap"), t("pdf_th_mean_speed"),
            t("pdf_th_max_speed"), t("pdf_th_fuel"), t("pdf_th_status")]
    rows = [head]
    style = []
    kind_lbl = {"best": t("pdf_st_best"), "pit": t("pdf_st_pit"), "outlier": t("pdf_st_outlier"), "clean": ""}
    for i, L in enumerate(laps, start=1):
        gap = (L["time"] - best) if (_fin(best) and L["time"] and L["kind"] in ("clean", "best")) else None
        status = kind_lbl.get(L["kind"], "")
        if L["kind"] == "best":
            status = _colored(f"<b>{esc(status)}</b>", charts.OK)
        rows.append([
            esc(L["n"]), fmt_laptime(L["time"]) if L["time"] else "—",
            N(gap, 3, True) if gap is not None else "—",
            N(L.get("mean_speed"), 1), N(L.get("max_speed"), 1),
            N(L.get("fuel"), 2), status,
        ])
        if L["kind"] in ("pit", "outlier"):
            style.append(("TEXTCOLOR", (0, i), (-1, i), C_INK3))
    tbl = make_table(S, rows, [1.4, 2.6, 2.4, 2.8, 2.8, 2.4, 3.0], num_cols=(0, 1, 2, 3, 4, 5), pad=2.4,
                     extra_style=style)
    el.append(KeepTogether([Paragraph(esc(t("pdf_h_lap_table")), S["h2"]), tbl]) if len(rows) <= 14
              else Paragraph(esc(t("pdf_h_lap_table")), S["h2"]))
    if len(rows) > 14:
        el.append(tbl)
    el.append(Paragraph(esc(t("pdf_cap_lap_table", n_total=pace.get("n_total", 0), n_clean=pace.get("n_clean", 0))),
                        S["caption"]))
    return el


# ── Corner section ────────────────────────────────────────────────────────────

def _priority_table(ctx: Ctx, corners: list[dict]) -> list:
    S = ctx.S
    top = _top_loss_corners(corners, 5)
    el = [Paragraph(esc(t("pdf_h_priority")), S["h2"])]
    if not top:
        el.append(Paragraph(esc(t("pdf_no_priority")), S["small"]))
        return el
    rows = [[t("pdf_th_corner"), t("pdf_th_loss"), t("pdf_th_phase"), t("pdf_th_focus")]]
    for c in top:
        ph = _dominant_phase(c)
        rows.append([f"<b>{_clabel(c)}</b>", _loss_markup(c["loss"]), esc(t(ph)) if ph else "—",
                     esc(t(_PHASE_FOCUS[ph])) if ph else "—"])
    named = any(c.get("name") for c in top)
    el.append(make_table(S, rows, [4.2, 2.6, 3.4, 7.2] if named else [2.0, 2.6, 3.4, 9.4], num_cols=(0, 1)))
    return el


def _section_corners(ctx: Ctx, corners: list[dict], kind: str) -> list:
    if not corners:
        return []
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_corners")), S["h1"])]
    if kind == "session":
        ylabel = t("pdf_chart_loss_ref")
        intro = t("pdf_intro_corners_session")
        ref = _get(ctx.stint, "curvas_sesion", default={}) or {}
        if ref.get("reference_lap") is not None:
            intro += " " + t("pdf_intro_corners_ref", ref=ref.get("reference_lap"), n=ref.get("n_laps_compared", "?"))
    else:
        ylabel = t("pdf_chart_loss_cmp", a=ctx.la, b=ctx.lb)
        intro = t("pdf_intro_corners_compare", a=esc(ctx.la), b=esc(ctx.lb))
    el.append(Paragraph(esc(intro), S["caption"]))
    ch = charts.chart_corner_bars([{"n": c["n"], "loss": c["loss"], "sigma": c.get("sigma"),
                                    "flat": c.get("kind") in _FLAT_KINDS} for c in corners],
                                  ylabel, h=4.4 if ctx.compact else 5.6)
    if ch:
        el.append(_img(ch))
        el.append(Paragraph(esc(t("pdf_cap_corner_bars")), S["caption"]))
    if not ctx.compact:   # compact reports already list the top losses (with phase) on page 1 and in the detail table
        el += _priority_table(ctx, corners)

    el.append(Paragraph(esc(t("pdf_h_corner_detail")), S["h2"]))
    head = [t("pdf_th_corner"), t("pdf_th_loss"), t("pdf_th_sigma") if kind == "session" else "",
            t("pdf_th_brake"), t("pdf_th_apex"), t("pdf_th_throttle"), t("pdf_th_phase"), t("pdf_th_reading")]
    use_sigma = kind == "session"
    cols = [0, 1] + ([2] if use_sigma else []) + [3, 4, 5, 6, 7]
    rows = [[head[i] for i in cols]]
    for c in corners:
        ph = _dominant_phase(c)
        full = [
            f"<b>{_clabel(c)}</b>", _loss_markup(c["loss"]),
            N(c.get("sigma"), 2) if use_sigma else "",
            N(c.get("brake"), 0, True) if _fin(c.get("brake")) and abs(c["brake"]) >= 0.5 else "—",
            N(c.get("apex"), 1, True) if _fin(c.get("apex")) and abs(c["apex"]) >= 0.05 else "—",
            N(c.get("throttle"), 0, True) if _fin(c.get("throttle")) and abs(c["throttle"]) >= 0.5 else "—",
            esc(t(ph)) if ph else (esc(t(_KIND_MARK[c["kind"]])) if c.get("kind") in _FLAT_KINDS else "—"),
            esc(_corner_reading(c, with_sigma=use_sigma)),
        ]
        rows.append([full[i] for i in cols])
    widths_full = [1.6, 1.9, 1.4, 1.9, 1.9, 1.9, 2.2, 5.2]
    if any(c.get("name") for c in corners):  # room for "4 · Tamburello"; the reading column absorbs it
        widths_full = [3.6, 1.9, 1.4, 1.8, 1.8, 1.8, 2.1, 3.6]
    widths = [widths_full[i] for i in cols]
    nums = [k for k, i in enumerate(cols) if i in (0, 1, 2, 3, 4, 5)]
    phase_col = cols.index(6)
    el.append(make_table(S, rows, widths, num_cols=nums, pad=2.1 if ctx.compact else 2.6,
                         extra_style=[("LEFTPADDING", (phase_col, 0), (phase_col, -1), 10)]))
    el.append(Paragraph(esc(t("pdf_cap_corner_table_session" if kind == "session" else "pdf_cap_corner_table_compare",
                              a=ctx.la, b=ctx.lb)), S["caption"]))
    return el


# ── Setup & strategy ──────────────────────────────────────────────────────────

_PRIO_TEXT = {"alta": "pdf_prio_high", "media": "pdf_prio_mid", "baja": "pdf_prio_low"}
_PRIO_SHORT = {"alta": "pdf_prio_s_alta", "media": "pdf_prio_s_media", "baja": "pdf_prio_s_baja"}
_PRIO_COL = {"alta": charts.BAD, "media": charts.WARN, "baja": charts.OK}


def _setup_compact_table(ctx: Ctx, recs: list[dict]) -> list:
    """One table for all priorities; identical advice given for both laps is merged into one row."""
    S = ctx.S
    merged: dict = {}
    for r in recs:
        key = (r.get("priority"), _rec_text(r.get("category")), _rec_text(r.get("recommendation")))
        e = merged.setdefault(key, {"problems": [], "details": [], "gain": _rec_text(r.get("expected_gain")) or "—"})
        for fld, bucket in (("problem", "problems"), ("detail", "details")):
            v = _rec_text(r.get(fld))
            if v and v not in e[bucket]:
                e[bucket].append(v)
    rows = [[t("pdf_th_priority"), t("pdf_setup_area"), t("pdf_setup_problem"), t("pdf_setup_rec"), t("pdf_setup_gain")]]
    for (prio, cat, rec), e in merged.items():
        rec_txt = esc(rec)
        if e["details"]:
            rec_txt += "<br/>" + _colored(f'<font size="6.6">{esc(" · ".join(e["details"]))}</font>', charts.INK_2)
        tag = _colored(f"<b>{esc(t(_PRIO_SHORT[prio])).upper()}</b>", _PRIO_COL[prio]) if prio in _PRIO_TEXT else "—"
        rows.append([tag, f"<b>{esc(cat)}</b>", esc(" · ".join(e["problems"])), rec_txt, esc(e["gain"])])
    return [make_table(S, rows, [1.7, 2.5, 4.4, 6.9, 2.3], num_cols=(4,), pad=2.4)]


def _section_setup(ctx: Ctx) -> list:
    setup = _setup_recs(ctx)
    recs = _sorted_recs(setup)
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_setup")), S["h1"])]
    if not recs:
        el.append(Paragraph(esc(t("pdf_setup_none")), S["small"]))
        return el
    gain = setup.get("total_gain_range")
    el.append(Paragraph(esc(t("pdf_setup_summary", n=len(recs), gain=gain or "—")) if gain
                        else esc(t("pdf_setup_summary_nogain", n=len(recs))), S["body"]))
    el.append(Spacer(1, 3))
    if ctx.compact:
        el += _setup_compact_table(ctx, recs)
        el.append(Paragraph(esc(t("pdf_setup_disclaimer")), S["caption"]))
        return el
    for prio in ("alta", "media", "baja"):
        group = [r for r in recs if r.get("priority") == prio]
        if not group:
            continue
        el.append(Paragraph(_colored(esc(t(_PRIO_TEXT[prio])).upper(), _PRIO_COL[prio]), S["h2"]))
        rows = [[t("pdf_setup_area"), t("pdf_setup_problem"), t("pdf_setup_rec"), t("pdf_setup_gain")]]
        for r in group:
            rec = esc(_rec_text(r.get("recommendation")))
            det = _rec_text(r.get("detail"))
            if det:
                rec += "<br/>" + _colored(f'<font size="7">{esc(det)}</font>', charts.INK_2)
            rows.append([f"<b>{esc(_rec_text(r.get('category')))}</b>", esc(_rec_text(r.get("problem"))),
                         rec, esc(_rec_text(r.get("expected_gain")) or "—")])
        el.append(make_table(S, rows, [2.9, 5.0, 7.1, 2.4], num_cols=(3,), pad=3))
    el.append(Paragraph(esc(t("pdf_setup_disclaimer")), S["caption"]))
    return el


def _conf_label(deg: dict) -> str:
    c = deg.get("confidence")
    return {"high": t("pdf_conf_high"), "medium": t("pdf_conf_mid"), "low": t("pdf_conf_low")}.get(c, "—")


_REASON_KEYS = {
    "insufficient_sample": "pdf_reason_insufficient_sample",
    "wide_slope_ci": "pdf_reason_wide_slope_ci",
    "wear_inactive": "pdf_reason_wear_inactive",
    "no_detectable_degradation": "pdf_reason_no_degradation",
}


def _kv_table(S: dict, rows: list[tuple[str, str]], widths=(8.0, 9.4)) -> Table:
    data = [[f"{esc(k)}", v] for k, v in rows]
    return make_table(S, data, list(widths), header=False, pad=2.8, num_cols=())


def _section_strategy(ctx: Ctx) -> list:
    st = ctx.stint
    if not st:
        return []
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_strategy")), S["h1"])]
    shown = False

    # Pace degradation / projection
    deg = st.get("degradacion") or {}
    if _avail(deg):
        shown = True
        el.append(Paragraph(esc(t("pdf_h_deg")), S["h2"]))
        slope = deg.get("degradation_s_per_lap", deg.get("tasa_s_per_lap"))
        ci = deg.get("slope_ci")
        ci_txt = f"{N(ci[0], 3, True)} / {N(ci[1], 3, True)} s" if isinstance(ci, list) and len(ci) == 2 \
            and _fin(ci[0]) and _fin(ci[1]) else "—"
        rows = [
            (t("pdf_kv_deg_rate"), N(slope, 3, True, " s/" + t("pdf_unit_lap"))),
            (t("pdf_kv_ci"), ci_txt),
            (t("pdf_kv_raw_slope"), N(deg.get("raw_slope_s_per_lap"), 3, True, " s/" + t("pdf_unit_lap"))),
            (t("pdf_kv_fuel_effect"), N(deg.get("fuel_effect_s_per_lap"), 3, True, " s/" + t("pdf_unit_lap"))),
            (t("pdf_kv_confidence"), esc(_conf_label(deg))),
            (t("pdf_kv_laps_used"), N(deg.get("n_laps_used"), 0)),
        ]
        el.append(_kv_table(S, rows))
        code = deg.get("reason_code")
        if code in _REASON_KEYS:
            el.append(Paragraph(esc(t(_REASON_KEYS[code])), S["caption"]))
        elif deg.get("low_confidence"):
            el.append(Paragraph(esc(t("pdf_reason_low_conf_generic")), S["caption"]))
        if deg.get("low_confidence"):
            ctx.note("warn", t("pdf_q_deg_lowconf", n=deg.get("n_laps_used", "?"), min=deg.get("min_laps_for_trend", 5)))
        mc = st.get("montecarlo") or {}
        if _avail(mc) and isinstance(mc.get("future_laps"), list) and mc["future_laps"]:
            el.append(Paragraph(esc(t("pdf_h_projection")), S["h2"]))
            rows = [[t("pdf_th_lap"), t("pdf_th_p10"), t("pdf_th_p50"), t("pdf_th_p90")]]
            n_show = min(8, len(mc["future_laps"]))
            for i in range(n_show):
                try:
                    rows.append([N(mc["future_laps"][i], 0), fmt_laptime(mc["p10"][i]),
                                 f"<b>{fmt_laptime(mc['p50'][i])}</b>", fmt_laptime(mc["p90"][i])])
                except (IndexError, TypeError, KeyError):
                    break
            if len(rows) > 1:
                el.append(make_table(S, rows, [2.4, 3.6, 3.6, 3.6], num_cols=(0, 1, 2, 3), pad=2.4))
                cap = t("pdf_cap_projection")
                if mc.get("low_confidence"):
                    cap += " " + t("pdf_cap_projection_low")
                el.append(Paragraph(esc(cap), S["caption"]))

    # Fuel
    fuel = st.get("combustible") or {}
    if _avail(fuel):
        shown = True
        el.append(Paragraph(esc(t("pdf_h_fuel")), S["h2"]))
        pw = fuel.get("pit_window")
        pw_txt = f"{N(pw[0], 0)}–{N(pw[1], 0)}" if isinstance(pw, list) and len(pw) == 2 \
            and _fin(pw[0]) and _fin(pw[1]) else "—"
        rows = [
            (t("pdf_kv_fuel_rate"), (N(fuel.get("consumo_medio_l"), 2, False, " L/" + t("pdf_unit_lap"))
                                     + (f" (σ {N(fuel.get('consumo_std_l'), 2)})" if _fin(fuel.get("consumo_std_l")) else ""))),
            (t("pdf_kv_fuel_used"), N(fuel.get("combustible_usado_l"), 1, False, " L")),
            (t("pdf_kv_fuel_now"), N(fuel.get("combustible_actual_l"), 1, False, " L")),
            (t("pdf_kv_laps_left"), _range_txt(fuel.get("vueltas_restantes_min"), fuel.get("vueltas_restantes_max"))),
            (t("pdf_kv_pit_window"), t("pdf_pit_window_laps", w=pw_txt) if pw_txt != "—" else "—"),
            (t("pdf_kv_tank"), N(fuel.get("tank_capacity_l"), 0, False, " L")),
        ]
        el.append(_kv_table(S, rows))
    else:
        ctx.note("info", t("pdf_q_no_fuel"))

    # Tyre wear model
    tw = st.get("degradacion_neumatico") or {}
    if _avail(tw):
        shown = True
        el.append(Paragraph(esc(t("pdf_h_tyre_wear")), S["h2"]))
        rows = []
        if tw.get("degradation_detected") is False:
            rows.append((t("pdf_kv_wear_state"), t("pdf_wear_none")))
        elif tw.get("degradation_detected"):
            rows.append((t("pdf_kv_wear_state"), t("pdf_wear_detected")))
        if _fin(tw.get("degradation_rate_s_per_lap")):
            rows.append((t("pdf_kv_wear_rate"), N(tw["degradation_rate_s_per_lap"], 3, True, " s/" + t("pdf_unit_lap"))))
        if _fin(tw.get("wear_pct")):
            rows.append((t("pdf_kv_wear_pct"), N(tw["wear_pct"], 0, False, " %")))
        if _fin(tw.get("remaining_laps")):
            rows.append((t("pdf_kv_wear_remaining"), N(tw["remaining_laps"], 0)))
        if _fin(tw.get("current_delta_s")):
            rows.append((t("pdf_kv_wear_delta"), N(tw["current_delta_s"], 2, True, " s")))
        if _fin(tw.get("cliff_threshold_s")):
            rows.append((t("pdf_kv_wear_cliff"), N(tw["cliff_threshold_s"], 1, False, " s")))
        if _fin(tw.get("left_mean_temp")) and _fin(tw.get("right_mean_temp")):
            rows.append((t("pdf_kv_lr_temp"), f"{N(tw['left_mean_temp'], 1)} / {N(tw['right_mean_temp'], 1)} °C"))
        if rows:
            el.append(_kv_table(S, rows))
    elif isinstance(tw, dict) and tw.get("reason_code") == "wear_inactive":
        ctx.note("info", t("pdf_q_wear_inactive"))

    # Track evolution
    te = st.get("track_evolution") or {}
    if _avail(te) and _fin(te.get("total_gain_s")):
        shown = True
        direction = te.get("direction")
        key = {"improving": "pdf_track_improving", "degrading": "pdf_track_degrading"}.get(direction, "pdf_track_stable")
        el.append(Paragraph(esc(t("pdf_h_track_evo")), S["h2"]))
        el.append(Paragraph(esc(t(key, s=N(abs(te["total_gain_s"]), 2))), S["body"]))
    if not shown:
        el.append(Paragraph(esc(t("pdf_strategy_none")), S["small"]))
    return el


# ── Technical sections (session telemetry summary) ────────────────────────────

def _section_session_tech(ctx: Ctx) -> list:
    tel = _get(ctx.stint, "telemetria_sesion", default={}) or {}
    if not _avail(tel):
        return []
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_tech")), S["h1"])]

    tyre = tel.get("tyre") or {}
    if isinstance(tyre, dict) and any(k in tyre for k in ("FL", "FR", "RL", "RR")):
        el.append(Paragraph(esc(t("pdf_h_tyre_temps")), S["h2"]))
        rows = [[t("pdf_th_position"), t("pdf_th_mean_temp"), t("pdf_th_max_temp"), t("pdf_th_state"),
                 t("pdf_th_camber_grad")]]
        pos_key = {"FL": "pdf_pos_fl", "FR": "pdf_pos_fr", "RL": "pdf_pos_rl", "RR": "pdf_pos_rr"}
        for pos in ("FL", "FR", "RL", "RR"):
            d = tyre.get(pos)
            if not isinstance(d, dict):
                continue
            rows.append([esc(t(pos_key[pos])), N(d.get("mean_temp"), 1, False, " °C"),
                         N(d.get("max_temp"), 1, False, " °C"),
                         esc(t(_STATUS_KEYS[d["status"]])) if d.get("status") in _STATUS_KEYS else "—",
                         N(d.get("camber_gradient"), 1, False, " °C")])
        if len(rows) > 1:
            el.append(make_table(S, rows, [4.0, 3.4, 3.4, 3.6, 3.0], num_cols=(1, 2, 4), pad=2.6))
            extra = []
            if _fin(tyre.get("front_rear_delta")):
                extra.append(t("pdf_tyre_fr_delta", v=N(tyre["front_rear_delta"], 1, True)))
            if _fin(tyre.get("left_right_delta")):
                extra.append(t("pdf_tyre_lr_delta", v=N(tyre["left_right_delta"], 1, True)))
            extra.append(t("pdf_cap_tyre_session"))
            el.append(Paragraph(esc(" ".join(extra)), S["caption"]))

    def block(title, rows):
        rows = [(k, v) for k, v in rows if v != "—"]
        if not rows:
            return None
        return [Paragraph(esc(title), S["h2"]), _kv_table(S, rows, (9.0, 8.4))]

    brake = tel.get("brake") or {}
    bias = _get(ctx.stint, "thermal_analysis", "brake_bias", default={}) or {}
    blocks = []
    b = block(t("pdf_h_brakes"), [
        (t("pdf_kv_brake_eff"), N(brake.get("mean_efficiency"), 2, False, " g/%")),
        (t("pdf_kv_brake_eff_min"), N(brake.get("min_efficiency"), 2, False, " g/%")),
        (t("pdf_kv_fade_pct"), N(brake.get("mean_fade_pct"), 1, False, " %")),
        (t("pdf_kv_brake_bias"), N(bias.get("current_pct"), 1, False, " %") if _avail(bias) else "—"),
    ])
    if b:
        blocks.append(b)
    if _avail(bias) and isinstance(bias.get("typical_range"), list) and len(bias["typical_range"]) == 2 \
            and _fin(bias.get("current_pct")):
        lo, hi = bias["typical_range"]
        if _fin(lo) and _fin(hi) and not (lo <= bias["current_pct"] <= hi):
            ctx.note("info", t("pdf_q_bias_range", v=N(bias["current_pct"], 1), lo=N(lo, 0), hi=N(hi, 0)))
    susp = tel.get("suspension") or {}
    b = block(t("pdf_h_suspension"), [
        (t("pdf_kv_roll_f"), N(susp.get("mean_roll_f"), 1, False, " mm")),
        (t("pdf_kv_roll_r"), N(susp.get("mean_roll_r"), 1, False, " mm")),
        (t("pdf_kv_roll_max"), f"{N(susp.get('max_roll_f'), 1)} / {N(susp.get('max_roll_r'), 1)} mm"
         if _fin(susp.get("max_roll_f")) and _fin(susp.get("max_roll_r")) else "—"),
        (t("pdf_kv_pitch_mean"), N(susp.get("mean_pitch"), 1, False, " mm")),
        (t("pdf_kv_bottoming"), N(susp.get("mean_bottoming_events"), 2, False, " " + t("pdf_unit_per_lap"))),
    ])
    if b:
        blocks.append(b)
    inputs = tel.get("inputs") or {}
    b = block(t("pdf_h_inputs"), [
        (t("pdf_kv_nerv_mean"), N(inputs.get("mean_nervousness"), 2) if _fin(inputs.get("mean_nervousness")) else "—"),
        (t("pdf_kv_nerv_max"), N(inputs.get("max_nervousness"), 2) if _fin(inputs.get("max_nervousness")) else "—"),
        (t("pdf_kv_overlap"), N(inputs.get("mean_overlap_pct"), 1, False, " %")),
    ])
    if b:
        blocks.append(b)
    bal = tel.get("balance") or {}
    b = block(t("pdf_h_balance"), [
        (t("pdf_understeer_pct"), N(bal.get("mean_understeer_pct"), 1)),
        (t("pdf_oversteer_pct"), N(bal.get("mean_oversteer_pct"), 1)),
        (t("pdf_kv_balance_mean"), N(bal.get("balance_mean"), 2, True, " °")),
        (t("pdf_kv_steer_rms"), N(bal.get("steer_rms"), 1, False, " °")),
    ])
    if b:
        blocks.append(b)
    for blk in blocks:
        el.append(KeepTogether(blk))
    el.append(Paragraph(esc(t("pdf_cap_tech_session", n=tel.get("n_laps", "?"))), S["caption"]))
    return el


_STATUS_KEYS = {"fria": "pdf_tyre_fria", "suboptima": "pdf_tyre_suboptima", "optima": "pdf_tyre_optima",
                "caliente": "pdf_tyre_caliente", "sobrecalentada": "pdf_tyre_sobrecalentada"}


# ── Lap-comparison sections ───────────────────────────────────────────────────

def _chart_block(S: dict, title: str, chart: Optional[Chart], caption_key: str, **kw) -> list:
    if not chart:
        return []
    return [KeepTogether([Paragraph(esc(title), S["h2"]), _img(chart, kw.pop("max_w", CONTENT_CM)),
                          Paragraph(esc(t(caption_key)), S["caption"])])]


def _two_lap_table(S: dict, la: str, lb: str, rows: list[tuple[str, str, str]], widths=(7.4, 5.0, 5.0)) -> Table:
    data = [["", esc(la), esc(lb)]] + [[esc(k), a, b] for k, a, b in rows]
    return make_table(S, data, list(widths), num_cols=(1, 2), pad=2.8)


def _section_traces(ctx: Ctx) -> list:
    comp = ctx.comp
    if not comp:
        return []
    S, la, lb = ctx.S, ctx.la, ctx.lb
    el: list = [CondPageBreak(5.5 * cm if ctx.compact else 7 * cm), Paragraph(esc(t("pdf_h_traces")), S["h1"])]
    n0 = len(el)
    c = ctx.compact
    el += _chart_block(S, t("pdf_h_speed"),
                       charts.chart_speed(comp.get("speed_comparison") or {}, la, lb, h=4.6 if c else 6.0),
                       "pdf_cap_speed")
    el += _chart_block(S, t("pdf_h_delta"),
                       charts.chart_delta(comp.get("time_delta_series") or {}, lb, h=3.4 if c else 4.4),
                       "pdf_cap_delta")
    el += _chart_block(S, t("pdf_h_brake_throttle"),
                       charts.chart_brake_throttle(comp.get("brake_comparison") or {},
                                                   comp.get("throttle_comparison") or {}, la, lb,
                                                   h=6.0 if c else 8.6),
                       "pdf_cap_brake_throttle")
    gg = charts.chart_gg(comp.get("gg_diagram"), la, lb, **({"w": 7.2, "h": 6.6} if c else {}))
    el += _chart_block(S, t("pdf_h_gg"), gg, "pdf_cap_gg", max_w=7.5 if c else 9.5)
    if len(el) == n0:
        return []
    return el


def _bottoming_summary(ctx: Ctx, susp: dict) -> list:
    """Events per wheel and worst severity for each lap (instead of one row per event)."""
    S, la, lb = ctx.S, ctx.la, ctx.lb
    per: dict = {}
    for idx, key in ((0, "bottoming_a"), (1, "bottoming_b")):
        for ev in susp.get(key) or []:
            pos = str(ev.get("corner") or "").strip() or "—"
            e = per.setdefault(pos, [[0, None], [0, None]])
            e[idx][0] += 1
            sev = ev.get("severity")
            if _fin(sev) and (e[idx][1] is None or sev > e[idx][1]):
                e[idx][1] = sev
    if not per:
        return []
    order = {"FL": 0, "FR": 1, "RL": 2, "RR": 3}
    pos_key = {"FL": "pdf_pos_fl", "FR": "pdf_pos_fr", "RL": "pdf_pos_rl", "RR": "pdf_pos_rr"}
    rows = [[t("pdf_th_position"), f"{esc(la)} – {esc(t('pdf_th_events'))}", f"{esc(la)} – {esc(t('pdf_th_sev_max'))}",
             f"{esc(lb)} – {esc(t('pdf_th_events'))}", f"{esc(lb)} – {esc(t('pdf_th_sev_max'))}"]]
    for pos in sorted(per, key=lambda p: order.get(p, 9)):
        (na, sa), (nb, sb) = per[pos]
        rows.append([esc(t(pos_key[pos])) if pos in pos_key else esc(pos), N(na, 0),
                     N(sa * 100, 0, False, " %") if sa is not None else "—", N(nb, 0),
                     N(sb * 100, 0, False, " %") if sb is not None else "—"])
    return [Paragraph(esc(t("pdf_h_bottoming_cmp")), S["h2"]),
            make_table(S, rows, [3.4, 3.4, 3.8, 3.4, 3.8], num_cols=(1, 2, 3, 4), pad=2.2),
            Paragraph(esc(t("pdf_cap_bottoming_cmp")), S["caption"])]


def _section_comp_tech(ctx: Ctx) -> list:
    comp = ctx.comp
    if not comp:
        return []
    S, la, lb = ctx.S, ctx.la, ctx.lb
    el: list = []
    missing = []
    c = ctx.compact
    brk = CondPageBreak(5.5 * cm if c else 7 * cm)

    tyre = comp.get("tyre_analysis") or {}
    if _avail(tyre):
        el += [brk,
               Paragraph(esc(t("pdf_h_tyres_cmp", tmin=N(tyre.get("t_min", 80), 0), tmax=N(tyre.get("t_max", 100), 0))),
                         S["h1"])]
        ca = {c["corner"]: c for c in (tyre.get("lap_a") or {}).get("corners", [])}
        cb = {c["corner"]: c for c in (tyre.get("lap_b") or {}).get("corners", [])}
        pos_key = {"FL": "pdf_pos_fl", "FR": "pdf_pos_fr", "RL": "pdf_pos_rl", "RR": "pdf_pos_rr"}
        rows = [[t("pdf_th_position"), f"{esc(la)} – {esc(t('pdf_th_state'))}", f"{esc(la)} (°C)",
                 f"{esc(lb)} – {esc(t('pdf_th_state'))}", f"{esc(lb)} (°C)"]]
        for pos in ("FL", "FR", "RL", "RR"):
            if pos not in ca and pos not in cb:
                continue
            a, b = ca.get(pos, {}), cb.get(pos, {})
            rows.append([esc(t(pos_key[pos])),
                         esc(t(_STATUS_KEYS[a["window_status"]])) if a.get("window_status") in _STATUS_KEYS else "—",
                         N(a.get("surface_mean"), 1),
                         esc(t(_STATUS_KEYS[b["window_status"]])) if b.get("window_status") in _STATUS_KEYS else "—",
                         N(b.get("surface_mean"), 1)])
        if len(rows) > 1:
            el.append(make_table(S, rows, [3.2, 4.2, 2.6, 4.2, 2.6], num_cols=(2, 4), pad=2.8))
        if c:       # the table above already carries state + temperature per tyre: no repeated chart
            el.append(Paragraph(esc(t("pdf_cap_tyres")), S["caption"]))
        else:
            ch = _img(charts.chart_tyre_bars(tyre, la, lb))
            if ch:
                el.append(Spacer(1, 4))
                el += [ch, Paragraph(esc(t("pdf_cap_tyres")), S["caption"])]
    else:
        missing.append(t("pdf_mod_tyres"))

    brake = comp.get("brake_analysis") or {}
    if _avail(brake):
        el += [brk, Paragraph(esc(t("pdf_h_brakes")), S["h1"])]
        sa, sb = brake.get("score_a"), brake.get("score_b")
        ba, bb = brake.get("baseline_a"), brake.get("baseline_b")
        da = (1 - sa / ba) * 100 if _fin(sa) and _fin(ba) and ba else None
        db = (1 - sb / bb) * 100 if _fin(sb) and _fin(bb) and bb else None
        el.append(_two_lap_table(S, la, lb, [
            (t("pdf_kv_brake_score"), N(sa, 3), N(sb, 3)),
            (t("pdf_kv_brake_baseline"), N(ba, 3), N(bb, 3)),
            (t("pdf_kv_brake_degradation"), N(da, 1, False, " %"), N(db, 1, False, " %")),
            (t("pdf_kv_fade_zones"), str(len(brake.get("fade_zones_a") or [])), str(len(brake.get("fade_zones_b") or []))),
        ]))
        for key, lap in (("fade_zones_a", la), ("fade_zones_b", lb)):
            zones = brake.get(key) or []
            n_zones = len(zones)
            if c and n_zones > 5:     # the chart shades every zone; the table lists the 5 worst
                zones = sorted(sorted(zones, key=lambda z: -(z.get("severity") or 0))[:5],
                               key=lambda z: z.get("start") or 0)
            if zones:
                el.append(Paragraph(esc(t("pdf_h_fade_zones", lap=lap)), S["h2"]))
                rows = [[t("pdf_th_start_m"), t("pdf_th_end_m"), t("pdf_th_severity"), t("pdf_th_diagnosis")]]
                for z in zones:
                    sev = z.get("severity")
                    d = "—"
                    if _fin(sev):
                        d = t("pdf_sev_mild") if sev < 0.15 else t("pdf_sev_mod") if sev < 0.30 else t("pdf_sev_severe")
                    rows.append([N(z.get("start"), 0), N(z.get("end"), 0),
                                 N(sev * 100, 0, False, " %") if _fin(sev) else "—", esc(d)])
                el.append(make_table(S, rows, [3.5, 3.5, 3.5, 5.0], num_cols=(0, 1, 2), pad=2.0 if c else 2.4))
                if len(zones) < n_zones:
                    el.append(Paragraph(esc(t("pdf_cap_zones_top", shown=len(zones), total=n_zones)), S["caption"]))
        el += _chart_block(S, t("pdf_h_brake_eff_chart"),
                           charts.chart_brake_fade(brake, la, lb, h=4.2 if c else 5.6), "pdf_cap_brake_fade")
    else:
        missing.append(t("pdf_mod_brakes"))

    inputs = comp.get("driver_inputs") or {}
    if _avail(inputs):
        el += [brk, Paragraph(esc(t("pdf_h_inputs")), S["h1"])]
        na, nb = inputs.get("nervousness_score_a"), inputs.get("nervousness_score_b")

        def nerv(v):
            if not _fin(v):
                return "—"
            lvl = "pdf_nerv_low" if v < 0.25 else "pdf_nerv_mid" if v < 0.5 else "pdf_nerv_high"
            return f"{N(v * 100, 1, False, ' %')} ({esc(t(lvl))})"
        rows = [(t("pdf_kv_nerv"), nerv(na), nerv(nb))]
        fa, fb = inputs.get("fft_bands_a") or {}, inputs.get("fft_bands_b") or {}

        def fft(d):
            if not isinstance(d, dict) or not all(_fin(d.get(k)) for k in ("low", "mid", "high")):
                return "—"
            return f"{N(d['low'] * 100, 1)} / {N(d['mid'] * 100, 1)} / {N(d['high'] * 100, 1)} %"
        rows.append((t("pdf_kv_fft"), fft(fa), fft(fb)))
        rows.append((t("pdf_kv_overlap"), N(inputs.get("overlap_pct_a"), 1, False, " %"),
                     N(inputs.get("overlap_pct_b"), 1, False, " %")))
        el.append(_two_lap_table(S, la, lb, rows))
        el += _chart_block(S, t("pdf_h_nerv_chart"), charts.chart_nervousness(inputs, la, lb, h=3.8 if c else 5.2),
                           "pdf_cap_nerv")
    else:
        missing.append(t("pdf_mod_inputs"))

    susp = comp.get("suspension") or {}
    if _avail(susp):
        el += [brk, Paragraph(esc(t("pdf_h_suspension")), S["h1"])]
        sa, sb = susp.get("summary_a") or {}, susp.get("summary_b") or {}
        rows = []
        for key, lbl, dec, unit in (("max_roll_f", "pdf_kv_roll_max_f", 1, " mm"), ("max_roll_r", "pdf_kv_roll_max_r", 1, " mm"),
                                    ("max_pitch", "pdf_kv_pitch_max", 1, " mm"), ("mean_pitch", "pdf_kv_pitch_mean", 1, " mm"),
                                    ("bottoming_events", "pdf_kv_bottoming_events", 0, "")):
            rows.append((t(lbl), N(sa.get(key), dec, False, unit), N(sb.get(key), dec, False, unit)))
        el.append(_two_lap_table(S, la, lb, rows))
        if c:
            el += _bottoming_summary(ctx, susp)
        for key, lap in (() if c else (("bottoming_a", la), ("bottoming_b", lb))):
            evs = susp.get(key) or []
            if evs:
                el.append(Paragraph(esc(t("pdf_h_bottoming", lap=lap)), S["h2"]))
                rows2 = [[t("pdf_th_position"), t("pdf_th_start_m"), t("pdf_th_end_m"), t("pdf_th_severity")]]
                for ev in evs:
                    rows2.append([esc(ev.get("corner", "")), N(ev.get("start_m"), 0), N(ev.get("end_m"), 0),
                                  N(ev["severity"] * 100, 0, False, " %") if _fin(ev.get("severity")) else "—"])
                el.append(make_table(S, rows2, [3.0, 3.5, 3.5, 3.5], num_cols=(1, 2, 3), pad=2.4))
        el += _chart_block(S, t("pdf_h_susp_chart"), charts.chart_suspension(susp, la, lb, h=6.2 if c else 8.6),
                           "pdf_cap_susp")
    else:
        missing.append(t("pdf_mod_suspension"))

    slip = comp.get("slip_angle") or {}
    if _avail(slip):
        el += [brk, Paragraph(esc(t("pdf_h_slip")), S["h1"])]
        sa, sb = slip.get("summary_a") or {}, slip.get("summary_b") or {}
        rows = []
        for key, lbl, dec, unit in (("beta_max", "pdf_kv_beta_max", 1, " °"), ("beta_p95", "pdf_kv_beta_p95", 1, " °"),
                                    ("balance_mean", "pdf_kv_balance_mean", 2, " °"),
                                    ("understeer_pct", "pdf_understeer_pct", 1, ""),
                                    ("neutral_pct", "pdf_neutral_pct", 1, ""),
                                    ("oversteer_pct", "pdf_oversteer_pct", 1, "")):
            rows.append((t(lbl), N(sa.get(key), dec, False, unit), N(sb.get(key), dec, False, unit)))
        el.append(_two_lap_table(S, la, lb, rows))
        el += _chart_block(S, t("pdf_h_slip_chart"), charts.chart_slip(slip, la, lb, h=6.2 if c else 8.6),
                           "pdf_cap_slip")
    else:
        missing.append(t("pdf_mod_slip"))

    if missing:
        ctx.note("info", t("pdf_q_modules_missing", items=", ".join(missing)))
    return el


# ── Data quality / limitations ────────────────────────────────────────────────

def _collect_quality(ctx: Ctx) -> None:
    if ctx.meta.get("distance_synthetic"):
        ctx.note("warn", t("pdf_q_synthetic_distance"))
    st = ctx.stint
    if ctx.session and not st:
        ctx.note("info", t("pdf_q_no_stint"))
    if st:
        n = st.get("n_laps")
        if _fin(n) and n < 5:
            ctx.note("warn", t("pdf_q_short_session", n=int(n)))
        th = st.get("thermal_analysis") or {}
        if isinstance(th, dict):
            miss = [t(lbl) for key, lbl in (("water_temp", "pdf_ch_water"), ("oil_temp", "pdf_ch_oil"),
                                            ("brake_temps", "pdf_ch_brake_temp"))
                    if isinstance(th.get(key), dict) and th[key].get("available") is False]
            if miss:
                ctx.note("info", t("pdf_q_channels_missing", items=", ".join(miss)))
        hs = st.get("health_summary") or {}
        names = {"thermal": "pdf_mod_thermal", "setup": "pdf_mod_setup", "tyre_degradation": "pdf_mod_tyre_deg",
                 "racing_line": "pdf_mod_racing_line", "slip": "pdf_mod_slip", "corners": "pdf_mod_corners"}
        wear_off = _get(st, "degradacion_neumatico", "reason_code") == "wear_inactive"
        bad = [t(names[k]) for k, v in hs.items()
               if k in names and v == "unavailable" and not (k == "tyre_degradation" and wear_off)]
        if bad:
            ctx.note("info", t("pdf_q_modules_unavailable", items=", ".join(bad)))
        if not _avail(st.get("curvas_sesion")):
            ctx.note("warn", t("pdf_q_no_corners"))
        deg = st.get("degradacion") or {}
        if isinstance(deg, dict) and deg.get("low_confidence"):
            ctx.note("warn", t("pdf_q_deg_lowconf", n=deg.get("n_laps_used", "?"), min=deg.get("min_laps_for_trend", 5)))
    if ctx.comp:
        gt = ctx.comp.get("health_summary") or {}
        if isinstance(gt, dict) and gt.get("overall") == "critical":
            ctx.note("warn", t("pdf_q_health_critical"))


def _section_quality(ctx: Ctx) -> list:
    S = ctx.S
    el: list = [CondPageBreak(7 * cm), Paragraph(esc(t("pdf_h_limits")), S["h1"])]
    if not ctx.notes:
        el.append(Paragraph(esc(t("pdf_q_none")), S["body"]))
    else:
        rows = []
        for level, text in sorted(ctx.notes, key=lambda n: 0 if n[0] == "warn" else 1):
            tag = t("pdf_tag_warn") if level == "warn" else t("pdf_tag_info")
            col = charts.BAD if level == "warn" else charts.INK_2
            rows.append([Paragraph(_colored(esc(tag).upper(), col), S["tag"]), Paragraph(esc(text), S["td"])])
        tbl = Table(rows, colWidths=[2.1 * cm, CONTENT_W - 2.1 * cm])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, C_LINE),
        ]))
        el.append(tbl)
    el.append(Spacer(1, 6))
    el.append(Paragraph(esc(t("pdf_limits_general")), S["caption"]))
    return el


# ── Page decoration ───────────────────────────────────────────────────────────

def _make_canvas(header_left: str, header_right: str, footer_left: str, page_label):
    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._saved: list = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int):
            self.saveState()
            self.setFont(F_REG, 7)
            self.setFillColor(C_INK2)
            page = self._pageNumber
            if page > 1:
                self.drawString(MARGIN_X, PAGE_H - 1.05 * cm, header_left)
                self.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 1.05 * cm, header_right)
                self.setStrokeColor(C_LINE)
                self.setLineWidth(0.5)
                self.line(MARGIN_X, PAGE_H - 1.25 * cm, PAGE_W - MARGIN_X, PAGE_H - 1.25 * cm)
            self.setStrokeColor(C_LINE)
            self.setLineWidth(0.5)
            self.line(MARGIN_X, 1.35 * cm, PAGE_W - MARGIN_X, 1.35 * cm)
            self.drawString(MARGIN_X, 0.9 * cm, footer_left)
            self.drawRightString(PAGE_W - MARGIN_X, 0.9 * cm, page_label(page, total))
            self.restoreState()

    return NumberedCanvas


# ── Assembly ──────────────────────────────────────────────────────────────────

def _build(ctx: Ctx, lang: str) -> bytes:
    S = ctx.S
    laps = _session_laps(ctx) if ctx.kind == "session" else []
    pace = _pace_stats(laps) if laps else {}
    corners_s = _corners_session(ctx)
    corners_c = _corners_compare(ctx)

    # Populate quality notes before rendering the page-1 summary (sections add more later).
    _collect_quality(ctx)

    body: list = []
    if ctx.kind == "session":
        body += _section_pace(ctx, laps, pace)
        body += _section_corners(ctx, corners_s, "session")
        body += _section_setup(ctx)
        body += _section_strategy(ctx)
        body += _section_session_tech(ctx)
    if ctx.comp:
        if ctx.kind == "comparison":
            body += _section_corners(ctx, corners_c, "compare")
            body += _section_setup(ctx)
        body += _section_traces(ctx)
        if ctx.kind == "session":
            body += _section_corners(ctx, corners_c, "compare")
        body += _section_comp_tech(ctx)
    if ctx.kind == "comparison" and not ctx.comp:
        body.append(Paragraph(esc(t("pdf_no_data")), S["body"]))
    # Quality notes may have grown while rendering sections; build the front page last.
    front = _header_block(ctx) + _exec_summary(ctx, laps, pace, corners_s, corners_c) + _quality_box(ctx)
    if ctx.compact and len(ctx.notes) <= 3:
        # everything is already on page 1: no closing page for the limitations, just the standing disclaimer
        story = front + [Spacer(1, 4), Paragraph(esc(t("pdf_limits_general")), S["caption"]), PageBreak()] + body
    else:
        story = front + [PageBreak()] + body + _section_quality(ctx)

    m = ctx.meta
    header_left = _join([m["venue"], m["vehicle"]], " – ") or _title_for(ctx)
    header_right = _join([_title_for(ctx), _fmt_date(m["date"])])
    footer_left = f"{PRODUCT_NAME}  v{REPORT_VERSION}"

    def page_label(page, total):
        return t("pdf_page_of", n=page, total=total)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN_X - 6, rightMargin=MARGIN_X - 6,   # 6 pt frame padding
        topMargin=1.9 * cm, bottomMargin=1.9 * cm,
        title=f"{_title_for(ctx)} – {header_left}", author=PRODUCT_NAME,
        subject=_title_for(ctx), creator=f"{PRODUCT_NAME} v{REPORT_VERSION}", lang=lang,
    )
    doc.build(story, canvasmaker=_make_canvas(header_left, header_right, footer_left, page_label))
    return buf.getvalue()


def _render(ctx_args: tuple, filepath: Optional[str], lang: str) -> bytes:
    lang = "es" if lang not in ("es", "en") else lang
    with LanguageContext(lang):
        ctx = Ctx(*ctx_args)
        pdf = _build(ctx, lang)
    if filepath:
        with open(filepath, "wb") as f:
            f.write(pdf)
        logger.info("PDF saved: %s (%d KB)", filepath, len(pdf) // 1024)
    return pdf


def export_report_pdf(comparison_result: dict, filepath: Optional[str] = None, lang: str = "es") -> bytes:
    """Lap-comparison PDF from a comparison result dict. Returns the PDF bytes."""
    comp = comparison_result if isinstance(comparison_result, dict) else {}
    return _render((None, None, comp, None), filepath, lang)


def export_session_report_pdf(session_result: dict, stint_result: Optional[dict] = None,
                              comparison_result: Optional[dict] = None, metadata: Optional[dict] = None,
                              filepath: Optional[str] = None, lang: str = "es") -> bytes:
    """
    Whole-session PDF from the JSON the frontend already holds: the /analyze-session result,
    the /stint/analyze result and (optionally) a lap comparison. ``metadata`` may carry
    venue / vehicle / driver / log_date / session_type / file to complete the header.
    """
    return _render((session_result, stint_result, comparison_result, metadata), filepath, lang)
