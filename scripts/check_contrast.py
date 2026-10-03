"""WCAG contrast verification of the colour tokens of both UI themes.

Reads the tokens from frontend/src/styles/design-system.css (dark, the first
``:root`` block) and frontend/src/styles/theme-light.css (light) and checks the
pairs that actually appear in the UI:

* text pairs   -> WCAG AA 4.5:1
* graphic / UI -> WCAG 3:1 (lap series, borders of controls, status colours)

Also reports the minimum colour distance between lap series under simulated
colour-vision deficiency (informative, not a failure condition).

The light theme is new and must pass every pair. The dark theme predates this
check and is reported as a baseline only (it does not fail the run) unless
``--strict`` is given.

Usage:  python scripts/check_contrast.py [--strict]   (exit 1 on failing pairs)
"""
from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "frontend" / "src" / "styles"
DARK_CSS = STYLES / "design-system.css"
LIGHT_CSS = STYLES / "theme-light.css"

TEXT_MIN = 4.5
GRAPHIC_MIN = 3.0

SURFACES = ["surface-0", "surface-1", "surface-2", "surface-3"]
LAPS = [f"lap-{c}" for c in "abcdef"]

# (foreground, background, minimum ratio, description)
PAIRS: list[tuple[str, str, float, str]] = []
for _s in SURFACES:
    for _t in ("ink-1", "ink-2", "ink-3"):
        PAIRS.append((_t, _s, TEXT_MIN, "text"))
    for _t in ("accent", "ok", "warn", "bad"):
        PAIRS.append((_t, _s, TEXT_MIN, "semantic text"))
for _s in ("surface-0", "surface-1", "surface-2"):
    for _l in LAPS:
        PAIRS.append((_l, _s, GRAPHIC_MIN, "lap series"))
    PAIRS.append(("ink-4", _s, GRAPHIC_MIN, "disabled / decorative"))
    PAIRS.append(("line-strong", _s, GRAPHIC_MIN, "control border"))
PAIRS += [
    ("accent-ink", "accent", TEXT_MIN, "primary button label"),
    ("accent-ink", "accent-hover", TEXT_MIN, "primary button label (hover)"),
    ("map-line", "surface-0", GRAPHIC_MIN, "track map line"),
    ("map-line", "map-casing", GRAPHIC_MIN, "track map line on casing"),
]
# translucent badge backgrounds: tone text over (tone-soft composited on surface)
for _tone in ("accent", "ok", "warn", "bad"):
    for _s in ("surface-1", "surface-2"):
        PAIRS.append((_tone, f"{_tone}-soft@{_s}", TEXT_MIN, "badge text"))


def parse_block(text: str, start: int) -> str:
    open_at = text.index("{", start)
    depth = 0
    for i in range(open_at, len(text)):
        depth += text[i] == "{"
        depth -= text[i] == "}"
        if depth == 0:
            return text[open_at + 1 : i]
    raise ValueError("unbalanced CSS block")


def parse_color(v: str) -> tuple[float, float, float, float] | None:
    v = v.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", v)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)", v)
    if m:
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    return None


def parse_tokens(block: str) -> dict[str, tuple[float, float, float, float]]:
    out: dict[str, tuple[float, float, float, float]] = {}
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    for name, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block):
        c = parse_color(val)
        if c:
            out[name[2:]] = c
    return out


def load_themes(dark_css: Path = DARK_CSS, light_css: Path = LIGHT_CSS) -> dict[str, dict]:
    dtext = dark_css.read_text(encoding="utf-8")
    dark = parse_tokens(parse_block(dtext, dtext.index(":root")))
    ltext = light_css.read_text(encoding="utf-8")
    light = dict(dark)  # light inherits anything it does not override
    light.update(parse_tokens(parse_block(ltext, ltext.index(':root[data-theme="light"]'))))
    return {"dark": dark, "light": light}


def composite(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2) -> float:
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def resolve(tokens: dict, ref: str):
    """Token name, or 'tone-soft@surface' (translucent token over a surface)."""
    if "@" in ref:
        top, base = ref.split("@")
        return composite(tokens[top], tokens[base])
    c = tokens[ref]
    return c if c[3] >= 1 else composite(c, tokens["surface-1"])


def check(tokens: dict) -> list[tuple[str, str, float, float, str, bool]]:
    rows = []
    for fg, bg, minimum, what in PAIRS:
        ratio = contrast(resolve(tokens, fg), resolve(tokens, bg))
        rows.append((fg, bg, ratio, minimum, what, ratio >= minimum))
    return rows


# --- colour-vision-deficiency separation of the lap series (informative) ----
_CVD = {  # Machado et al. 2009, severity 1.0, applied in linear RGB
    "deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def _to_lab(rgb):
    r, g, b = (_lin(x) for x in rgb[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _simulate(rgb, matrix):
    lin = [_lin(x) for x in rgb[:3]]
    out = [max(0.0, min(1.0, sum(m * c for m, c in zip(row, lin)))) for row in matrix]

    def enc(c):
        return 255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)

    return tuple(enc(c) for c in out)


def min_lap_distance(tokens: dict) -> dict[str, tuple[float, str, str]]:
    res = {}
    for name, m in (("normal", None), *_CVD.items()):
        best = (1e9, "", "")
        for a, b in itertools.combinations(LAPS, 2):
            ca, cb = tokens[a], tokens[b]
            if m:
                ca, cb = _simulate(ca, m), _simulate(cb, m)
            la, lb = _to_lab(ca), _to_lab(cb)
            d = sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5
            if d < best[0]:
                best = (d, a, b)
        res[name] = best
    return res


def main(argv: list[str] | None = None) -> int:
    strict = "--strict" in (argv if argv is not None else sys.argv[1:])
    themes = load_themes()
    failures = 0
    for theme, tokens in themes.items():
        rows = check(tokens)
        print(f"\n=== {theme.upper()} ===")
        for fg, bg, ratio, minimum, what, ok in rows:
            if not ok:
                if strict or theme == "light":
                    failures += 1
                print(f"  {'FAIL' if strict or theme == 'light' else 'baseline'} {ratio:5.2f} < {minimum}  {fg} on {bg}  ({what})")
        worst: dict[str, tuple[float, float, str, str]] = {}
        for fg, bg, ratio, minimum, what, ok in rows:
            if what not in worst or ratio / minimum < worst[what][0]:
                worst[what] = (ratio / minimum, ratio, fg, bg)
        for what, (_, ratio, fg, bg) in worst.items():
            print(f"  lowest {what:30s} {ratio:5.2f}:1  ({fg} on {bg})")
        for name, (d, a, b) in min_lap_distance(tokens).items():
            print(f"  lap series min deltaE under {name:13s} {d:5.1f}  ({a} vs {b})")
        print(f"  {len(rows)} pairs checked, {sum(1 for r in rows if not r[5])} failing")
    print("\nOK" if not failures else f"\n{failures} failing pair(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
