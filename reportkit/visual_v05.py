from __future__ import annotations

import math
import os
import re
import unicodedata
import json
from pathlib import Path

import fitz
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from . import engine as e

_INSTALLED = False
_ORIG = {}

_STRIP_CODEPOINTS = {
    0xFEFF: None,
    0x200E: None,
    0x200F: None,
    0x061C: None,
    0x00AD: None,
    0x2066: None,
    0x2067: None,
    0x2068: None,
    0x2069: None,
}


def clean_text(value) -> str:
    """Normalize pasted/source text before measurement or drawing.

    ZWNJ (U+200C) is preserved because it is semantically important in Persian.
    Invisible controls that produced visible hairlines/missing glyphs in real reports
    are stripped.
    """
    text = unicodedata.normalize("NFC", str(value or "")).translate(_STRIP_CODEPOINTS)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[\t\u00a0 ]+", " ", line).strip() for line in text.split("\n")).strip()


def _font_file(name: str):
    for base in e._font_dirs():
        if base:
            p = Path(base) / name
            if p.exists():
                return p
    return None


def register_fonts_v05():
    """Use approved/modern sans faces; never silently choose Naskh for Persian."""
    rt_r, rt_b = e._convert_plex_runtime()
    latin_r = e._first_existing(
        _font_file("IBMPlexSans-Regular.ttf"),
        rt_r,
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    latin_b = e._first_existing(
        _font_file("IBMPlexSans-Bold.ttf"),
        rt_b,
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    fa_r = e._first_existing(
        _font_file("Vazirmatn-Regular.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansArabicUI-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    fa_b = e._first_existing(
        _font_file("Vazirmatn-Bold.ttf"),
        _font_file("Vazirmatn-Medium.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansArabic-SemiBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    fa_ui = e._first_existing(
        _font_file("Vazirmatn-Medium.ttf"),
        _font_file("Vazirmatn-Bold.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansArabicUI-Regular.ttf",
        fa_b,
    )
    vazir_ready = bool(
        _font_file("Vazirmatn-Regular.ttf")
        and (_font_file("Vazirmatn-Medium.ttf") or _font_file("Vazirmatn-Bold.ttf"))
    )
    if (
        getattr(e, "_V05_REQUIRE_PERSIAN", False)
        and not vazir_ready
        and os.environ.get("REPORTKIT_ALLOW_PERSIAN_FALLBACK") != "1"
    ):
        raise RuntimeError(
            "FONT_SETUP_FAIL: Persian reports require Vazirmatn. "
            "Run `python scripts/bootstrap_fonts.py` and rebuild."
        )

    missing = [
        n
        for n, v in (
            ("Latin", latin_r),
            ("LatinB", latin_b),
            ("Fa", fa_r),
            ("FaB", fa_b),
            ("FaUI", fa_ui),
        )
        if not v
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


def wrap_v05(text, font, size, width, rtl=False):
    text = clean_text(text)
    if "\n" in text:
        lines = []
        for para in text.split("\n"):
            if not para:
                lines.append("")
            else:
                lines.extend(wrap_v05(para, font, size, width, rtl))
        return lines

    raw = text
    if rtl:
        raw = e.LTR_RE.sub(lambda m: m.group(0).replace(" ", "\u00A0"), raw)
        words = raw.split(" ")
    else:
        words = raw.split()

    if not words:
        return []

    lines = []
    cur = words[0]
    for word in words[1:]:
        cand = cur + " " + word
        if e.txt_width(cand, font, size, rtl) <= width:
            cur = cand
        else:
            if e.txt_width(cur, font, size, rtl) > width:
                raise ValueError(
                    f"FIT_FAIL: unbreakable token exceeds {width/e.MM:.1f}mm: {cur[:120]}"
                )
            lines.append(cur)
            cur = word

    if e.txt_width(cur, font, size, rtl) > width:
        raise ValueError(
            f"FIT_FAIL: unbreakable token exceeds {width/e.MM:.1f}mm: {cur[:120]}"
        )
    lines.append(cur)

    # Widow control for prominent copy: do not strand one short word when a
    # balanced two-line ending is possible.
    if len(lines) >= 2:
        last_words = lines[-1].replace("\u00A0", " ").split()
        prev_words = lines[-2].replace("\u00A0", " ").split()
        if (
            len(last_words) == 1
            and len(prev_words) >= 3
            and e.txt_width(lines[-1], font, size, rtl) < width * 0.34
        ):
            moved = prev_words[-1]
            joiner = "\u00A0" if rtl else " "
            new_prev = joiner.join(prev_words[:-1])
            new_last = joiner.join([moved] + last_words)
            if new_prev and e.txt_width(new_last, font, size, rtl) <= width:
                lines[-2] = new_prev
                lines[-1] = new_last
    return lines


def draw_visual_line_v05(c, text, x, y, width, font, size, rtl, align="left"):
    text = clean_text(text)
    if not rtl:
        c.setFont(font, size)
        if align == "right":
            c.drawRightString(x + width, y, text)
        elif align == "center":
            c.drawCentredString(x + width / 2, y, text)
        else:
            c.drawString(x, y, text)
        return

    runs = e.visual_runs(text)
    pieces = []
    total = 0
    for kind, run in runs:
        # Persian/Arabic digits are LTR for bidi ordering but must use the
        # Persian face when the Latin font lacks those glyphs.
        has_fa_digits = any(
            ("\u06f0" <= ch <= "\u06f9") or ("\u0660" <= ch <= "\u0669")
            for ch in run
        )
        rf = font if has_fa_digits else ("Latin" if kind == "ltr" else font)
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

def draw_single_line_v05(
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
    return _ORIG["draw_single_line"](
        c,
        clean_text(text),
        x,
        y,
        width,
        size=size,
        min_size=min_size,
        font=font,
        rtl=rtl,
        colorv=colorv,
        bold=bold,
        align=align,
    )


def _draw_justified_ltr(c, line, x, y, width, font, size):
    words = line.split()
    if len(words) < 2:
        c.setFont(font, size)
        c.drawString(x, y, line)
        return
    natural = sum(pdfmetrics.stringWidth(w, font, size) for w in words)
    spacing = (width - natural) / (len(words) - 1)
    if spacing < 0 or spacing > size * 1.5:
        c.setFont(font, size)
        c.drawString(x, y, line)
        return
    xx = x
    c.setFont(font, size)
    for i, word in enumerate(words):
        c.drawString(xx, y, word)
        xx += pdfmetrics.stringWidth(word, font, size)
        if i < len(words) - 1:
            xx += spacing


def draw_text_v05(
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
    justify=None,
):
    text = clean_text(text)
    rtl = e.is_fa(text) if rtl is None else rtl
    if font is None:
        font = ("FaB" if bold else "Fa") if rtl else ("LatinB" if bold else "Latin")
    leading = leading or size * (1.55 if rtl else 1.48)
    lines = wrap_v05(text, font, size, width, rtl)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError(
            f"FIT_FAIL: text needs {len(lines)} lines, max {max_lines}: {text[:120]}"
        )
    if justify is None:
        justify = (
            not rtl
            and not bold
            and len(text) >= 78
            and len(lines) >= 2
            and size >= 8.8
        )

    c.setFillColor(e.color(colorv))
    yy = y
    nonempty = [i for i, line in enumerate(lines) if line]
    last_nonempty = nonempty[-1] if nonempty else -1

    for i, line in enumerate(lines):
        if not line:
            yy -= leading
            continue
        if justify and not rtl and i != last_nonempty:
            _draw_justified_ltr(c, line, x, yy, width, font, size)
        else:
            e.draw_visual_line(
                c,
                line,
                x,
                yy,
                width,
                font,
                size,
                rtl,
                align="right" if rtl else "left",
            )
        yy -= leading
    return yy


def _page_rtl(meta, p=None, title=None):
    if p and p.get("direction") == "ltr":
        return False
    if p and p.get("direction") == "rtl":
        return True
    probe = title or (p or {}).get("title") or meta.get("title", "")
    return e.is_fa(probe)


def header_footer_v05(c, meta, page, page_title, th):
    rtl = _page_rtl(meta, title=page_title)
    total = int(meta.get("_page_count", page))
    hy = e.H - 15.2 * e.MM
    hh = 8.6 * e.MM
    e.round_rect(
        c,
        e.SAFE_X,
        hy,
        e.W - 2 * e.SAFE_X,
        hh,
        hh / 2,
        fill="#FFFFFF",
        stroke="#DCE6F3",
        sw=0.45,
    )
    dotx = e.W - e.SAFE_X - 5 * e.MM if rtl else e.SAFE_X + 5 * e.MM
    c.setFillColor(e.color(th["accent2"], 0.22))
    c.circle(dotx, hy + hh / 2, 2.5 * e.MM, fill=1, stroke=0)
    c.setFillColor(e.color(th["accent"]))
    c.circle(dotx, hy + hh / 2, 1.15 * e.MM, fill=1, stroke=0)

    if rtl:
        e.draw_single_line(
            c,
            clean_text(meta["title"]),
            e.W - e.SAFE_X - 80 * e.MM,
            hy + 3.0 * e.MM,
            70 * e.MM,
            size=7.1,
            min_size=6.2,
            font="FaUI",
            rtl=True,
            colorv="#66758A",
            align="right",
        )
        if page_title:
            e.draw_single_line(
                c,
                clean_text(page_title),
                e.SAFE_X + 6 * e.MM,
                hy + 3.0 * e.MM,
                70 * e.MM,
                size=7.4,
                min_size=6.2,
                bold=True,
                rtl=True,
                colorv=th["deep"],
                align="left",
            )
        e.glow_line(
            c,
            e.W - e.SAFE_X - 55 * e.MM,
            hy - 0.8 * e.MM,
            e.W - e.SAFE_X - 10 * e.MM,
            hy - 0.8 * e.MM,
            th,
            0.65,
        )
    else:
        e.draw_single_line(
            c,
            clean_text(meta["title"]).upper(),
            e.SAFE_X + 10 * e.MM,
            hy + 3.1 * e.MM,
            70 * e.MM,
            size=6.9,
            min_size=6.1,
            font="LatinB",
            rtl=False,
            colorv="#66758A",
        )
        if page_title:
            e.draw_single_line(
                c,
                clean_text(page_title),
                e.W - e.SAFE_X - 75 * e.MM,
                hy + 3.0 * e.MM,
                69 * e.MM,
                size=7.5,
                min_size=6.2,
                bold=True,
                colorv=th["deep"],
                align="right",
            )
        e.glow_line(
            c,
            e.SAFE_X + 10 * e.MM,
            hy - 0.8 * e.MM,
            e.SAFE_X + 55 * e.MM,
            hy - 0.8 * e.MM,
            th,
            0.65,
        )

    fy = 9.6 * e.MM
    c.setStrokeColor(e.color("#DCE6F3"))
    c.setLineWidth(0.45)
    c.line(e.SAFE_X, fy + 5.6 * e.MM, e.W - e.SAFE_X, fy + 5.6 * e.MM)
    c.setStrokeColor(e.color(th["accent"], 0.82))
    c.setLineWidth(1.1)

    if rtl:
        c.line(
            e.W - e.SAFE_X - 27 * e.MM,
            fy + 5.6 * e.MM,
            e.W - e.SAFE_X,
            fy + 5.6 * e.MM,
        )
        e.draw_single_line(
            c,
            "نیما محب  //  توسعه‌دهنده فول‌استک",
            e.W - e.SAFE_X - 92 * e.MM,
            fy + 1.5 * e.MM,
            92 * e.MM,
            size=6.8,
            min_size=6.0,
            font="FaUI",
            rtl=True,
            colorv="#59687C",
            align="right",
        )
        px = e.SAFE_X
    else:
        c.line(e.SAFE_X, fy + 5.6 * e.MM, e.SAFE_X + 27 * e.MM, fy + 5.6 * e.MM)
        e.draw_single_line(
            c,
            "Nima Moheb  //  Full Stack Developer",
            e.SAFE_X,
            fy + 1.7 * e.MM,
            86 * e.MM,
            size=6.9,
            min_size=6.5,
            font="LatinB",
            rtl=False,
            colorv="#59687C",
        )
        px = e.W - e.SAFE_X - 30 * e.MM

    pw = 30 * e.MM
    ph = 7.2 * e.MM
    py = fy - 0.2 * e.MM
    e.round_rect(c, px, py, pw, ph, ph / 2, fill=th["deep"])
    c.setFont("LatinB", 6.6)
    c.setFillColor(e.color(th["accent2"]))
    c.drawString(px + 4 * e.MM, py + 2.5 * e.MM, "PAGE")
    c.setFont("LatinB", 8.1)
    c.setFillColor(e.white)
    c.drawRightString(px + pw - 4 * e.MM, py + 2.25 * e.MM, f"{page:02d} / {total:02d}")


def page_title_v05(c, title, eyebrow, th, y=e.H - 39 * e.MM):
    title = clean_text(title)
    eyebrow = clean_text(eyebrow)
    rtl = e.is_fa(title) or e.is_fa(eyebrow)
    marker_y = y + 9.5 * e.MM

    if rtl:
        mx = e.W - e.SAFE_X - 5.5 * e.MM
        c.setFillColor(e.color(th["accent"], 0.12))
        c.roundRect(mx, marker_y, 5.5 * e.MM, 5.5 * e.MM, 2.75 * e.MM, fill=1, stroke=0)
        c.setFillColor(e.color(th["accent"]))
        c.circle(mx + 2.75 * e.MM, marker_y + 2.75 * e.MM, 1.0 * e.MM, fill=1, stroke=0)
        e.draw_single_line(
            c,
            eyebrow,
            e.W - e.SAFE_X - 88 * e.MM,
            y + 10.2 * e.MM,
            80 * e.MM,
            size=7.6,
            min_size=6.5,
            font="FaUI",
            rtl=True,
            colorv=th["accent"],
            align="right",
        )
        e.draw_text(
            c,
            title,
            e.SAFE_X,
            y - 5 * e.MM,
            e.W - 2 * e.SAFE_X,
            size=22.5,
            bold=True,
            rtl=True,
            max_lines=2,
        )
    else:
        c.setFillColor(e.color(th["accent"], 0.12))
        c.roundRect(
            e.SAFE_X, marker_y, 5.5 * e.MM, 5.5 * e.MM, 2.75 * e.MM, fill=1, stroke=0
        )
        c.setFillColor(e.color(th["accent"]))
        c.circle(
            e.SAFE_X + 2.75 * e.MM,
            marker_y + 2.75 * e.MM,
            1.0 * e.MM,
            fill=1,
            stroke=0,
        )
        e.draw_single_line(
            c,
            eyebrow.upper(),
            e.SAFE_X + 8 * e.MM,
            y + 10.2 * e.MM,
            80 * e.MM,
            size=7.4,
            min_size=6.4,
            font="LatinB",
            rtl=False,
            colorv=th["accent"],
        )
        e.draw_text(
            c,
            title,
            e.SAFE_X,
            y - 5 * e.MM,
            e.W - 2 * e.SAFE_X,
            size=22.5,
            bold=True,
            max_lines=2,
        )
    return y - 24 * e.MM


def _soft_panel(c, x, y, w, h, th, alpha=0.70):
    e.round_rect(
        c,
        x,
        y,
        w,
        h,
        15,
        fill=th["soft"],
        stroke="#DCE6F2",
        sw=0.45,
        alpha=alpha,
    )


def summary_v05(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Overview"), th)

    intro_h = 43 * e.MM
    _soft_panel(c, e.SAFE_X, y - intro_h, e.W - 2 * e.SAFE_X, intro_h, th, 0.82)
    e.draw_text(
        c,
        p["intro"],
        e.SAFE_X + 8 * e.MM,
        y - 10 * e.MM,
        e.W - 2 * e.SAFE_X - 16 * e.MM,
        size=11.3,
        leading=17.2,
        max_lines=6,
        justify=True,
        colorv="#344256",
    )

    top = y - intro_h - 7 * e.MM
    bottom = 31 * e.MM
    cards = p["cards"]
    cols = 2 if len(cards) > 1 else 1
    rows = math.ceil(len(cards) / cols)
    gap = 6 * e.MM
    avail = top - bottom - gap * (rows - 1)
    h = avail / rows
    h = max(50 * e.MM, min(h, 66 * e.MM))
    grid_h = rows * h + (rows - 1) * gap
    top = bottom + grid_h
    w = (e.W - 2 * e.SAFE_X - gap * (cols - 1)) / cols

    for i, card in enumerate(cards):
        col = i % cols
        row = i // cols
        x = e.SAFE_X + col * (w + gap)
        yy = top - row * (h + gap) - h
        e.shadow_card(c, x, yy, w, h, 14, accent=th["accent"])
        e.draw_text(
            c,
            card["label"],
            x + 8 * e.MM,
            yy + h - 12 * e.MM,
            w - 16 * e.MM,
            size=10.0,
            bold=True,
            max_lines=2,
            colorv="#55657A",
        )
        e.draw_single_line(
            c,
            card["value"],
            x + 8 * e.MM,
            yy + h * 0.49 - 5 * e.MM,
            w - 16 * e.MM,
            size=34,
            min_size=22,
            bold=True,
            colorv=th["deep"],
            align="center",
        )
        if card.get("note"):
            e.draw_single_line(
                c,
                card["note"],
                x + 8 * e.MM,
                yy + 9 * e.MM,
                w - 16 * e.MM,
                size=8.3,
                min_size=7.0,
                colorv="#7A8798",
                align="center",
            )


def _group_content_height(group, tw):
    return max(1, _ORIG["measure_group"](group, tw))


def text_page_v05(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Report"), th)

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

    gap = 6 * e.MM
    bottom = 30 * e.MM
    tw = e.W - 2 * e.SAFE_X - 18 * e.MM
    available = y - bottom - gap * (len(groups) - 1)
    minimum = [max(42 * e.MM, _group_content_height(g, tw) + 6 * e.MM) for g in groups]
    if sum(minimum) > available:
        raise ValueError(
            f"FIT_FAIL: text groups need {sum(minimum)/e.MM:.1f}mm, "
            f"have {available/e.MM:.1f}mm on {p['id']}"
        )

    extra = (available - sum(minimum)) / max(len(groups), 1)
    heights = [h + extra for h in minimum]
    top = y
    rtl_page = _page_rtl(meta, p)

    for gi, (group, card_h) in enumerate(zip(groups, heights), 1):
        yy = top - card_h
        e.shadow_card(
            c,
            e.SAFE_X,
            yy,
            e.W - 2 * e.SAFE_X,
            card_h,
            15,
            accent=th["accent"],
        )
        idx_x = e.SAFE_X + 7 * e.MM if rtl_page else e.W - e.SAFE_X - 22 * e.MM
        e.pill(c, f"{gi:02d}", idx_x, top - 13 * e.MM, 15 * e.MM, 7.5 * e.MM, th)

        tx = e.SAFE_X + 9 * e.MM
        content_h = _group_content_height(group, tw)
        top_pad = max(
            13 * e.MM,
            min(24 * e.MM, (card_h - content_h) / 2 + 7 * e.MM),
        )
        cy = top - top_pad
        if group["title"]:
            cy = e.draw_text(
                c,
                group["title"],
                tx,
                cy,
                tw,
                size=14.7,
                bold=True,
                max_lines=2,
            )
            cy -= 4 * e.MM

        for block in group["content"]:
            if block["kind"] == "text":
                cy = e.draw_text(
                    c,
                    block["text"],
                    tx,
                    cy,
                    tw,
                    size=10.9,
                    max_lines=12,
                    justify=not e.is_fa(block["text"]),
                )
                cy -= 3.5 * e.MM
            elif block["kind"] == "bullets":
                for item in block["items"]:
                    rtl = e.is_fa(item)
                    bx = tx + 5 * e.MM
                    bw = tw - 7 * e.MM
                    dotx = tx + tw - 1.8 * e.MM if rtl else tx + 1.6 * e.MM
                    c.setFillColor(e.color(th["accent"]))
                    c.circle(dotx, cy + 1.4, 1.35, fill=1, stroke=0)
                    cy = e.draw_text(c, item, bx, cy, bw, size=10.2, max_lines=4)
                    cy -= 2.5 * e.MM

        if cy < yy + 7 * e.MM:
            raise ValueError(f"FIT_FAIL: text group overflow on page {p['id']}")
        top = yy - gap


def cards_page_v05(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Highlights"), th)

    cards = p["cards"]
    gap = 6 * e.MM
    bottom = 31 * e.MM
    cols = 2 if len(cards) >= 4 else 1
    rows = math.ceil(len(cards) / cols)
    w = (e.W - 2 * e.SAFE_X - gap * (cols - 1)) / cols
    avail = y - bottom - gap * (rows - 1)
    h = avail / rows
    h = max(43 * e.MM, min(h, 92 * e.MM))
    grid_h = rows * h + (rows - 1) * gap
    top = bottom + grid_h
    rtl_page = _page_rtl(meta, p)

    for i, card in enumerate(cards):
        col = i % cols
        row = i // cols
        x = e.SAFE_X + col * (w + gap)
        yy = top - row * (h + gap) - h
        e.shadow_card(c, x, yy, w, h, 14, accent=th["accent"])
        badge_x = x + w - 20 * e.MM if rtl_page else x + 6 * e.MM
        e.pill(c, f"{i+1:02d}", badge_x, yy + h - 14 * e.MM, 14 * e.MM, 7 * e.MM, th)

        title_y = yy + h - 26 * e.MM
        e.draw_text(
            c,
            card["title"],
            x + 7 * e.MM,
            title_y,
            w - 14 * e.MM,
            size=11.7,
            bold=True,
            max_lines=2,
        )

        body_lines = e.wrap(
            card["text"],
            "Fa" if e.is_fa(card["text"]) else "Latin",
            9.6,
            w - 14 * e.MM,
            e.is_fa(card["text"]),
        )
        body_h = len(body_lines) * 9.6 * 1.52
        body_top = yy + max(13 * e.MM, (h - 34 * e.MM + body_h) / 2)
        e.draw_text(
            c,
            card["text"],
            x + 7 * e.MM,
            body_top,
            w - 14 * e.MM,
            size=9.6,
            max_lines=7,
            colorv="#536174",
            justify=not e.is_fa(card["text"]),
        )


def comparison_v05(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Comparison"), th)

    items = p["items"]
    rtl_page = _page_rtl(meta, p)
    gap = 5 * e.MM
    bottom = 31 * e.MM
    w = (e.W - 2 * e.SAFE_X - gap * (len(items) - 1)) / len(items)
    h = y - bottom

    for i, item in enumerate(items):
        x = e.SAFE_X + i * (w + gap)
        yy = bottom
        e.shadow_card(c, x, yy, w, h, 15, accent=th["accent"])

        c.setFillColor(e.color(th["soft"], 0.95))
        c.roundRect(
            x + 2 * e.MM,
            yy + h - 45 * e.MM,
            w - 4 * e.MM,
            39 * e.MM,
            10,
            fill=1,
            stroke=0,
        )
        badge_x = x + w - 20 * e.MM if rtl_page else x + 5 * e.MM
        e.pill(c, f"{i+1:02d}", badge_x, yy + h - 15 * e.MM, 14 * e.MM, 7.5 * e.MM, th)
        e.draw_text(
            c,
            item["title"],
            x + 6 * e.MM,
            yy + h - 29 * e.MM,
            w - 12 * e.MM,
            size=11.2,
            bold=True,
            max_lines=2,
        )
        if "value" in item:
            e.draw_single_line(
                c,
                item["value"],
                x + 6 * e.MM,
                yy + h - 60 * e.MM,
                w - 12 * e.MM,
                size=22,
                min_size=15,
                bold=True,
                colorv=th["deep"],
                align="right" if rtl_page else "left",
            )

        c.setStrokeColor(e.color(th["accent"], 0.22))
        c.setLineWidth(0.7)
        c.line(
            x + 6 * e.MM,
            yy + h - 68 * e.MM,
            x + w - 6 * e.MM,
            yy + h - 68 * e.MM,
        )

        by = yy + h - 82 * e.MM
        for bullet in item["bullets"]:
            rtl = e.is_fa(bullet)
            dotx = x + w - 7.2 * e.MM if rtl else x + 7.2 * e.MM
            c.setFillColor(e.color(th["accent"]))
            c.circle(dotx, by + 1.5, 1.25, fill=1, stroke=0)
            bx = x + 6 * e.MM if rtl else x + 12 * e.MM
            bw = w - 18 * e.MM
            by = e.draw_text(
                c,
                bullet,
                bx,
                by,
                bw,
                size=9.1,
                max_lines=4,
                colorv="#46566B",
                justify=not rtl,
            )
            by -= 5 * e.MM

        if by < yy + 9 * e.MM:
            raise ValueError(f"FIT_FAIL: comparison card overflow on page {p['id']}")


def timeline_v05(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Timeline"), th)

    items = p["items"]
    rtl = _page_rtl(meta, p)
    bottom = 33 * e.MM
    gap = 6 * e.MM

    # Five- and six-step processes become a two-column process grid around a
    # central timeline. This gives each step enough text height instead of
    # squeezing six tiny cards down one edge.
    if len(items) >= 5:
        rows = math.ceil(len(items) / 2)
        col_gap = 14 * e.MM
        w = (e.W - 2 * e.SAFE_X - col_gap) / 2
        h = (y - bottom - gap * (rows - 1)) / rows
        if h < 43 * e.MM:
            raise ValueError(f"FIT_FAIL: timeline cards too dense on {p['id']}")

        cx = e.W / 2
        c.setStrokeColor(e.color(th["accent"], 0.22))
        c.setLineWidth(1.4)
        c.line(cx, bottom, cx, y - 4 * e.MM)

        for i, item in enumerate(items):
            row = i // 2
            slot = i % 2
            visual_col = (1 - slot) if rtl else slot
            x = e.SAFE_X + visual_col * (w + col_gap)
            top = y - row * (h + gap)
            yy = top - h
            node_y = yy + h / 2

            c.setFillColor(e.color(th["accent2"], 0.24))
            c.circle(cx, node_y, 4.1 * e.MM, fill=1, stroke=0)
            c.setFillColor(e.color(th["accent"]))
            c.circle(cx, node_y, 1.8 * e.MM, fill=1, stroke=0)
            edge = x if visual_col == 1 else x + w
            c.setStrokeColor(e.color(th["accent"], 0.24))
            c.setLineWidth(0.9)
            c.line(cx, node_y, edge, node_y)

            e.shadow_card(c, x, yy, w, h, 12, accent=th["accent"])
            badge_x = x + w - 19 * e.MM if rtl else x + 6 * e.MM
            e.pill(c, f"{i+1:02d}", badge_x, top - 12 * e.MM, 13 * e.MM, 7 * e.MM, th)
            e.draw_text(
                c, item["title"], x + 7 * e.MM, top - 24 * e.MM,
                w - 14 * e.MM, size=10.6, bold=True, max_lines=2
            )
            e.draw_text(
                c, item["text"], x + 7 * e.MM, top - 38 * e.MM,
                w - 14 * e.MM, size=8.6, colorv="#59677A",
                max_lines=4, justify=not e.is_fa(item["text"])
            )
        return

    line_x = e.W - e.SAFE_X - 10 * e.MM if rtl else e.SAFE_X + 10 * e.MM
    h = (y - bottom - gap * (len(items) - 1)) / len(items)
    h = min(47 * e.MM, max(36 * e.MM, h))
    c.setStrokeColor(e.color(th["accent"], 0.30))
    c.setLineWidth(2)
    c.line(line_x, bottom, line_x, y - 4 * e.MM)

    top = y
    for i, item in enumerate(items):
        yy = top - h
        node_y = yy + h / 2
        c.setFillColor(e.color(th["accent2"], 0.28))
        c.circle(line_x, node_y, 4.6 * e.MM, fill=1, stroke=0)
        c.setFillColor(e.color(th["accent"]))
        c.circle(line_x, node_y, 2 * e.MM, fill=1, stroke=0)

        if rtl:
            x = e.SAFE_X
            cw = line_x - e.SAFE_X - 9 * e.MM
        else:
            x = line_x + 9 * e.MM
            cw = e.W - e.SAFE_X - x

        e.shadow_card(c, x, yy, cw, h, 12, accent=th["accent"])
        badge_x = x + cw - 19 * e.MM if rtl else x + 6 * e.MM
        e.pill(c, f"{i+1:02d}", badge_x, top - 12 * e.MM, 13 * e.MM, 7 * e.MM, th)
        e.draw_text(
            c, item["title"], x + 7 * e.MM, top - 24 * e.MM,
            cw - 14 * e.MM, size=10.7, bold=True, max_lines=2
        )
        e.draw_text(
            c, item["text"], x + 7 * e.MM, top - 38 * e.MM,
            cw - 14 * e.MM, size=8.8, colorv="#59677A",
            max_lines=4, justify=not e.is_fa(item["text"])
        )
        top = yy - gap

def cover_v05(c, meta, p, th):
    meta2 = dict(meta)
    p2 = dict(p)
    for key in ("title", "subtitle", "author", "date", "recipient"):
        if key in meta2:
            meta2[key] = clean_text(meta2[key])
    for key in ("title", "subtitle", "eyebrow"):
        if key in p2:
            p2[key] = clean_text(p2[key])
    return _ORIG["cover"](c, meta2, p2, th)


def _contains_persian(obj):
    if isinstance(obj, str):
        return e.is_fa(clean_text(obj))
    if isinstance(obj, dict):
        return any(_contains_persian(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_persian(v) for v in obj)
    return False


def _density_check(pdf_path, cfg):
    if cfg.get("meta", {}).get("mode", "report") != "report":
        return

    doc = fitz.open(pdf_path)
    rules = {
        "summary": 0.66,
        "text": 0.62,
        "cards": 0.62,
        "comparison": 0.60,
        "timeline": 0.66,
        "chart_text": 0.66,
    }
    failures = []

    for idx, page_cfg in enumerate(cfg.get("pages", [])):
        typ = page_cfg.get("type")
        if typ not in rules:
            continue

        page = doc[idx]
        h = page.rect.height
        blocks = []
        for block in page.get_text("blocks"):
            if len(block) < 5 or not str(block[4]).strip():
                continue
            y0, y1 = float(block[1]), float(block[3])
            if y1 < 92 or y0 > h - 72:
                continue
            blocks.append((y0, y1, str(block[4])))

        if not blocks:
            failures.append((page_cfg.get("id", idx + 1), typ, 0))
            continue

        max_y = max(y1 for _, y1, _ in blocks)
        if max_y / h < rules[typ]:
            failures.append((page_cfg.get("id", idx + 1), typ, max_y / h))

    if failures:
        detail = ", ".join(
            f"{pid}:{typ}={ratio:.0%}" for pid, typ, ratio in failures
        )
        raise RuntimeError(
            "QA_DENSITY_FAIL: meaningful content ends too high on page(s): "
            + detail
            + ". Use a denser archetype/layout or add/split meaningful content; "
            "do not ship a mostly empty page."
        )


def _variety_check(cfg):
    if cfg.get("meta", {}).get("mode", "report") != "report":
        return
    interior = [
        p.get("type")
        for p in cfg.get("pages", [])
        if p.get("type") not in ("cover", "closing")
    ]
    if len(interior) < 6:
        return

    run_type = None
    run = 0
    for typ in interior:
        if typ == run_type:
            run += 1
        else:
            run_type = typ
            run = 1
        if typ in ("cards", "text") and run > 2:
            raise RuntimeError(
                f"QA_VARIETY_FAIL: {run} consecutive {typ} pages. "
                "Recompose the report with different approved archetypes/layouts "
                "instead of repeating one template."
            )

    for typ in ("cards", "text"):
        count = interior.count(typ)
        if count / len(interior) > 0.55:
            raise RuntimeError(
                f"QA_VARIETY_FAIL: {typ} pages are {count}/{len(interior)} of the report. "
                "Use a more varied content architecture."
            )


def build_v05(config_path, out_pdf, only_ids=None, run_qa=True):
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    _variety_check(cfg)
    e._V05_REQUIRE_PERSIAN = _contains_persian(cfg)
    try:
        result = _ORIG["build"](
            config_path, out_pdf, only_ids=only_ids, run_qa=run_qa
        )
        if run_qa:
            _density_check(out_pdf, cfg)
        return result
    finally:
        e._V05_REQUIRE_PERSIAN = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    for name in (
        "draw_visual_line",
        "draw_single_line",
        "draw_text",
        "cover",
        "measure_group",
    ):
        key = "measure_group" if name == "measure_group" else name
        attr = "_measure_group" if name == "measure_group" else name
        _ORIG[key] = getattr(e, attr)

    _ORIG["register_fonts"] = e.register_fonts
    _ORIG["build"] = e.build

    e.ENGINE_VERSION = "0.5.0"
    e.register_fonts = register_fonts_v05
    e.wrap = wrap_v05
    e.draw_visual_line = draw_visual_line_v05
    e.draw_single_line = draw_single_line_v05
    e.draw_text = draw_text_v05
    e.header_footer = header_footer_v05
    e.page_title = page_title_v05
    e.summary = summary_v05
    e.text_page = text_page_v05
    e.cards_page = cards_page_v05
    e.timeline = timeline_v05
    e.comparison = comparison_v05
    e.cover = cover_v05
    e.build = build_v05

    e.RENDERERS["cover"] = cover_v05
    e.RENDERERS["summary"] = summary_v05
    e.RENDERERS["text"] = text_page_v05
    e.RENDERERS["cards"] = cards_page_v05
    e.RENDERERS["comparison"] = comparison_v05
    e.RENDERERS["timeline"] = timeline_v05
