from __future__ import annotations

import math
from pathlib import Path

from fontTools.ttLib import TTFont as FontToolsTTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from . import engine as e
from .visual_v05 import clean_text

_INSTALLED = False
_ORIG = {}

# Enough coverage to reject broken/subset "Persian" fonts while remaining
# deterministic and independent from network access.
_REQUIRED_PERSIAN_GLYPHS = set(
    "ابتثجحخدذرزسشصضطظعغفقکگلمنوهیپچژگ"
    "آأإؤئۀةكيى"
    "۰۱۲۳۴۵۶۷۸۹"
)


def _first_valid_font(*paths):
    for value in paths:
        if not value:
            continue
        p = Path(value).expanduser()
        if p.exists():
            return p
    return None


def _font_has_persian_coverage(path: Path | str | None) -> bool:
    if not path:
        return False
    try:
        font = FontToolsTTFont(str(path), lazy=True)
        cmap = font.getBestCmap() or {}
        return all(ord(ch) in cmap for ch in _REQUIRED_PERSIAN_GLYPHS)
    except Exception:
        return False
    finally:
        try:
            font.close()
        except Exception:
            pass


def _font_from_dirs(name: str):
    for base in e._font_dirs():
        if not base:
            continue
        p = Path(base) / name
        if p.exists():
            return p
    return None


def _pick_persian_family():
    """Prefer Vazirmatn, otherwise use a validated local modern sans.

    Network is never required. Invalid/subset cached Vazirmatn files are ignored
    instead of poisoning the build.
    """
    vazir_r = _font_from_dirs("Vazirmatn-Regular.ttf")
    vazir_b = _first_valid_font(
        _font_from_dirs("Vazirmatn-Bold.ttf"),
        _font_from_dirs("Vazirmatn-Medium.ttf"),
    )
    vazir_ui = _first_valid_font(
        _font_from_dirs("Vazirmatn-Medium.ttf"),
        _font_from_dirs("Vazirmatn-Bold.ttf"),
    )
    if (
        _font_has_persian_coverage(vazir_r)
        and _font_has_persian_coverage(vazir_b)
        and _font_has_persian_coverage(vazir_ui)
    ):
        return "Vazirmatn", vazir_r, vazir_b, vazir_ui

    # Deliberately narrow approved fallback list. DejaVu Sans is local on common
    # Linux runtimes, visually neutral/sans, and has Persian letters + digits.
    dejavu_r = _first_valid_font(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    )
    dejavu_b = _first_valid_font(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    )
    if _font_has_persian_coverage(dejavu_r) and _font_has_persian_coverage(dejavu_b):
        return "DejaVuSans", dejavu_r, dejavu_b, dejavu_b

    raise RuntimeError(
        "FONT_SETUP_FAIL: no approved local Persian sans font with complete "
        "letter/digit coverage. Valid Vazirmatn or DejaVu Sans is required; "
        "network access is not required."
    )


def register_fonts_v062():
    """Register Latin + capability-validated Persian fonts without network."""
    rt_r, rt_b = e._convert_plex_runtime()
    latin_r = _first_valid_font(
        _font_from_dirs("IBMPlexSans-Regular.ttf"),
        rt_r,
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    latin_b = _first_valid_font(
        _font_from_dirs("IBMPlexSans-Bold.ttf"),
        rt_b,
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    family, fa_r, fa_b, fa_ui = _pick_persian_family()

    missing = [
        name
        for name, value in (
            ("Latin", latin_r),
            ("LatinB", latin_b),
            ("Fa", fa_r),
            ("FaB", fa_b),
            ("FaUI", fa_ui),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("FONT_SETUP_FAIL: " + ", ".join(missing))

    known = set(pdfmetrics.getRegisteredFontNames())
    for name, path in (
        ("Latin", latin_r),
        ("LatinB", latin_b),
        ("Fa", fa_r),
        ("FaB", fa_b),
        ("FaUI", fa_ui),
    ):
        if name not in known:
            pdfmetrics.registerFont(TTFont(name, str(path)))

    e._PERSIAN_FONT_FAMILY = family


def _is_compact_metric(value: str, rtl: bool) -> bool:
    text = clean_text(value)
    # Circle is for a true metric token: number, percent, short ratio, version-like
    # token. A phrase/unit belongs in the adaptive capsule.
    letters = [ch for ch in text if ch.isalpha()]
    if letters:
        return False
    visual_len = len(text.replace(" ", ""))
    return visual_len <= 7


def _draw_metric_capsule(c, value, cx, cy, max_width, max_height, th, rtl):
    height = min(max_height, 29 * e.MM)
    target_size = 29.0
    min_size = 16.0
    font = "FaB" if rtl else "LatinB"

    text_w = e.txt_width(value, font, target_size, rtl)
    desired = max(48 * e.MM, text_w + 17 * e.MM)
    width = min(max_width, desired)
    x = cx - width / 2
    y = cy - height / 2

    # Soft outer field + white inner capsule + asymmetric orbit accents.
    e.round_rect(c, x, y, width, height, height / 2,
                 fill=th["soft"], stroke=None, alpha=.96)
    e.round_rect(c, x + 2.2*e.MM, y + 2.2*e.MM,
                 width - 4.4*e.MM, height - 4.4*e.MM,
                 (height - 4.4*e.MM) / 2,
                 fill="#FFFFFF", stroke=th["accent"], sw=.55)
    c.setFillColor(e.color(th["accent2"], .62))
    c.circle(x + 6.2*e.MM, cy, 1.45*e.MM, fill=1, stroke=0)
    c.setFillColor(e.color(th["accent"], .35))
    c.circle(x + width - 6.2*e.MM, cy, 1.1*e.MM, fill=1, stroke=0)

    e.draw_single_line(
        c,
        value,
        x + 7.5*e.MM,
        cy - 4.4*e.MM,
        width - 15*e.MM,
        size=target_size,
        min_size=min_size,
        bold=True,
        colorv=th["deep"],
        align="center",
        rtl=rtl,
    )


def _metric_value_v062(c, value, cx, cy, max_width, max_height, th, rtl):
    value = clean_text(value)
    if not _is_compact_metric(value, rtl):
        return _draw_metric_capsule(
            c, value, cx, cy, max_width, max_height, th, rtl
        )

    radius = min(18 * e.MM, max_height * .43, max_width * .25)
    c.setFillColor(e.color(th["accent"], .08))
    c.circle(cx, cy, radius * 1.15, fill=1, stroke=0)
    c.setStrokeColor(e.color(th["accent"], .25))
    c.setLineWidth(1.1)
    c.circle(cx, cy, radius, fill=0, stroke=1)
    c.setFillColor(e.color("#FFFFFF"))
    c.circle(cx, cy, radius * .83, fill=1, stroke=0)
    for ang in (35, 155, 275):
        a = math.radians(ang)
        nx = cx + math.cos(a) * radius
        ny = cy + math.sin(a) * radius
        c.setFillColor(e.color(th["accent2"], .55))
        c.circle(nx, ny, 1.25 * e.MM, fill=1, stroke=0)

    e.draw_single_line(
        c,
        value,
        cx - radius * 1.20,
        cy - 5.2 * e.MM,
        radius * 2.40,
        size=38,
        min_size=19,
        bold=True,
        colorv=th["deep"],
        align="center",
        rtl=rtl,
    )


def summary_v062(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Overview"), th)
    rtl_page = e.is_fa(p["title"])

    intro_h = 42 * e.MM
    e.round_rect(
        c, e.SAFE_X, y-intro_h, e.W-2*e.SAFE_X, intro_h, 16,
        fill=th["soft"], stroke="#DCE6F2", sw=.45, alpha=.78
    )
    ax = e.W-e.SAFE_X-2.2*e.MM if rtl_page else e.SAFE_X+.7*e.MM
    c.setFillColor(e.color(th["accent"]))
    c.roundRect(
        ax, y-intro_h+5*e.MM, 1.5*e.MM, intro_h-10*e.MM,
        .75*e.MM, fill=1, stroke=0
    )
    e.draw_text(
        c, p["intro"], e.SAFE_X+9*e.MM, y-10*e.MM,
        e.W-2*e.SAFE_X-18*e.MM, size=11.4, leading=17.5,
        max_lines=6, justify=not rtl_page, colorv="#344256"
    )

    cards = p["cards"]
    cols = 2 if len(cards) > 1 else 1
    rows = (len(cards) + cols - 1) // cols
    gap = 6 * e.MM
    bottom = 31 * e.MM
    top = y - intro_h - 7 * e.MM
    h = (top - bottom - gap * (rows - 1)) / rows
    w = (e.W - 2*e.SAFE_X - gap * (cols - 1)) / cols

    for i, card in enumerate(cards):
        col = i % cols
        row = i // cols
        x = e.SAFE_X + col * (w + gap)
        yy = top - row * (h + gap) - h
        e.shadow_card(c, x, yy, w, h, 16)

        cx = x + w / 2
        cy = yy + h * .60
        value = clean_text(card["value"])
        _metric_value_v062(
            c,
            value,
            cx,
            cy,
            max_width=w - 13*e.MM,
            max_height=h * .48,
            th=th,
            rtl=e.is_fa(value),
        )

        e.draw_single_line(
            c, card["label"], x+7*e.MM, yy+16*e.MM, w-14*e.MM,
            size=10.3, min_size=8.8, bold=True,
            colorv="#405066", align="center", rtl=e.is_fa(card["label"])
        )
        if card.get("note"):
            e.draw_single_line(
                c, card["note"], x+7*e.MM, yy+7.5*e.MM, w-14*e.MM,
                size=8.3, min_size=7.0, colorv="#7A8798",
                align="center", rtl=e.is_fa(card["note"])
            )


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    _ORIG["register_fonts"] = e.register_fonts
    _ORIG["summary"] = e.summary

    e.ENGINE_VERSION = "0.6.2"
    e.register_fonts = register_fonts_v062
    e.summary = summary_v062
    e.RENDERERS["summary"] = summary_v062
