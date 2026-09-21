from __future__ import annotations
import hashlib, json, math, os, re, sys
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
from jsonschema import validate
from .rtl import visual_rtl, visual_runs

W, H = A4
MM = 72/25.4
SAFE_X = 16*MM
TOP = H-16*MM
BOTTOM = 15*MM

BANNED = [
    "TODO", "DRAFT", "INTERNAL NOTE", "MANAGER NOTE", "CEO NOTE", "DEBUG", "PLACEHOLDER", "FIX LATER",
    "یادداشت داخلی", "یادداشت مدیر", "بعداً اصلاح", "پیش نویس", "پیش‌نویس"
]

ROOT = Path(__file__).resolve().parents[1]
THEMES = json.loads((ROOT/"themes/themes.json").read_text())
SCHEMA = json.loads((ROOT/"schemas/report.schema.json").read_text())

FONT_DIR = ROOT/".runtime-fonts"
FONT_DIR.mkdir(exist_ok=True)


def _first_existing(*paths):
    for p in paths:
        p=Path(p)
        if p.exists(): return p
    return None


def _convert_plex_runtime():
    """Runtime-only fallback for this ChatGPT environment; never committed as an asset."""
    regular = Path('/opt/pyvenv/lib/python3.13/site-packages/gradio/templates/frontend/static/fonts/IBMPlexSans/IBMPlexSans-Regular.woff2')
    bold = Path('/opt/pyvenv/lib/python3.13/site-packages/gradio/templates/frontend/static/fonts/IBMPlexSans/IBMPlexSans-Bold.woff2')
    out_r = FONT_DIR/'IBMPlexSans-Regular.ttf'; out_b=FONT_DIR/'IBMPlexSans-Bold.ttf'
    if regular.exists() and not out_r.exists():
        from fontTools.ttLib import TTFont as FT
        f=FT(str(regular)); f.flavor=None; f.save(str(out_r))
    if bold.exists() and not out_b.exists():
        from fontTools.ttLib import TTFont as FT
        f=FT(str(bold)); f.flavor=None; f.save(str(out_b))
    return out_r, out_b


def register_fonts():
    assets=ROOT/'assets/fonts'
    rt_r,rt_b=_convert_plex_runtime()
    latin_r=_first_existing(
        assets/'IBMPlexSans-Regular.ttf', rt_r,
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    latin_b=_first_existing(
        assets/'IBMPlexSans-Bold.ttf', rt_b,
        '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    fa_r=_first_existing(
        assets/'Vazirmatn-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    fa_b=_first_existing(
        assets/'Vazirmatn-Bold.ttf', assets/'Vazirmatn-Medium.ttf',
        '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    fa_ui=_first_existing(
        assets/'Vazirmatn-Medium.ttf', assets/'Vazirmatn-Bold.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Medium.ttf', fa_b)
    missing=[n for n,v in [('Latin',latin_r),('LatinB',latin_b),('Fa',fa_r),('FaB',fa_b),('FaUI',fa_ui)] if not v]
    if missing: raise RuntimeError('FONT_SETUP_FAIL: '+', '.join(missing))
    pdfmetrics.registerFont(TTFont('Latin', str(latin_r)))
    pdfmetrics.registerFont(TTFont('LatinB', str(latin_b)))
    pdfmetrics.registerFont(TTFont('Fa', str(fa_r)))
    pdfmetrics.registerFont(TTFont('FaB', str(fa_b)))
    pdfmetrics.registerFont(TTFont('FaUI', str(fa_ui)))


def is_fa(text):
    return bool(re.search(r'[\u0600-\u06FF]', text or ''))


def color(hexv, alpha=1):
    c=HexColor(hexv); return Color(c.red,c.green,c.blue,alpha=alpha)


def txt_width(text,font,size,rtl=False):
    if rtl:
        total=0
        for kind,run in visual_runs(text):
            rf = 'Latin' if kind=='ltr' else font
            total += pdfmetrics.stringWidth(run,rf,size)
        return total
    return pdfmetrics.stringWidth(text,font,size)


def wrap(text, font, size, width, rtl=False):
    raw=str(text)
    if rtl:
        from .rtl import LTR_RE
        raw=LTR_RE.sub(lambda m: m.group(0).replace(' ', '\u00A0'), raw)
        words=raw.split(' ')
    else:
        words=raw.split()
    if not words: return []
    lines=[]; cur=words[0]
    for w in words[1:]:
        cand=cur+' '+w
        if txt_width(cand,font,size,rtl) <= width:
            cur=cand
        else:
            lines.append(cur); cur=w
    lines.append(cur)
    return lines


def draw_text(c, text, x, y, width, size=11, font=None, leading=None, rtl=None, colorv='#172033', max_lines=None, bold=False):
    rtl = is_fa(text) if rtl is None else rtl
    if font is None:
        font = ('FaB' if bold else 'Fa') if rtl else ('LatinB' if bold else 'Latin')
    leading = leading or size*1.52
    lines = wrap(text,font,size,width,rtl)
    if max_lines is not None and len(lines)>max_lines:
        raise ValueError(f'FIT_FAIL: text needs {len(lines)} lines, max {max_lines}: {text[:80]}')
    c.setFillColor(color(colorv)); c.setFont(font,size)
    yy=y
    for line in lines:
        if rtl:
            runs=visual_runs(line)
            total=0
            widths=[]
            for kind,run in runs:
                rf='Latin' if kind=='ltr' else font
                rw=pdfmetrics.stringWidth(run,rf,size); widths.append((kind,run,rf,rw)); total+=rw
            xx=x+width-total
            for kind,run,rf,rw in widths:
                c.setFont(rf,size); c.drawString(xx,yy,run); xx+=rw
        else:
            c.setFont(font,size); c.drawString(x,yy,line)
        yy-=leading
    return yy


def round_rect(c,x,y,w,h,r=10,fill='#FFFFFF',stroke=None,sw=0.5,alpha=1):
    c.saveState(); c.setFillColor(color(fill,alpha));
    if stroke: c.setStrokeColor(color(stroke)); c.setLineWidth(sw)
    else: c.setStrokeColor(color(fill,0))
    c.roundRect(x,y,w,h,r,fill=1,stroke=1 if stroke else 0); c.restoreState()


def shadow_card(c,x,y,w,h,r=10,fill='#FFFFFF',accent=None):
    round_rect(c,x+2,y-2,w,h,r,fill='#0A1930',alpha=.07)
    round_rect(c,x,y,w,h,r,fill=fill,stroke='#DDE5F1',sw=.45)
    if accent:
        c.setFillColor(color(accent)); c.roundRect(x,y,w,3,r/2,fill=1,stroke=0)


def glow_line(c,x1,y1,x2,y2,th,width=1.0):
    c.saveState()
    c.setStrokeColor(color(th['accent2'],.20)); c.setLineWidth(width*3.2); c.line(x1,y1,x2,y2)
    c.setStrokeColor(color(th['accent'],.72)); c.setLineWidth(width); c.line(x1,y1,x2,y2)
    c.restoreState()


def pill(c,text,x,y,w,h,th,dark=False):
    fill='#FFFFFF' if dark else th['soft']; fg=th['deep'] if dark else th['accent']
    round_rect(c,x,y,w,h,h/2,fill=fill,stroke=None,alpha=.95 if dark else 1)
    c.setFillColor(color(fg)); c.setFont('LatinB',7.3); c.drawCentredString(x+w/2,y+h/2-2.2,text.upper())


def _measure_block(block, width):
    kind=block.get('kind','text')
    if kind=='heading':
        rtl=is_fa(block.get('text','')); return len(wrap(block.get('text',''),'FaB' if rtl else 'LatinB',14.7,width,rtl))*14.7*1.52 + 4*MM
    if kind=='text':
        rtl=is_fa(block.get('text','')); return len(wrap(block.get('text',''),'Fa' if rtl else 'Latin',10.9,width,rtl))*10.9*1.52 + 3.5*MM
    if kind=='bullets':
        total=0
        for item in block.get('items',[]):
            rtl=is_fa(item); total += len(wrap(item,'Fa' if rtl else 'Latin',10.2,width-7*MM,rtl))*10.2*1.52 + 2.5*MM
        return total
    return 0


def _measure_group(g,width):
    h=12*MM
    if g.get('title'):
        rtl=is_fa(g['title']); h += len(wrap(g['title'],'FaB' if rtl else 'LatinB',14.7,width,rtl))*14.7*1.52 + 4*MM
    for b in g.get('content',[]): h += _measure_block(b,width)
    return h+4*MM


def header_footer(c, meta, page, page_title, th, footer_override=None):
    total=int(meta.get('_page_count',page))
    # Header: compact digital navigation rail, not a corporate rule.
    hy=H-15.2*MM; hh=8.6*MM
    round_rect(c,SAFE_X,hy,W-2*SAFE_X,hh,hh/2,fill='#FFFFFF',stroke='#DCE6F3',sw=.45)
    c.setFillColor(color(th['accent2'],.25)); c.circle(SAFE_X+5*MM,hy+hh/2,2.5*MM,fill=1,stroke=0)
    c.setFillColor(color(th['accent'])); c.circle(SAFE_X+5*MM,hy+hh/2,1.15*MM,fill=1,stroke=0)
    c.setFont('LatinB',6.9); c.setFillColor(color('#66758A'))
    c.drawString(SAFE_X+10*MM,hy+3.1*MM,meta['title'][:42].upper())
    if page_title:
        font='FaUI' if is_fa(page_title) else 'LatinB'; c.setFont(font,7.5); c.setFillColor(color(th['deep']))
        if is_fa(page_title): c.drawRightString(W-SAFE_X-6*MM,hy+3.0*MM,visual_rtl(page_title[:42]))
        else: c.drawRightString(W-SAFE_X-6*MM,hy+3.0*MM,page_title[:42])
    glow_line(c,SAFE_X+10*MM,hy-.8*MM,SAFE_X+55*MM,hy-.8*MM,th,.65)

    # Footer: two-layer identity rail + rectangular page chip.
    fy=9.6*MM
    c.setStrokeColor(color('#DCE6F3')); c.setLineWidth(.45); c.line(SAFE_X,fy+5.6*MM,W-SAFE_X,fy+5.6*MM)
    c.setStrokeColor(color(th['accent'],.85)); c.setLineWidth(1.15); c.line(SAFE_X,fy+5.6*MM,SAFE_X+27*MM,fy+5.6*MM)
    footer=footer_override or 'Nima Moheb  //  Full Stack Developer'
    c.setFont('LatinB',6.9); c.setFillColor(color('#59687C')); c.drawString(SAFE_X,fy+1.7*MM,footer[:58])
    if meta.get('branding') in ('normal','prominent'):
