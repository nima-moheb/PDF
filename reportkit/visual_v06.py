from __future__ import annotations

import unicodedata
from pathlib import Path

from reportlab.pdfbase import pdfmetrics

from . import engine as e
from .visual_v05 import clean_text

_INSTALLED = False
_ORIG = {}

# Controls may be semantically useful before bidi shaping, but they must never be
# sent to ReportLab as visible glyphs. Real Chromium/Acrobat PDF viewers exposed
# U+200C as a thin horizontal mark in some embedded Persian fonts.
_VISUAL_CONTROL_CHARS = {"\u200c", "\u200d", "\u200e", "\u200f", "\u061c", "\ufeff"}


def _visible_run(run: str) -> str:
    return "".join(
        ch
        for ch in run
        if ch not in _VISUAL_CONTROL_CHARS and unicodedata.category(ch) != "Cf"
    )


def _fa_digits(value) -> str:
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _run_font(kind: str, run: str, font: str) -> str:
    has_fa_digits = any(("\u06f0" <= ch <= "\u06f9") or ("\u0660" <= ch <= "\u0669") for ch in run)
    return font if has_fa_digits else ("Latin" if kind == "ltr" else font)


def txt_width_v06(text, font, size, rtl=False):
    text = clean_text(text)
    if not rtl:
        return pdfmetrics.stringWidth(text, font, size)
    total = 0
    for kind, run in e.visual_runs(text):
        run = _visible_run(run)
        if not run:
            continue
        rf = _run_font(kind, run, font)
        total += pdfmetrics.stringWidth(run, rf, size)
    return total


def draw_visual_line_v06(c, text, x, y, width, font, size, rtl, align="left"):
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

    pieces = []
    total = 0
    for kind, run in e.visual_runs(text):
        run = _visible_run(run)
        if not run:
            continue
        rf = _run_font(kind, run, font)
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


def header_footer_v06(c, meta, page, page_title, th):
    rtl = e.is_fa(page_title or meta.get("title", ""))
    total = int(meta.get("_page_count", page))
    hy = e.H - 15.2 * e.MM
    hh = 8.6 * e.MM
    e.round_rect(c, e.SAFE_X, hy, e.W - 2 * e.SAFE_X, hh, hh / 2,
                 fill="#FFFFFF", stroke="#DCE6F3", sw=0.45)
    dotx = e.W - e.SAFE_X - 5 * e.MM if rtl else e.SAFE_X + 5 * e.MM
    c.setFillColor(e.color(th["accent2"], 0.22)); c.circle(dotx, hy + hh/2, 2.5*e.MM, fill=1, stroke=0)
    c.setFillColor(e.color(th["accent"])); c.circle(dotx, hy + hh/2, 1.15*e.MM, fill=1, stroke=0)

    if rtl:
        e.draw_single_line(c, meta["title"], e.W-e.SAFE_X-80*e.MM, hy+3*e.MM, 70*e.MM,
                           size=7.1, min_size=6.2, font="FaUI", rtl=True,
                           colorv="#66758A", align="right")
        if page_title:
            e.draw_single_line(c, page_title, e.SAFE_X+6*e.MM, hy+3*e.MM, 70*e.MM,
                               size=7.4, min_size=6.2, font="FaUI", rtl=True,
                               colorv=th["deep"], align="left")
        e.glow_line(c, e.W-e.SAFE_X-55*e.MM, hy-.8*e.MM,
                    e.W-e.SAFE_X-10*e.MM, hy-.8*e.MM, th, .65)
    else:
        _ORIG["header_footer"](c, meta, page, page_title, th)
        return

    fy = 9.6 * e.MM
    c.setStrokeColor(e.color("#DCE6F3")); c.setLineWidth(.45)
    c.line(e.SAFE_X, fy+5.6*e.MM, e.W-e.SAFE_X, fy+5.6*e.MM)
    c.setStrokeColor(e.color(th["accent"], .82)); c.setLineWidth(1.1)
    c.line(e.W-e.SAFE_X-27*e.MM, fy+5.6*e.MM, e.W-e.SAFE_X, fy+5.6*e.MM)
    e.draw_single_line(c, "نیما محب  //  توسعه‌دهنده فول‌استک",
                       e.W-e.SAFE_X-92*e.MM, fy+1.5*e.MM, 92*e.MM,
                       size=6.8, min_size=6, font="FaUI", rtl=True,
                       colorv="#59687C", align="right")

    pw = 33 * e.MM; ph = 7.6 * e.MM; px = e.SAFE_X; py = fy-.2*e.MM
    e.round_rect(c, px, py, pw, ph, ph/2, fill=th["deep"])
    e.draw_single_line(c, f"صفحه {_fa_digits(page)} از {_fa_digits(total)}",
                       px+3*e.MM, py+2.15*e.MM, pw-6*e.MM,
                       size=7.1, min_size=6.2, font="FaUI", rtl=True,
                       colorv="#FFFFFF", align="center")


def _localized_cover_single_line(c, text, x, y, width, *args, **kwargs):
    mapping = {
        "NIMA REPORT ENGINE": "گزارش نیما",
        "STRUCTURED / FINAL": "ساختاریافته / نهایی",
        "REPORT": "گزارش",
        "DATA / INSIGHT / IMPACT": "داده / تحلیل / نتیجه",
        "REPORT COMPLETE": "پایان گزارش",
        "PORTFOLIO / RESUME": "رزومه / نمونه‌کار",
    }
    mapped = mapping.get(str(text))
    if mapped is None:
        return _ORIG["draw_single_line"](c, text, x, y, width, *args, **kwargs)

    kw = dict(kwargs)
    kw["font"] = "FaUI"
    kw["rtl"] = True
    # Original decorative calls already choose suitable centering/right alignment.
    return _ORIG["draw_single_line"](c, mapped, x, y, width, *args, **kw)


def cover_v06(c, meta, p, th):
    rtl = p.get("direction") == "rtl" or (
        p.get("direction") != "ltr" and e.is_fa(p.get("title", meta.get("title", "")))
    )
    if not rtl:
        return _ORIG["cover"](c, meta, p, th)

    # All five v0.4 cover templates are preserved. Only decorative English chrome
    # is localized; intentional English in report content (e.g. CRM) is untouched.
    previous = e.draw_single_line
    e.draw_single_line = _localized_cover_single_line
    try:
        return _ORIG["cover"](c, meta, p, th)
    finally:
        e.draw_single_line = previous


def _metric_value(c, value, cx, cy, radius, th, rtl):
    # Outer halo + clean core + small orbit nodes. It makes the metric a visual
    # anchor instead of a lonely number floating inside a large rectangle.
    c.setFillColor(e.color(th["accent"], .08)); c.circle(cx, cy, radius*1.15, fill=1, stroke=0)
    c.setStrokeColor(e.color(th["accent"], .25)); c.setLineWidth(1.1)
    c.circle(cx, cy, radius, fill=0, stroke=1)
    c.setFillColor(e.color("#FFFFFF")); c.circle(cx, cy, radius*.83, fill=1, stroke=0)
    for ang in (35, 155, 275):
        import math
        a = math.radians(ang)
        nx = cx + math.cos(a)*radius; ny = cy + math.sin(a)*radius
        c.setFillColor(e.color(th["accent2"], .55)); c.circle(nx, ny, 1.25*e.MM, fill=1, stroke=0)
    e.draw_single_line(c, value, cx-radius*1.20, cy-5.2*e.MM, radius*2.40,
                       size=38, min_size=21, bold=True,
                       colorv=th["deep"], align="center", rtl=rtl)


def _index_badge(c, text, x, y, w, h, th, rtl=False):
    e.round_rect(c, x, y, w, h, h/2, fill=th["soft"], stroke=None, alpha=.98)
    e.draw_single_line(c, _fa_digits(text) if rtl else str(text),
                       x+1.5*e.MM, y+h/2-2.1, w-3*e.MM,
                       size=7.2, min_size=6.2,
                       font="FaUI" if rtl else "LatinB", rtl=rtl,
                       colorv=th["accent"], align="center")


def summary_v06(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Overview"), th)
    rtl_page = e.is_fa(p["title"])

    intro_h = 42 * e.MM
    e.round_rect(c, e.SAFE_X, y-intro_h, e.W-2*e.SAFE_X, intro_h, 16,
                 fill=th["soft"], stroke="#DCE6F2", sw=.45, alpha=.78)
    # Vertical accent is mirrored instead of relying on another horizontal rail.
    ax = e.W-e.SAFE_X-2.2*e.MM if rtl_page else e.SAFE_X+.7*e.MM
    c.setFillColor(e.color(th["accent"])); c.roundRect(ax, y-intro_h+5*e.MM, 1.5*e.MM, intro_h-10*e.MM, .75*e.MM, fill=1, stroke=0)
    e.draw_text(c, p["intro"], e.SAFE_X+9*e.MM, y-10*e.MM,
                e.W-2*e.SAFE_X-18*e.MM, size=11.4, leading=17.5,
                max_lines=6, justify=not rtl_page, colorv="#344256")

    cards = p["cards"]
    cols = 2 if len(cards) > 1 else 1
    rows = (len(cards)+cols-1)//cols
    gap = 6*e.MM; bottom = 31*e.MM; top = y-intro_h-7*e.MM
    h = (top-bottom-gap*(rows-1))/rows
    w = (e.W-2*e.SAFE_X-gap*(cols-1))/cols

    for i, card in enumerate(cards):
        col=i%cols; row=i//cols
        x=e.SAFE_X+col*(w+gap); yy=top-row*(h+gap)-h
        e.shadow_card(c, x, yy, w, h, 16)
        cx=x+w/2; cy=yy+h*.58
        _metric_value(c, str(card["value"]), cx, cy, min(18*e.MM, h*.23), th, e.is_fa(str(card["value"])))
        e.draw_single_line(c, card["label"], x+7*e.MM, yy+16*e.MM, w-14*e.MM,
                           size=10.3, min_size=8.8, bold=True,
                           colorv="#405066", align="center", rtl=e.is_fa(card["label"]))
        if card.get("note"):
            e.draw_single_line(c, card["note"], x+7*e.MM, yy+7.5*e.MM, w-14*e.MM,
                               size=8.3, min_size=7.0, colorv="#7A8798",
                               align="center", rtl=e.is_fa(card["note"]))


def comparison_v06(c, meta, p, th, page):
    e.header_footer(c, meta, page, p["title"], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p["title"], p.get("eyebrow", "Comparison"), th)
    items=p["items"]; rtl_page=e.is_fa(p["title"])
    gap=5*e.MM; bottom=31*e.MM
    w=(e.W-2*e.SAFE_X-gap*(len(items)-1))/len(items); h=y-bottom

    for i,item in enumerate(items):
        x=e.SAFE_X+i*(w+gap); yy=bottom
        e.shadow_card(c,x,yy,w,h,16)
        c.setFillColor(e.color(th["soft"],.92)); c.roundRect(x+2*e.MM, yy+h-59*e.MM, w-4*e.MM, 53*e.MM, 12, fill=1, stroke=0)

        index=_fa_digits(f"{i+1:02d}") if rtl_page else f"{i+1:02d}"
        # Large index watermark + metric/value medallion.
        e.draw_single_line(c,index,x+7*e.MM,yy+h-20*e.MM,w-14*e.MM,
                           size=27,min_size=23,bold=True,colorv=th["accent"],
                           align="right" if rtl_page else "left",rtl=rtl_page)
        c.setFillColor(e.color(th["accent"],.09)); c.circle(x+w/2,yy+h-80*e.MM,15*e.MM,fill=1,stroke=0)
        c.setStrokeColor(e.color(th["accent"],.30)); c.setLineWidth(1.0); c.circle(x+w/2,yy+h-80*e.MM,12.5*e.MM,fill=0,stroke=1)
        if "value" in item:
            e.draw_single_line(c,item["value"],x+w/2-12*e.MM,yy+h-84*e.MM,24*e.MM,
                               size=16.5,min_size=12,bold=True,colorv=th["deep"],
                               align="center",rtl=e.is_fa(str(item["value"])))
        e.draw_text(c,item["title"],x+6*e.MM,yy+h-48*e.MM,w-12*e.MM,
                    size=11.2,bold=True,max_lines=2)

        c.setStrokeColor(e.color(th["accent"],.18)); c.setLineWidth(.7)
        c.line(x+7*e.MM,yy+h-102*e.MM,x+w-7*e.MM,yy+h-102*e.MM)
        bullets=item["bullets"]
        # Distribute the bullets through the remaining body instead of packing them at the top.
        body_top=yy+h-116*e.MM; body_bottom=yy+14*e.MM
        slot=(body_top-body_bottom)/max(len(bullets),1)
        for j,bullet in enumerate(bullets):
            by=body_top-j*slot
            rtl=e.is_fa(bullet)
            dotx=x+w-8*e.MM if rtl else x+8*e.MM
            c.setFillColor(e.color(th["accent"])); c.circle(dotx,by+1.3,1.35,fill=1,stroke=0)
            bx=x+7*e.MM if rtl else x+13*e.MM
            e.draw_text(c,bullet,bx,by,w-20*e.MM,size=9.0,max_lines=4,
                        colorv="#46566B",justify=not rtl)


def timeline_v06(c, meta, p, th, page):
    rtl = e.is_fa(p.get("title", ""))
    if not rtl:
        return _ORIG["timeline"](c, meta, p, th, page)

    previous = e.pill
    def rtl_pill(c2, text, x, y, w, h, th2, dark=False):
        # Timeline indices are chrome, so use Persian digits in RTL reports.
        return _index_badge(c2, str(text), x, y, w, h, th2, rtl=True)
    e.pill = rtl_pill
    try:
        return _ORIG["timeline"](c, meta, p, th, page)
    finally:
        e.pill = previous


def closing_v06(c, meta, p, th, page):
    # Use v0.4/v0.5 closing, but localize decorative English chrome for Persian.
    rtl = e.is_fa(p.get("title", "")) or e.is_fa(p.get("text", ""))
    if not rtl:
        return _ORIG["closing"](c, meta, p, th, page)
    previous=e.draw_single_line
    e.draw_single_line=_localized_cover_single_line
    try:
        return _ORIG["closing"](c, meta, p, th, page)
    finally:
        e.draw_single_line=previous


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED=True

    for name in ("txt_width","draw_visual_line","draw_single_line","cover","summary","comparison","header_footer","timeline","closing"):
        _ORIG[name]=getattr(e,name)

    e.ENGINE_VERSION="0.6.0"
    e.txt_width=txt_width_v06
    e.draw_visual_line=draw_visual_line_v06
    e.header_footer=header_footer_v06
    e.cover=cover_v06
    e.summary=summary_v06
    e.comparison=comparison_v06
    e.timeline=timeline_v06
    e.closing=closing_v06
    e.RENDERERS["cover"]=cover_v06
    e.RENDERERS["summary"]=summary_v06
    e.RENDERERS["comparison"]=comparison_v06
    e.RENDERERS["timeline"]=timeline_v06
    e.RENDERERS["closing"]=closing_v06
