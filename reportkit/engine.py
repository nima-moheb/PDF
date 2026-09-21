from __future__ import annotations

import hashlib
import json
import math
import os
import re
from importlib.resources import files
from pathlib import Path

from fontTools.ttLib import TTFont as FontToolsTTFont
from jsonschema import validate
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .qa import preflight_and_render
from .rtl import LTR_RE, visual_rtl, visual_runs

ENGINE_VERSION = "0.3.0"
W, H = A4
MM = 72 / 25.4
SAFE_X = 16 * MM
BOTTOM = 15 * MM
RESUME_URL = "https://nima-moheb.github.io/myCV/"

BANNED = [
    "TODO",
    "DRAFT",
    "INTERNAL NOTE",
    "MANAGER NOTE",
    "CEO NOTE",
    "DEBUG",
    "PLACEHOLDER",
    "FIX LATER",
    "یادداشت داخلی",
    "یادداشت مدیر",
    "بعداً اصلاح",
    "پیش نویس",
    "پیش‌نویس",
]

THEMES = json.loads(files("reportkit").joinpath("data/themes.json").read_text(encoding="utf-8"))
SCHEMA = json.loads(files("reportkit").joinpath("data/report.schema.json").read_text(encoding="utf-8"))


def _first_existing(*paths):
    for p in paths:
        if not p:
            continue
        p = Path(p).expanduser()
        if p.exists():
            return p
    return None


def _font_dirs():
    env = os.environ.get("REPORTKIT_FONT_DIR")
    cache = Path.home() / ".cache" / "nima-report-engine" / "fonts"
    repo_assets = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    return [Path(env).expanduser() if env else None, cache, repo_assets]


def _convert_plex_runtime():
    cache = Path.home() / ".cache" / "nima-report-engine" / "runtime-fonts"
    cache.mkdir(parents=True, exist_ok=True)
    candidates = [
        Path("/opt/pyvenv/lib/python3.13/site-packages/gradio/templates/frontend/static/fonts/IBMPlexSans"),
        Path("/opt/pyvenv/lib/python3.12/site-packages/gradio/templates/frontend/static/fonts/IBMPlexSans"),
    ]
    src_dir = next((p for p in candidates if p.exists()), None)
    out_r = cache / "IBMPlexSans-Regular.ttf"
    out_b = cache / "IBMPlexSans-Bold.ttf"
    if src_dir:
        pairs = [
            (src_dir / "IBMPlexSans-Regular.woff2", out_r),
            (src_dir / "IBMPlexSans-Bold.woff2", out_b),
        ]
        for src, dst in pairs:
            if src.exists() and not dst.exists():
                f = FontToolsTTFont(str(src))
                f.flavor = None
                f.save(str(dst))
    return out_r if out_r.exists() else None, out_b if out_b.exists() else None


def register_fonts():
    dirs = _font_dirs()
    rt_r, rt_b = _convert_plex_runtime()

    def from_dirs(name):
        return _first_existing(*[(d / name) if d else None for d in dirs])

    latin_r = _first_existing(
        from_dirs("IBMPlexSans-Regular.ttf"),
        rt_r,
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    latin_b = _first_existing(
        from_dirs("IBMPlexSans-Bold.ttf"),
        rt_b,
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    fa_r = _first_existing(
        from_dirs("Vazirmatn-Regular.ttf"),
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    fa_b = _first_existing(
        from_dirs("Vazirmatn-Bold.ttf"),
        from_dirs("Vazirmatn-Medium.ttf"),
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    fa_ui = _first_existing(
        from_dirs("Vazirmatn-Medium.ttf"),
        from_dirs("Vazirmatn-Bold.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Medium.ttf",
        fa_b,
    )
    missing = [
        n
        for n, v in [("Latin", latin_r), ("LatinB", latin_b), ("Fa", fa_r), ("FaB", fa_b), ("FaUI", fa_ui)]
        if not v
    ]
    if missing:
        raise RuntimeError("FONT_SETUP_FAIL: " + ", ".join(missing))

    # ReportLab raises if a font name is re-registered in some long-lived runtimes.
    known = set(pdfmetrics.getRegisteredFontNames())
    for name, path in [("Latin", latin_r), ("LatinB", latin_b), ("Fa", fa_r), ("FaB", fa_b), ("FaUI", fa_ui)]:
        if name not in known:
            pdfmetrics.registerFont(TTFont(name, str(path)))


def is_fa(text):
    return bool(re.search(r"[\u0600-\u06FF]", str(text or "")))


def color(hexv, alpha=1):
    c = HexColor(hexv)
    return Color(c.red, c.green, c.blue, alpha=alpha)


def txt_width(text, font, size, rtl=False):
    if rtl:
        total = 0
        for kind, run in visual_runs(str(text)):
            rf = "Latin" if kind == "ltr" else font
            total += pdfmetrics.stringWidth(run, rf, size)
        return total
    return pdfmetrics.stringWidth(str(text), font, size)


def wrap(text, font, size, width, rtl=False):
    raw = str(text)
    if rtl:
        raw = LTR_RE.sub(lambda m: m.group(0).replace(" ", "\u00A0"), raw)
        words = raw.split(" ")
    else:
        words = raw.split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for word in words[1:]:
        cand = cur + " " + word
        if txt_width(cand, font, size, rtl) <= width:
            cur = cand
        else:
            if txt_width(cur, font, size, rtl) > width:
                raise ValueError(f"FIT_FAIL: unbreakable token exceeds {width/MM:.1f}mm: {cur[:120]}")
            lines.append(cur)
            cur = word
    if txt_width(cur, font, size, rtl) > width:
        raise ValueError(f"FIT_FAIL: unbreakable token exceeds {width/MM:.1f}mm: {cur[:120]}")
    lines.append(cur)
    return lines


def draw_visual_line(c, text, x, y, width, font, size, rtl, align="left"):
    if rtl:
        runs = visual_runs(str(text))
        pieces = []
        total = 0
        for kind, run in runs:
            rf = "Latin" if kind == "ltr" else font
            rw = pdfmetrics.stringWidth(run, rf, size)
            pieces.append((run, rf, rw))
            total += rw
        if align == "right":
            xx = x + width - total
        elif align == "center":
            xx = x + (width - total) / 2
        else:
            xx = x
        for run, rf, rw in pieces:
            c.setFont(rf, size)
            c.drawString(xx, y, run)
            xx += rw
    else:
        c.setFont(font, size)
        if align == "right":
            c.drawRightString(x + width, y, str(text))
        elif align == "center":
            c.drawCentredString(x + width / 2, y, str(text))
        else:
            c.drawString(x, y, str(text))


def draw_single_line(
    c,
    text,
    x,
    y,
    width,
    size=8,
    min_size=None,
    font=None,
    rtl=None,
    colorv="#172033",
    bold=False,
    align="left",
):
    text = str(text)
    rtl = is_fa(text) if rtl is None else rtl
    if font is None:
        font = ("FaB" if bold else "Fa") if rtl else ("LatinB" if bold else "Latin")
    min_size = size if min_size is None else min_size
    chosen = size
    while chosen >= min_size - 1e-6 and txt_width(text, font, chosen, rtl) > width:
        chosen -= 0.25
    if chosen < min_size - 1e-6:
        raise ValueError(f"FIT_FAIL: single-line text does not fit: {text[:120]}")
    c.setFillColor(color(colorv))
    draw_visual_line(c, text, x, y, width, font, chosen, rtl, align=align)
    return chosen


def draw_text(
    c,
    text,
    x,
    y,
    width,
    size=11,
    font=None,
    leading=None,
    rtl=None,
    colorv="#172033",
    max_lines=None,
    bold=False,
):
    text = str(text)
    rtl = is_fa(text) if rtl is None else rtl
    if font is None:
        font = ("FaB" if bold else "Fa") if rtl else ("LatinB" if bold else "Latin")
    leading = leading or size * 1.52
    lines = wrap(text, font, size, width, rtl)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError(f"FIT_FAIL: text needs {len(lines)} lines, max {max_lines}: {text[:120]}")
    c.setFillColor(color(colorv))
    yy = y
    for line in lines:
        draw_visual_line(c, line, x, yy, width, font, size, rtl, align="right" if rtl else "left")
        yy -= leading
    return yy


def round_rect(c, x, y, w, h, r=10, fill="#FFFFFF", stroke=None, sw=0.5, alpha=1):
    c.saveState()
    c.setFillColor(color(fill, alpha))
    if stroke:
        c.setStrokeColor(color(stroke))
        c.setLineWidth(sw)
    else:
        c.setStrokeColor(color(fill, 0))
    c.roundRect(x, y, w, h, r, fill=1, stroke=1 if stroke else 0)
    c.restoreState()


def shadow_card(c, x, y, w, h, r=10, fill="#FFFFFF", accent=None):
    round_rect(c, x + 2, y - 2, w, h, r, fill="#0A1930", alpha=0.07)
    round_rect(c, x, y, w, h, r, fill=fill, stroke="#DDE5F1", sw=0.45)
    if accent:
        c.setFillColor(color(accent))
        c.roundRect(x, y, w, 3, r / 2, fill=1, stroke=0)


def glow_line(c, x1, y1, x2, y2, th, width=1.0):
    c.saveState()
    c.setStrokeColor(color(th["accent2"], 0.20))
    c.setLineWidth(width * 3.2)
    c.line(x1, y1, x2, y2)
    c.setStrokeColor(color(th["accent"], 0.72))
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    c.restoreState()


def pill(c, text, x, y, w, h, th, dark=False):
    fill = "#FFFFFF" if dark else th["soft"]
    fg = th["deep"] if dark else th["accent"]
    round_rect(c, x, y, w, h, h / 2, fill=fill, stroke=None, alpha=0.95 if dark else 1)
    draw_single_line(c, str(text).upper(), x + 2 * MM, y + h / 2 - 2.2, w - 4 * MM, size=7.3, min_size=6.4, font="LatinB", rtl=False, colorv=fg, align="center")


def draw_resume_link(c, x, y, th, label="VIEW RESUME  ↗", size=7.2, align="left"):
    c.saveState()
    c.setFont("LatinB", size)
    tw = pdfmetrics.stringWidth(label, "LatinB", size)
    tx = x - tw if align == "right" else x
    c.setFillColor(color(th["accent"]))
    c.drawString(tx, y, label)
    c.setStrokeColor(color(th["accent"], 0.55))
    c.setLineWidth(0.45)
    c.line(tx, y - 1.4, tx + tw, y - 1.4)
    c.linkURL(RESUME_URL, (tx - 2, y - 4, tx + tw + 3, y + size + 4), relative=0, thickness=0)
    c.restoreState()
    return tx, tw


def _pdf_uri_count(path, target):
    count = 0
    rd = PdfReader(str(path))
    for page in rd.pages:
        for ref in page.get("/Annots", []) or []:
            obj = ref.get_object()
            action = obj.get("/A")
            if action and action.get("/URI") == target:
                count += 1
    return count


def _measure_block(block, width):
    kind = block.get("kind", "text")
    if kind == "heading":
        rtl = is_fa(block["text"])
        return len(wrap(block["text"], "FaB" if rtl else "LatinB", 14.7, width, rtl)) * 14.7 * 1.52 + 4 * MM
    if kind == "text":
        rtl = is_fa(block["text"])
        return len(wrap(block["text"], "Fa" if rtl else "Latin", 10.9, width, rtl)) * 10.9 * 1.52 + 3.5 * MM
    if kind == "bullets":
        total = 0
        for item in block["items"]:
            rtl = is_fa(item)
            total += len(wrap(item, "Fa" if rtl else "Latin", 10.2, width - 7 * MM, rtl)) * 10.2 * 1.52 + 2.5 * MM
        return total
    raise ValueError(f"SCHEMA_FAIL: unsupported text block {kind!r}")


def _measure_group(group, width):
    h = 12 * MM
    if group.get("title"):
        rtl = is_fa(group["title"])
        h += len(wrap(group["title"], "FaB" if rtl else "LatinB", 14.7, width, rtl)) * 14.7 * 1.52 + 4 * MM
    for block in group.get("content", []):
        h += _measure_block(block, width)
    return h + 4 * MM


def header_footer(c, meta, page, page_title, th):
    total = int(meta.get("_page_count", page))
    hy = H - 15.2 * MM
    hh = 8.6 * MM
    round_rect(c, SAFE_X, hy, W - 2 * SAFE_X, hh, hh / 2, fill="#FFFFFF", stroke="#DCE6F3", sw=0.45)
    c.setFillColor(color(th["accent2"], 0.25))
    c.circle(SAFE_X + 5 * MM, hy + hh / 2, 2.5 * MM, fill=1, stroke=0)
    c.setFillColor(color(th["accent"]))
    c.circle(SAFE_X + 5 * MM, hy + hh / 2, 1.15 * MM, fill=1, stroke=0)
    draw_single_line(c, meta["title"].upper(), SAFE_X + 10 * MM, hy + 3.1 * MM, 70 * MM, size=6.9, min_size=6.1, font="LatinB", rtl=False, colorv="#66758A")
    if page_title:
        draw_single_line(
            c,
            page_title,
            W - SAFE_X - 75 * MM,
            hy + 3.0 * MM,
            69 * MM,
            size=7.5,
            min_size=6.2,
            bold=True,
            colorv=th["deep"],
            align="right",
        )
    glow_line(c, SAFE_X + 10 * MM, hy - 0.8 * MM, SAFE_X + 55 * MM, hy - 0.8 * MM, th, 0.65)

    fy = 9.6 * MM
    c.setStrokeColor(color("#DCE6F3"))
    c.setLineWidth(0.45)
    c.line(SAFE_X, fy + 5.6 * MM, W - SAFE_X, fy + 5.6 * MM)
    c.setStrokeColor(color(th["accent"], 0.85))
    c.setLineWidth(1.15)
    c.line(SAFE_X, fy + 5.6 * MM, SAFE_X + 27 * MM, fy + 5.6 * MM)
    draw_single_line(c, "Nima Moheb  //  Full Stack Developer", SAFE_X, fy + 1.7 * MM, 70 * MM, size=6.9, min_size=6.5, font="LatinB", rtl=False, colorv="#59687C")
    if meta.get("branding") in ("normal", "prominent"):
        draw_resume_link(c, SAFE_X + 78 * MM, fy + 1.7 * MM, th, label="VIEW RESUME  ↗", size=6.9)
    pw = 30 * MM
    ph = 7.2 * MM
    px = W - SAFE_X - pw
    py = fy - 0.2 * MM
    round_rect(c, px, py, pw, ph, ph / 2, fill=th["deep"])
    c.setFont("LatinB", 6.6)
    c.setFillColor(color(th["accent2"]))
    c.drawString(px + 4 * MM, py + 2.5 * MM, "PAGE")
    c.setFont("LatinB", 8.1)
    c.setFillColor(white)
    c.drawRightString(px + pw - 4 * MM, py + 2.25 * MM, f"{page:02d} / {total:02d}")


def tech_grid(c, th, dark=False):
    c.saveState()
    c.setLineWidth(0.25)
    base = "#FFFFFF" if dark else th["accent"]
    c.setStrokeColor(color(base, 0.06 if dark else 0.045))
    step = 9 * MM
    x = 0
    while x < W:
        c.line(x, 0, x, H)
        x += step
    y = 0
    while y < H:
        c.line(0, y, W, y)
        y += step
    if not dark:
        cx = W - 22 * MM
        cy = 49 * MM
        c.setStrokeColor(color(th["accent"], 0.045))
        c.setLineWidth(0.8)
        for rr in (18 * MM, 27 * MM, 36 * MM):
            c.circle(cx, cy, rr, fill=0, stroke=1)
        c.setFillColor(color(th["accent2"], 0.09))
        for dx, dy in ((0, 0), (-20 * MM, 8 * MM), (10 * MM, 23 * MM), (-8 * MM, 31 * MM)):
            c.circle(cx + dx, cy + dy, 1.5 * MM, fill=1, stroke=0)
    c.restoreState()


def _wave_path(c, rtl, th):
    c.saveState()
    pts = (
        [(0, H * 0.94), (0, H * 0.53), (W * 0.63, H * 0.14), (W * 0.77, H * 0.14)]
        if rtl
        else [(W, H * 0.94), (W, H * 0.53), (W * 0.37, H * 0.14), (W * 0.23, H * 0.14)]
    )
    pth = c.beginPath()
    pth.moveTo(*pts[0])
    for pt in pts[1:]:
        pth.lineTo(*pt)
    pth.close()
    c.setFillColor(color(th["accent2"], 0.10))
    c.setStrokeColor(color(th["accent2"], 0.55))
    c.setLineWidth(1.2)
    c.drawPath(pth, fill=1, stroke=1)

    def ribbon(y0, amp, alpha, offset):
        p = c.beginPath()
        if rtl:
            p.moveTo(W, y0)
            p.curveTo(W * 0.79, y0 + amp * 0.70, W * 0.64, y0 - amp * 0.55, W * 0.45, y0 + amp * 0.08)
            p.curveTo(W * 0.29, y0 + amp * 0.55, W * 0.16, y0 - amp * 0.20, 0, y0 + amp * 0.22)
        else:
            p.moveTo(0, y0)
            p.curveTo(W * 0.21, y0 + amp * 0.70, W * 0.36, y0 - amp * 0.55, W * 0.55, y0 + amp * 0.08)
            p.curveTo(W * 0.71, y0 + amp * 0.55, W * 0.84, y0 - amp * 0.20, W, y0 + amp * 0.22)
        c.setStrokeColor(color(th["accent2"], alpha))
        c.setLineWidth(1.0 + offset * 0.45)
        c.drawPath(p, fill=0, stroke=1)

    for i in range(13):
        ribbon(56 * MM + i * 2.0 * MM, 16 * MM + i * 0.55 * MM, 0.10 + i * 0.015, i % 3)
    nodes = [(0.14, 0.31), (0.27, 0.37), (0.40, 0.29), (0.55, 0.41), (0.70, 0.35), (0.86, 0.46)]
    for nx, ny in nodes:
        x = (1 - nx) * W if rtl else nx * W
        y = ny * H
        c.setFillColor(color(th["accent2"], 0.15))
        c.circle(x, y, 4.0 * MM, fill=1, stroke=0)
        c.setFillColor(color(th["accent2"]))
        c.circle(x, y, 1.2 * MM, fill=1, stroke=0)
    c.restoreState()


def cover(c, meta, p, th):
    variant = p.get("variant", "digital-wave")
    if variant != "digital-wave":
        raise ValueError(f"DESIGN_FAIL: unsupported cover variant {variant!r}")
    title = p.get("title", meta["title"])
    rtl = bool(p.get("direction") == "rtl" or (p.get("direction") != "ltr" and is_fa(title)))
    c.setFillColor(color(th["deep"]))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    if rtl:
        c.linearGradient(W, 0, 0, H, [color(th["deep"]), color(th["accent"])], [0, 0.88])
    else:
        c.linearGradient(0, 0, W, H, [color(th["deep"]), color(th["accent"])], [0, 0.88])
    tech_grid(c, th, dark=True)
    _wave_path(c, rtl, th)

    eyebrow = p.get("eyebrow", "گزارش" if rtl else "REPORT")
    c.setFillColor(color(th["accent2"]))
    c.setLineWidth(1.4)
    if rtl:
        c.line(W - 18 * MM, H - 37 * MM, W - 5 * MM, H - 37 * MM)
        draw_text(c, eyebrow, W - 82 * MM, H - 44 * MM, 64 * MM, size=8.8, bold=True, rtl=is_fa(eyebrow), colorv="#EAF5FF", max_lines=1)
        draw_single_line(c, "DATA  ←  INSIGHT  ←  IMPACT", 16 * MM, H - 31 * MM, 70 * MM, size=6.8, min_size=6.4, font="LatinB", rtl=False, colorv="#BFD8FF")
    else:
        c.line(18 * MM, H - 37 * MM, 31 * MM, H - 37 * MM)
        draw_text(c, eyebrow, 18 * MM, H - 44 * MM, 64 * MM, size=8.8, bold=True, rtl=False, colorv="#EAF5FF", max_lines=1)
        draw_single_line(c, "DATA  →  INSIGHT  →  IMPACT", W - 86 * MM, H - 31 * MM, 70 * MM, size=6.8, min_size=6.4, font="LatinB", rtl=False, colorv="#BFD8FF", align="right")

    title_w = 118 * MM
    tx = W - 18 * MM - title_w if rtl else 18 * MM
    y = H - 70 * MM
    font = "FaB" if rtl else "LatinB"
    size = 31.5 if rtl else 32.5
    lines = wrap(title, font, size, title_w, rtl)
    if len(lines) > 4:
        raise ValueError("FIT_FAIL: cover title too long")
    c.setFillColor(white)
    for line in lines:
        draw_visual_line(c, line, tx, y, title_w, font, size, rtl, align="right" if rtl else "left")
        y -= size * 1.16

    uy = y + 2 * MM
    if rtl:
        glow_line(c, tx + title_w - 42 * MM, uy, tx + title_w, uy, th, 0.9)
    else:
        glow_line(c, tx, uy, tx + 42 * MM, uy, th, 0.9)

    subtitle = p.get("subtitle", meta.get("subtitle", ""))
    if subtitle:
        y -= 7 * MM
        draw_text(c, subtitle, tx, y, title_w, size=11.2, rtl=rtl if is_fa(subtitle) else None, colorv="#EAF2FF", max_lines=5)

    yb = H - 160 * MM
    gap = 3.2 * MM
    cw = (title_w - gap * 2) / 3
    ch = 24 * MM
    cells = (
        [("برای", meta.get("recipient", "")), ("تاریخ", meta.get("date", "")), ("تهیه شده توسط", meta.get("author", "Nima Moheb"))]
        if rtl
        else [("Prepared by", meta.get("author", "Nima Moheb")), ("Date", meta.get("date", "")), ("For", meta.get("recipient", ""))]
    )
    for i, (lab, val) in enumerate(cells):
        x = tx + i * (cw + gap)
        round_rect(c, x, yb, cw, ch, 9, fill="#061A36", stroke=th["accent2"], sw=0.45, alpha=0.64)
        draw_text(c, lab, x + 4 * MM, yb + 16 * MM, cw - 8 * MM, size=6.5, bold=True, rtl=is_fa(lab), colorv="#BFD8FF", max_lines=1)
        draw_text(c, str(val), x + 4 * MM, yb + 7.5 * MM, cw - 8 * MM, size=8.6, bold=True, rtl=is_fa(str(val)), colorv="#FFFFFF", max_lines=2)

    draw_single_line(c, "NIMA REPORT ENGINE", 18 * MM if not rtl else W - 78 * MM, 13 * MM, 60 * MM, size=6.3, min_size=6.3, font="LatinB", rtl=False, colorv="#93C7FF", align="right" if rtl else "left")
    draw_single_line(c, "STRUCTURED  /  TRACEABLE  /  FINAL", 18 * MM if rtl else W - 108 * MM, 13 * MM, 90 * MM, size=6.3, min_size=6.0, font="LatinB", rtl=False, colorv="#93C7FF", align="left" if rtl else "right")


def page_title(c, title, eyebrow, th, y=H - 30 * MM):
    draw_single_line(c, str(eyebrow).upper(), SAFE_X, y + 8 * MM, 80 * MM, size=7.4, min_size=6.4, font="LatinB", rtl=False, colorv=th["accent"])
    draw_text(c, title, SAFE_X, y, W - 2 * SAFE_X, size=21.5, bold=True, max_lines=2)
    return y - 13 * MM


def summary(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Overview"), th)
    y = draw_text(c, p["intro"], SAFE_X, y, W - 2 * SAFE_X, size=10.8, max_lines=5)
    y -= 8 * MM
    cards = p["cards"]
    gap = 6 * MM
    w = (W - 2 * SAFE_X - gap) / 2
    h = 59 * MM
    for i, card in enumerate(cards):
        col = i % 2
        row = i // 2
        x = SAFE_X + col * (w + gap)
        yy = y - row * (h + gap) - h
        shadow_card(c, x, yy, w, h, 12, accent=th["accent"])
        draw_single_line(c, card["value"], x + 6 * MM, yy + h - 13 * MM, w - 12 * MM, size=24, min_size=16, bold=True, colorv=th["deep"])
        draw_text(c, card["label"], x + 6 * MM, yy + h - 24 * MM, w - 12 * MM, size=10, bold=True, max_lines=2)
        if card.get("note"):
            draw_text(c, card["note"], x + 6 * MM, yy + 9 * MM, w - 12 * MM, size=8.4, colorv="#6E7D92", max_lines=2)


def text_page(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Report"), th)
    groups = []
    current = {"title": "", "content": []}
    for block in p["blocks"]:
        if block["kind"] == "heading":
            if current["title"] or current["content"]:
                groups.append(current)
            current = {"title": block["text"], "content": []}
        else:
            current["content"].append(block)
    if current["title"] or current["content"]:
        groups.append(current)
    gap = 5 * MM
    bottom = 30 * MM
    tw = W - 2 * SAFE_X - 14 * MM
    required = [max(34 * MM, _measure_group(g, tw)) for g in groups]
    available = y - bottom - gap * (len(groups) - 1)
    if sum(required) > available:
        raise ValueError(f"FIT_FAIL: text groups need {sum(required)/MM:.1f}mm, have {available/MM:.1f}mm on {p['id']}")
    extra = available - sum(required)
    bonus = min(extra / max(len(groups), 1), 10 * MM)
    heights = [h + bonus for h in required]
    top = y
    for gi, (group, card_h) in enumerate(zip(groups, heights)):
        yy = top - card_h
        shadow_card(c, SAFE_X, yy, W - 2 * SAFE_X, card_h, 13, accent=th["accent"] if gi == 0 else None)
        tx = SAFE_X + 7 * MM
        cy = top - 10 * MM
        if group["title"]:
            cy = draw_text(c, group["title"], tx, cy, tw, size=14.7, bold=True, max_lines=2)
            cy -= 4 * MM
        for block in group["content"]:
            if block["kind"] == "text":
                cy = draw_text(c, block["text"], tx, cy, tw, size=10.9, max_lines=12)
                cy -= 3.5 * MM
            elif block["kind"] == "bullets":
                for item in block["items"]:
                    rtl = is_fa(item)
                    bx = tx + 5 * MM
                    bw = tw - 7 * MM
                    dotx = tx + tw - 1.8 * MM if rtl else tx + 1.6 * MM
                    c.setFillColor(color(th["accent"]))
                    c.circle(dotx, cy + 1.4, 1.35, fill=1, stroke=0)
                    cy = draw_text(c, item, bx, cy, bw, size=10.2, max_lines=4)
                    cy -= 2.5 * MM
        if cy < yy + 6 * MM:
            raise ValueError(f"FIT_FAIL: text group overflow on page {p['id']}")
        top = yy - gap


def cards_page(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Highlights"), th)
    cards = p["cards"]
    gap = 5 * MM
    w = (W - 2 * SAFE_X - gap) / 2
    h = 45 * MM
    for i, card in enumerate(cards):
        x = SAFE_X + (i % 2) * (w + gap)
        yy = y - (i // 2) * (h + gap) - h
        shadow_card(c, x, yy, w, h, 13, accent=th["accent"])
        draw_text(c, card["title"], x + 6 * MM, yy + h - 10 * MM, w - 12 * MM, size=11.2, bold=True, max_lines=2)
        draw_text(c, card["text"], x + 6 * MM, yy + h - 23 * MM, w - 12 * MM, size=9, max_lines=5, colorv="#536174")


def _chart_label(c, label, center, y, slot_width):
    draw_single_line(c, label, center - slot_width / 2, y, slot_width, size=7, min_size=6.0, font="Latin", rtl=is_fa(label), colorv="#69778A", align="center")


def chart_text(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Data"), th)
    chart = p["chart"]
    data = [float(v) for v in chart["data"]]
    labels = chart["labels"]
    box_x = SAFE_X
    box_y = 74 * MM
    box_w = W - 2 * SAFE_X
    box_h = 105 * MM
    shadow_card(c, box_x, box_y, box_w, box_h, 14)
    draw_single_line(c, chart.get("title", "TREND").upper(), box_x + 7 * MM, box_y + box_h - 11 * MM, box_w - 14 * MM, size=8, min_size=7, font="LatinB", rtl=False, colorv="#536174")

    maxv = max(data)
    minv = min(data)
    if maxv == minv:
        maxv = minv + 1
    pad = (maxv - minv) * 0.16
    lo = minv - pad
    hi = maxv + pad
    left = box_x + 15 * MM
    bottom = box_y + 20 * MM
    gw = box_w - 28 * MM
    gh = box_h - 41 * MM

    c.setFont("Latin", 6.6)
    c.setFillColor(color("#7A8798"))
    for i in range(4):
        ratio = i / 3
        yy = bottom + ratio * gh
        val = lo + ratio * (hi - lo)
        c.setStrokeColor(color("#D9E2EE"))
        c.setLineWidth(0.35)
        c.line(left, yy, left + gw, yy)
        c.drawRightString(left - 3 * MM, yy - 2, f"{val:.0f}")

    typ = chart["type"]
    if typ == "bar":
        slot = gw / len(data)
        bw = min(13 * MM, slot * 0.56)
        for i, v in enumerate(data):
            x = left + i * slot + (slot - bw) / 2
            h = max(1.4 * MM, gh * (v - lo) / (hi - lo))
            c.setFillColor(color("#0A1930", 0.08))
            c.roundRect(x + 1.2, bottom - 1.2, bw, h, bw * 0.22, fill=1, stroke=0)
            c.setFillColor(color(th["accent"]))
            c.roundRect(x, bottom, bw, h, bw * 0.22, fill=1, stroke=0)
            draw_single_line(c, f"{v:g}", x - slot * 0.2, bottom + h + 3.5, bw + slot * 0.4, size=7.3, min_size=6.3, font="LatinB", rtl=False, colorv=th["deep"], align="center")
            _chart_label(c, labels[i], x + bw / 2, bottom - 10, slot * 0.9)
    else:
        pts = []
        slot = gw / max(len(data) - 1, 1)
        for i, v in enumerate(data):
            x = left + i * slot
            yy = bottom + gh * (v - lo) / (hi - lo)
            pts.append((x, yy, v))
        c.setStrokeColor(color(th["accent"]))
        c.setLineWidth(2.4)
        for a, b in zip(pts, pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
        for i, (x, yy, v) in enumerate(pts):
            c.setFillColor(color(th["accent2"], 0.20))
            c.circle(x, yy, 4.0, fill=1, stroke=0)
            c.setFillColor(color(th["accent"]))
            c.circle(x, yy, 2.2, fill=1, stroke=0)
            draw_single_line(c, f"{v:g}", x - 10 * MM, yy + 7, 20 * MM, size=7.1, min_size=6.2, font="LatinB", rtl=False, colorv=th["deep"], align="center")
            label_width = min(25 * MM, gw / max(len(data), 1) * 0.95)
            _chart_label(c, labels[i], x, bottom - 10, label_width)

    ay = 31 * MM
    ah = 34 * MM
    round_rect(c, SAFE_X, ay, W - 2 * SAFE_X, ah, 12, fill=th["soft"], stroke=th["accent"], sw=0.5)
    draw_text(c, p["analysis"], SAFE_X + 6 * MM, ay + ah - 9 * MM, W - 2 * SAFE_X - 12 * MM, size=9.4, max_lines=6)
    if p.get("source"):
        draw_text(c, "Source: " + p["source"], SAFE_X, 24 * MM, W - 2 * SAFE_X, size=7, colorv="#7A8798", max_lines=1)


def comparison(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Comparison"), th)
    items = p["items"]
    gap = 5 * MM
    w = (W - 2 * SAFE_X - gap * (len(items) - 1)) / len(items)
    h = 120 * MM
    for i, item in enumerate(items):
        x = SAFE_X + i * (w + gap)
        yy = y - h
        shadow_card(c, x, yy, w, h, 14, accent=th["accent"])
        c.setFillColor(color(th["accent"]))
        c.circle(x + w - 8 * MM, yy + h - 10 * MM, 4 * MM, fill=1, stroke=0)
        draw_text(c, item["title"], x + 6 * MM, yy + h - 12 * MM, w - 18 * MM, size=11.2, bold=True, max_lines=2)
        if "value" in item:
            draw_single_line(c, item["value"], x + 6 * MM, yy + h - 30 * MM, w - 12 * MM, size=20, min_size=14, bold=True, colorv=th["deep"])
        by = yy + h - 44 * MM
        for bullet in item["bullets"]:
            by = draw_text(c, "• " + bullet, x + 6 * MM, by, w - 12 * MM, size=8.6, max_lines=3)
            by -= 3 * MM
        if by < yy + 8 * MM:
            raise ValueError(f"FIT_FAIL: comparison card overflow on page {p['id']}")


def _table_cell_lines(value, width, header=False):
    text = str(value)
    rtl = is_fa(text)
    font = ("FaUI" if header else "Fa") if rtl else ("LatinB" if header else "Latin")
    size = 8.2
    lines = wrap(text, font, size, width, rtl)
    limit = 2 if header else 3
    if len(lines) > limit:
        raise ValueError(f"FIT_FAIL: table cell needs {len(lines)} lines (max {limit}): {text[:120]}")
    return lines, rtl, font, size


def table_page(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Table"), th)
    cols = p["columns"]
    rows = p["rows"]
    x = SAFE_X
    total = W - 2 * SAFE_X
    widths = [total / len(cols)] * len(cols)
    cell_pad = 4 * MM

    header_lines = [_table_cell_lines(col, widths[j] - 2 * cell_pad, header=True) for j, col in enumerate(cols)]
    hh = max(14 * MM, max(len(v[0]) for v in header_lines) * 9.8 + 7 * MM)
    row_specs = []
    for row in rows:
        cells = [_table_cell_lines(val, widths[j] - 2 * cell_pad, header=False) for j, val in enumerate(row)]
        rh = max(13 * MM, max(len(v[0]) for v in cells) * 9.8 + 6 * MM)
        row_specs.append((cells, rh))
    h = hh + sum(rh for _, rh in row_specs)
    if h > y - 28 * MM:
        raise ValueError(f"FIT_FAIL: table needs {h/MM:.1f}mm, page has {(y-28*MM)/MM:.1f}mm")
    yy = y - h
    shadow_card(c, x, yy, total, h, 13)
    c.setFillColor(color(th["deep"]))
    c.roundRect(x, yy + h - hh, total, hh, 11, fill=1, stroke=0)
    c.setFillColor(color(th["accent"]))
    c.roundRect(x, yy + h - 2.6, total, 2.6, 1.3, fill=1, stroke=0)

    xx = x
    for j, (lines, rtl, font, size) in enumerate(header_lines):
        cy = yy + h - hh / 2 + (len(lines) - 1) * 4.9 - 2.5
        c.setFillColor(white)
        for line in lines:
            draw_visual_line(c, line, xx + cell_pad, cy, widths[j] - 2 * cell_pad, font, size, rtl, align="right" if rtl else "left")
            cy -= 9.8
        xx += widths[j]

    top = yy + h - hh
    for i, (cells, rh) in enumerate(row_specs):
        ry = top - rh
        if i % 2 == 0:
            c.setFillColor(color(th["soft"], 0.55))
            c.rect(x, ry, total, rh, fill=1, stroke=0)
        xx = x
        for j, (lines, rtl, font, size) in enumerate(cells):
            cy = ry + rh / 2 + (len(lines) - 1) * 4.9 - 2.5
            c.setFillColor(color("#263449"))
            for line in lines:
                draw_visual_line(c, line, xx + cell_pad, cy, widths[j] - 2 * cell_pad, font, size, rtl, align="right" if rtl else "left")
                cy -= 9.8
            xx += widths[j]
        c.setStrokeColor(color("#D9E2EE"))
        c.setLineWidth(0.25)
        c.line(x, ry, x + total, ry)
        top = ry


def _resolve_asset(meta, value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(meta["_config_dir"]) / path
    return path.resolve()


def image_text(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Evidence"), th)
    x = SAFE_X
    iw = W - 2 * SAFE_X
    ih = 132 * MM
    iy = y - ih
    shadow_card(c, x, iy, iw, ih, 14)
    img = _resolve_asset(meta, p["image"])
    if not img.exists():
        raise ValueError(f"ASSET_FAIL: image page {p['id']} requires {img}")
    c.drawImage(str(img), x + 4 * MM, iy + 4 * MM, iw - 8 * MM, ih - 8 * MM, preserveAspectRatio=True, anchor="c", mask="auto")
    draw_text(c, p["text"], SAFE_X, iy - 10 * MM, W - 2 * SAFE_X, size=10.2, max_lines=6)


def timeline(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Timeline"), th)
    items = p["items"]
    xline = SAFE_X + 14 * MM
    c.setStrokeColor(color(th["accent"], 0.35))
    c.setLineWidth(2)
    c.line(xline, 36 * MM, xline, y - 5 * MM)
    gap = (y - 48 * MM) / len(items)
    yy = y - 12 * MM
    for i, item in enumerate(items):
        c.setFillColor(color(th["accent2"]))
        c.circle(xline, yy, 4.2 * MM, fill=1, stroke=0)
        c.setFillColor(color(th["accent"]))
        c.circle(xline, yy, 2.1 * MM, fill=1, stroke=0)
        cw = W - xline - 10 * MM - SAFE_X
        shadow_card(c, xline + 10 * MM, yy - 17 * MM, cw, 32 * MM, 10, accent=th["accent"] if i == 0 else None)
        draw_text(c, item["title"], xline + 16 * MM, yy + 7 * MM, cw - 12 * MM, size=10.5, bold=True, max_lines=2)
        draw_text(c, item["text"], xline + 16 * MM, yy - 3 * MM, cw - 12 * MM, size=8.5, colorv="#59677A", max_lines=3)
        yy -= gap


def sources(c, meta, p, th, page):
    header_footer(c, meta, page, p["title"], th)
    tech_grid(c, th)
    y = page_title(c, p["title"], p.get("eyebrow", "Sources"), th)
    items = p["items"]
    cols = 2 if len(items) <= 6 else 1
    gap = 5 * MM
    if cols == 2:
        w = (W - 2 * SAFE_X - gap) / 2
        rows = math.ceil(len(items) / 2)
        avail = y - 31 * MM - gap * (rows - 1)
        h = avail / rows
        if h < 37 * MM:
            raise ValueError("FIT_FAIL: source cards too dense")
        for i, source in enumerate(items):
            col = i % 2
            row = i // 2
            x = SAFE_X + col * (w + gap)
            top = y - row * (h + gap)
            yy = top - h
            shadow_card(c, x, yy, w, h, 12, accent=th["accent"] if i == 0 else None)
            pill(c, f"{i+1:02d}", x + 5 * MM, top - 12 * MM, 14 * MM, 7.5 * MM, th)
            draw_text(c, source, x + 5 * MM, top - 21 * MM, w - 10 * MM, size=9.1, max_lines=6, colorv="#344256")
    else:
        for i, source in enumerate(items, 1):
            h = 31 * MM
            yy = y - h
            shadow_card(c, SAFE_X, yy, W - 2 * SAFE_X, h, 11)
            pill(c, f"{i:02d}", SAFE_X + 5 * MM, y - 11 * MM, 14 * MM, 7 * MM, th)
            draw_text(c, source, SAFE_X + 24 * MM, y - 9 * MM, W - 2 * SAFE_X - 30 * MM, size=9.1, max_lines=4, colorv="#344256")
            y = yy - gap
            if y < 30 * MM:
                raise ValueError("FIT_FAIL: sources overflow")


def closing(c, meta, p, th, page):
    c.linearGradient(0, 0, W, H, [color("#F8FAFD"), color(th["soft"])])
    tech_grid(c, th)
    c.setFillColor(color(th["accent"]))
    c.roundRect(SAFE_X, H - 38 * MM, 34 * MM, 8 * MM, 4 * MM, fill=1, stroke=0)
    draw_single_line(c, "REPORT COMPLETE", SAFE_X + 2 * MM, H - 35.2 * MM, 30 * MM, size=8, min_size=7.2, font="LatinB", rtl=False, colorv="#FFFFFF", align="center")
    draw_text(c, p["title"], SAFE_X, H - 64 * MM, W - 2 * SAFE_X, size=28, bold=True, max_lines=2)
    draw_text(c, p["text"], SAFE_X, H - 88 * MM, W - 2 * SAFE_X, size=11, max_lines=6, colorv="#4E5C70")
    y = 40 * MM
    h = 36 * MM
    shadow_card(c, SAFE_X, y, W - 2 * SAFE_X, h, 14, accent=th["accent"])
    draw_single_line(c, "Nima Moheb", SAFE_X + 7 * MM, y + 23 * MM, 70 * MM, size=14, min_size=14, font="LatinB", rtl=False, colorv=th["deep"])
    draw_single_line(c, "Full Stack Developer", SAFE_X + 7 * MM, y + 14 * MM, 70 * MM, size=9, min_size=9, font="Latin", rtl=False, colorv="#5B687A")
    draw_resume_link(c, SAFE_X + 7 * MM, y + 6 * MM, th, label="VIEW RESUME  ↗", size=9.2)
    draw_single_line(c, RESUME_URL.replace("https://", ""), W - SAFE_X - 75 * MM, y + 6 * MM, 68 * MM, size=7.5, min_size=6.7, font="Latin", rtl=False, colorv="#778497", align="right")


RENDERERS = {
    "cover": cover,
    "summary": summary,
    "text": text_page,
    "cards": cards_page,
    "chart_text": chart_text,
    "comparison": comparison,
    "table": table_page,
    "image_text": image_text,
    "timeline": timeline,
    "sources": sources,
    "closing": closing,
}


def scrub(data):
    raw = json.dumps(data, ensure_ascii=False)
    upper = raw.upper()
    found = []
    for token in BANNED:
        if re.search(r"[A-Za-z]", token):
            pat = r"(?<![A-Z])" + re.escape(token.upper()) + r"(?![A-Z])"
            if re.search(pat, upper):
                found.append(token)
        elif token in raw:
            found.append(token)
    if found:
        raise ValueError("PUBLIC_SAFETY_FAIL: banned text: " + ", ".join(found))


def semantic_validate(cfg):
    ids = [p["id"] for p in cfg["pages"]]
    if len(ids) != len(set(ids)):
        raise ValueError("SCHEMA_FAIL: page ids must be unique")
    if cfg["pages"][0]["type"] != "cover":
        raise ValueError("SCHEMA_FAIL: first page must be cover")
    cover_count = sum(p["type"] == "cover" for p in cfg["pages"])
    if cover_count != 1:
        raise ValueError("SCHEMA_FAIL: report must contain exactly one cover")
    for p in cfg["pages"]:
        if p["type"] == "chart_text" and len(p["chart"]["labels"]) != len(p["chart"]["data"]):
            raise ValueError(f"DATA_FAIL: chart page {p['id']} labels/data length mismatch")
        if p["type"] == "table":
            n = len(p["columns"])
            for idx, row in enumerate(p["rows"], 1):
                if len(row) != n:
                    raise ValueError(f"DATA_FAIL: table page {p['id']} row {idx} has {len(row)} cells; expected {n}")


def render_page(meta, p, page_num, out):
    th = THEMES[meta.get("theme", "blue")]
    c = canvas.Canvas(str(out), pagesize=A4, pageCompression=1, invariant=1)
    c.setTitle(meta["title"])
    c.setAuthor(meta.get("author", "Nima Moheb"))
    RENDERERS[p["type"]](c, meta, p, th, page_num) if p["type"] == "closing" else (
        RENDERERS[p["type"]](c, meta, p, th)
        if p["type"] == "cover"
        else RENDERERS[p["type"]](c, meta, p, th, page_num)
    )
    c.showPage()
    c.save()


def sha(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _runtime_contract_hash():
    h = hashlib.sha256()
    for path in [
        Path(__file__),
        Path(__file__).with_name("rtl.py"),
        Path(__file__).with_name("qa.py"),
    ]:
        h.update(path.read_bytes())
    h.update(files("reportkit").joinpath("data/report.schema.json").read_bytes())
    h.update(files("reportkit").joinpath("data/themes.json").read_bytes())
    return h.hexdigest()


def _asset_hash_for_page(p, config_dir):
    if p["type"] != "image_text":
        return None
    path = Path(p["image"]).expanduser()
    if not path.is_absolute():
        path = Path(config_dir) / path
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"ASSET_FAIL: image page {p['id']} requires {path}")
    return sha(path)


def _page_input_fingerprint(p, config_dir):
    payload = {"page": p, "asset_sha256": _asset_hash_for_page(p, config_dir)}
    return _canonical_hash(payload)


def _read_previous_manifest(path):
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and isinstance(obj.get("build"), dict) and isinstance(obj.get("pages"), dict):
            return obj
    except Exception:
        pass
    return None


def _artifact_matches(entry, pages_dir):
    if not entry:
        return False
    path = pages_dir / entry.get("file", "")
    return path.exists() and entry.get("sha256") == sha(path)


def build(config_path, out_pdf, only_ids=None, run_qa=True):
    register_fonts()
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    validate(cfg, SCHEMA)
    semantic_validate(cfg)
    scrub(cfg)

    known_ids = {p["id"] for p in cfg["pages"]}
    only_ids = set(only_ids or [])
    unknown = only_ids - known_ids
    if unknown:
        raise ValueError("SURGERY_FAIL: unknown page ids: " + ", ".join(sorted(unknown)))

    out_pdf = Path(out_pdf).resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pages_dir = out_pdf.parent / "pages"
    pages_dir.mkdir(exist_ok=True)
    manifest_path = out_pdf.parent / "manifest.json"
    previous = _read_previous_manifest(manifest_path)

    runtime_hash = _runtime_contract_hash()
    global_payload = {
        "engine_version": ENGINE_VERSION,
        "runtime_contract_sha256": runtime_hash,
        "meta": cfg["meta"],
        "structure": [{"id": p["id"], "type": p["type"]} for p in cfg["pages"]],
    }
    global_fingerprint = _canonical_hash(global_payload)
    page_inputs = {p["id"]: _page_input_fingerprint(p, config_path.parent) for p in cfg["pages"]}

    render_ids = set(known_ids) if not only_ids else set(only_ids)
    build_mode = "full" if not only_ids else "surgical"
    if only_ids:
        if not previous or previous["build"].get("global_fingerprint") != global_fingerprint:
            render_ids = set(known_ids)
            build_mode = "surgical-invalidated-full"
        else:
            prev_pages = previous["pages"]
            auto_changed = {
                pid
                for pid in known_ids
                if prev_pages.get(pid, {}).get("input_fingerprint") != page_inputs[pid]
                or not _artifact_matches(prev_pages.get(pid), pages_dir)
            }
            if auto_changed - only_ids:
                build_mode = "surgical-expanded"
            render_ids |= auto_changed

    meta = dict(cfg["meta"])
    meta["_page_count"] = len(cfg["pages"])
    meta["_config_dir"] = str(config_path.parent)
    manifest_pages = {}
    for idx, p in enumerate(cfg["pages"], 1):
        pp = pages_dir / f"{idx:03d}-{p['id']}.pdf"
        if p["id"] in render_ids or not pp.exists():
            render_page(meta, p, idx, pp)
        manifest_pages[p["id"]] = {
            "index": idx,
            "file": pp.name,
            "sha256": sha(pp),
            "input_fingerprint": page_inputs[p["id"]],
        }

    writer = PdfWriter()
    for p in cfg["pages"]:
        pp = pages_dir / manifest_pages[p["id"]]["file"]
        reader = PdfReader(str(pp))
        if len(reader.pages) != 1:
            raise RuntimeError(f"BUILD_FAIL: page artifact {pp.name} is not exactly one page")
        writer.add_page(reader.pages[0])
    writer.add_metadata({
        "/Title": cfg["meta"]["title"],
        "/Author": cfg["meta"].get("author", "Nima Moheb"),
        "/Producer": f"Nima Report Engine {ENGINE_VERSION}",
    })
    with out_pdf.open("wb") as f:
        writer.write(f)

    if cfg["meta"].get("branding") in ("normal", "prominent") and _pdf_uri_count(out_pdf, RESUME_URL) < 1:
        raise RuntimeError("LINK_FAIL: resume URL annotation missing from final PDF")

    build_meta = {
        "engine_version": ENGINE_VERSION,
        "mode": build_mode,
        "global_fingerprint": global_fingerprint,
        "runtime_contract_sha256": runtime_hash,
        "final_pdf_sha256": sha(out_pdf),
        "page_count": len(cfg["pages"]),
    }
    manifest_path.write_text(
        json.dumps({"build": build_meta, "pages": manifest_pages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if run_qa:
        qa = preflight_and_render(out_pdf, out_pdf.parent / "qa", expected_pages=len(cfg["pages"]))
        # PDF hash in QA must match the build boundary exactly.
        if qa["pdf_sha256"] != build_meta["final_pdf_sha256"]:
            raise RuntimeError("QA_FAIL: final PDF changed during preflight")

    return manifest_pages
