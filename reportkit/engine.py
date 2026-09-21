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
RESUME_URL = "https://nima-moheb.github.io/myCV/"


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



def draw_resume_link(c, x, y, th, label="VIEW RESUME  ↗", size=7.2, align="left"):
    """Draw a visibly interactive resume link and attach a real PDF URI annotation."""
    c.saveState()
    c.setFont('LatinB',size)
    tw=pdfmetrics.stringWidth(label,'LatinB',size)
    if align=="right":
        tx=x-tw
    else:
        tx=x
    c.setFillColor(color(th['accent']))
    c.drawString(tx,y,label)
    c.setStrokeColor(color(th['accent'],.55)); c.setLineWidth(.45)
    c.line(tx,y-1.4,tx+tw,y-1.4)
    # Give the annotation a generous hit target for PDF viewers.
    c.linkURL(RESUME_URL,(tx-2,y-4,tx+tw+3,y+size+4),relative=0,thickness=0)
    c.restoreState()
    return tx,tw


def _pdf_uri_count(path, target):
    count=0
    rd=PdfReader(str(path))
    for page in rd.pages:
        for ref in page.get('/Annots',[]) or []:
            obj=ref.get_object()
            action=obj.get('/A')
            if action and action.get('/URI')==target:
                count+=1
    return count


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
        # Always use the shared hyperlink primitive; never render link-looking dead text.
        draw_resume_link(c,SAFE_X+78*MM,fy+1.7*MM,th,label='VIEW RESUME  ↗',size=6.9)
    pw=30*MM; ph=7.2*MM; px=W-SAFE_X-pw; py=fy-.2*MM
    round_rect(c,px,py,pw,ph,ph/2,fill=th['deep'])
    c.setFont('LatinB',6.6); c.setFillColor(color(th['accent2'])); c.drawString(px+4*MM,py+2.5*MM,'PAGE')
    c.setFont('LatinB',8.1); c.setFillColor(white); c.drawRightString(px+pw-4*MM,py+2.25*MM,f'{page:02d} / {total:02d}')


def tech_grid(c, th, dark=False):
    c.saveState(); c.setLineWidth(.25)
    base = '#FFFFFF' if dark else th['accent']
    c.setStrokeColor(color(base,.06 if dark else .045))
    step=9*MM
    x=0
    while x<W: c.line(x,0,x,H); x+=step
    y=0
    while y<H: c.line(0,y,W,y); y+=step
    if not dark:
        cx=W-22*MM; cy=49*MM
        c.setStrokeColor(color(th['accent'],.045)); c.setLineWidth(.8)
        for rr in (18*MM,27*MM,36*MM): c.circle(cx,cy,rr,fill=0,stroke=1)
        c.setFillColor(color(th['accent2'],.09))
        for dx,dy in ((0,0),(-20*MM,8*MM),(10*MM,23*MM),(-8*MM,31*MM)): c.circle(cx+dx,cy+dy,1.5*MM,fill=1,stroke=0)
    c.restoreState()


def _wave_path(c, rtl, th):
    """Native vector interpretation of the selected 'digital wave' cover direction."""
    c.saveState()
    # Diagonal light plane — mirrored automatically for RTL.
    if rtl:
        pts=[(0,H*.94),(0,H*.53),(W*.63,H*.14),(W*.77,H*.14)]
    else:
        pts=[(W,H*.94),(W,H*.53),(W*.37,H*.14),(W*.23,H*.14)]
    pth=c.beginPath(); pth.moveTo(*pts[0])
    for pt in pts[1:]: pth.lineTo(*pt)
    pth.close()
    c.setFillColor(color(th['accent2'],.10)); c.setStrokeColor(color(th['accent2'],.55)); c.setLineWidth(1.2)
    c.drawPath(pth,fill=1,stroke=1)

    # Layered data-wave ribbons. Purely decorative; no fake numeric labels.
    def ribbon(y0, amp, alpha, offset):
        p=c.beginPath()
        if rtl:
            p.moveTo(W,y0)
            p.curveTo(W*.79,y0+amp*.70,W*.64,y0-amp*.55,W*.45,y0+amp*.08)
            p.curveTo(W*.29,y0+amp*.55,W*.16,y0-amp*.20,0,y0+amp*.22)
        else:
            p.moveTo(0,y0)
            p.curveTo(W*.21,y0+amp*.70,W*.36,y0-amp*.55,W*.55,y0+amp*.08)
            p.curveTo(W*.71,y0+amp*.55,W*.84,y0-amp*.20,W,y0+amp*.22)
        c.setStrokeColor(color(th['accent2'],alpha)); c.setLineWidth(1.0+offset*.45)
        c.drawPath(p,fill=0,stroke=1)
    for i in range(13):
        ribbon(56*MM+i*2.0*MM,16*MM+i*.55*MM,.10+i*.015,i%3)

    # Signal nodes on the wave side.
    nodes=[(.14,.31),(.27,.37),(.40,.29),(.55,.41),(.70,.35),(.86,.46)]
    for nx,ny in nodes:
        x=(1-nx)*W if rtl else nx*W
        y=ny*H
        c.setFillColor(color(th['accent2'],.15)); c.circle(x,y,4.0*MM,fill=1,stroke=0)
        c.setFillColor(color(th['accent2'])); c.circle(x,y,1.2*MM,fill=1,stroke=0)
    c.restoreState()


def cover(c, meta, p, th):
    """Selected cover #2: diagonal digital-wave composition, automatically mirrored for RTL."""
    title=p.get('title',meta['title'])
    rtl=bool(p.get('direction')=='rtl' or (p.get('direction')!='ltr' and is_fa(title)))
    c.setFillColor(color(th['deep'])); c.rect(0,0,W,H,fill=1,stroke=0)
    # Dark -> vivid gradient, mirrored by direction.
    if rtl:
        c.linearGradient(W,0,0,H,[color(th['deep']),color(th['accent'])],[0,.88])
    else:
        c.linearGradient(0,0,W,H,[color(th['deep']),color(th['accent'])],[0,.88])
    tech_grid(c,th,dark=True)
    _wave_path(c,rtl,th)

    # Small top identity and cover category.
    eyebrow=p.get('eyebrow', 'گزارش' if rtl else 'REPORT')
    c.setFillColor(color(th['accent2'])); c.setLineWidth(1.4)
    if rtl:
        c.line(W-18*MM,H-37*MM,W-5*MM,H-37*MM)
        draw_text(c,eyebrow,W-82*MM,H-44*MM,64*MM,size=8.8,bold=True,rtl=is_fa(eyebrow),colorv='#EAF5FF',max_lines=1)
        c.setFont('LatinB',6.8); c.setFillColor(color('#BFD8FF')); c.drawString(16*MM,H-31*MM,'DATA  ←  INSIGHT  ←  IMPACT')
    else:
        c.line(18*MM,H-37*MM,31*MM,H-37*MM)
        draw_text(c,eyebrow,18*MM,H-44*MM,64*MM,size=8.8,bold=True,rtl=False,colorv='#EAF5FF',max_lines=1)
        c.setFont('LatinB',6.8); c.setFillColor(color('#BFD8FF')); c.drawRightString(W-16*MM,H-31*MM,'DATA  →  INSIGHT  →  IMPACT')

    # Title block occupies the quiet side; Persian is genuinely mirrored to the right.
    title_w=118*MM
    tx=W-18*MM-title_w if rtl else 18*MM
    y=H-70*MM
    font='FaB' if rtl else 'LatinB'
    size=31.5 if rtl else 32.5
    lines=wrap(title,font,size,title_w,rtl)
    if len(lines)>4: raise ValueError('FIT_FAIL: cover title too long')
    c.setFillColor(white)
    for line in lines:
        if rtl:
            c.setFont(font,size); c.drawRightString(tx+title_w,y,visual_rtl(line))
        else:
            c.setFont(font,size); c.drawString(tx,y,line)
        y-=size*1.16

    # Accent underline follows reading direction.
    uy=y+2*MM
    if rtl: glow_line(c,tx+title_w-42*MM,uy,tx+title_w,uy,th,.9)
    else: glow_line(c,tx,uy,tx+42*MM,uy,th,.9)

    subtitle=p.get('subtitle',meta.get('subtitle',''))
    if subtitle:
        y-=7*MM
        draw_text(c,subtitle,tx,y,title_w,size=11.2,rtl=rtl if is_fa(subtitle) else None,colorv='#EAF2FF',max_lines=5)

    # Compact metadata cards stay in the title half and reverse order for RTL.
    yb=H-160*MM; gap=3.2*MM; cw=(title_w-gap*2)/3; ch=24*MM
    if rtl:
        cells=[('برای',meta.get('recipient','')),('تاریخ',meta.get('date','')),('تهیه شده توسط',meta.get('author','Nima Moheb'))]
    else:
        cells=[('Prepared by',meta.get('author','Nima Moheb')),('Date',meta.get('date','')),('For',meta.get('recipient',''))]
    for i,(lab,val) in enumerate(cells):
        x=tx+i*(cw+gap)
        round_rect(c,x,yb,cw,ch,9,fill='#061A36',stroke=th['accent2'],sw=.45,alpha=.64)
        draw_text(c,lab,x+4*MM,yb+16*MM,cw-8*MM,size=6.5,bold=True,rtl=is_fa(lab),colorv='#BFD8FF',max_lines=1)
        draw_text(c,str(val),x+4*MM,yb+7.5*MM,cw-8*MM,size=8.6,bold=True,rtl=is_fa(str(val)),colorv='#FFFFFF',max_lines=2)

    # Bottom micro identity — no fake KPIs.
    c.setFont('LatinB',6.3); c.setFillColor(color('#93C7FF'))
    if rtl:
        c.drawRightString(W-18*MM,13*MM,'NIMA REPORT ENGINE')
        c.drawString(18*MM,13*MM,'STRUCTURED  /  TRACEABLE  /  FINAL')
    else:
        c.drawString(18*MM,13*MM,'NIMA REPORT ENGINE')
        c.drawRightString(W-18*MM,13*MM,'STRUCTURED  /  TRACEABLE  /  FINAL')


def page_title(c,title,eyebrow,th,y=H-30*MM):
    c.setFillColor(color(th['accent'])); c.setFont('LatinB',7.4); c.drawString(SAFE_X,y+8*MM,eyebrow.upper())
    draw_text(c,title,SAFE_X,y,W-2*SAFE_X,size=21.5,bold=True,max_lines=2)
    return y-13*MM


def summary(c,meta,p,th,page):
    header_footer(c,meta,page,p.get('title','Summary'),th,p.get('footer'))
    tech_grid(c,th); y=page_title(c,p['title'],p.get('eyebrow','Overview'),th)
    intro=p.get('intro',''); y=draw_text(c,intro,SAFE_X,y,W-2*SAFE_X,size=10.8,max_lines=5)
    y-=8*MM
    cards=p.get('cards',[])[:4]; gap=6*MM; w=(W-2*SAFE_X-gap)/2; h=59*MM
    for i,card in enumerate(cards):
        col=i%2; row=i//2; x=SAFE_X+col*(w+gap); yy=y-row*(h+gap)-h
        shadow_card(c,x,yy,w,h,12,accent=th['accent'])
        val=str(card.get('value','')); lab=str(card.get('label','')); note=str(card.get('note',''))
        c.setFillColor(color(th['deep'])); c.setFont('LatinB',24); c.drawString(x+6*MM,yy+h-13*MM,val)
        draw_text(c,lab,x+6*MM,yy+h-24*MM,w-12*MM,size=10,bold=True,max_lines=2)
        if note: draw_text(c,note,x+6*MM,yy+9*MM,w-12*MM,size=8.4,colorv='#6E7D92',max_lines=2)


def text_page(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Report'),th)
    blocks=p.get('blocks',[])
    groups=[]; current={'title':'','content':[]}
    for block in blocks:
        if block.get('kind')=='heading':
            if current['title'] or current['content']: groups.append(current)
            current={'title':block.get('text',''),'content':[]}
        else: current['content'].append(block)
    if current['title'] or current['content']: groups.append(current)
    if not groups: return
    gap=5*MM; bottom=30*MM; tw=W-2*SAFE_X-14*MM
    required=[max(34*MM,_measure_group(g,tw)) for g in groups]
    available=y-bottom-gap*(len(groups)-1)
    if sum(required)>available: raise ValueError(f'FIT_FAIL: text groups need {sum(required)/MM:.1f}mm, have {available/MM:.1f}mm on {p["id"]}')
    # Extra room is distributed gently, avoiding a short card occupying a third of a page.
    extra=available-sum(required); bonus=min(extra/max(len(groups),1),10*MM)
    heights=[h+bonus for h in required]
    top=y
    for gi,(g,card_h) in enumerate(zip(groups,heights)):
        yy=top-card_h
        shadow_card(c,SAFE_X,yy,W-2*SAFE_X,card_h,13,accent=th['accent'] if gi==0 else None)
        tx=SAFE_X+7*MM; cy=top-10*MM
        if g['title']:
            cy=draw_text(c,g['title'],tx,cy,tw,size=14.7,bold=True,max_lines=2); cy-=4*MM
        for block in g['content']:
            kind=block.get('kind','text')
            if kind=='text':
                cy=draw_text(c,block['text'],tx,cy,tw,size=10.9,max_lines=12); cy-=3.5*MM
            elif kind=='bullets':
                for item in block.get('items',[]):
                    rtl=is_fa(item); bx=tx+5*MM; bw=tw-7*MM
                    dotx=tx+tw-1.8*MM if rtl else tx+1.6*MM
                    c.setFillColor(color(th['accent'])); c.circle(dotx,cy+1.4,1.35,fill=1,stroke=0)
                    cy=draw_text(c,item,bx,cy,bw,size=10.2,max_lines=4); cy-=2.5*MM
        if cy < yy+6*MM: raise ValueError(f'FIT_FAIL: text group overflow on page {p["id"]}')
        top=yy-gap


def cards_page(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Highlights'),th)
    cards=p.get('cards',[])[:6]; cols=2; gap=5*MM; w=(W-2*SAFE_X-gap)/2; h=45*MM
    for i,card in enumerate(cards):
        x=SAFE_X+(i%cols)*(w+gap); yy=y-(i//cols)*(h+gap)-h
        shadow_card(c,x,yy,w,h,13,accent=card.get('accent',th['accent']))
        draw_text(c,card.get('title',''),x+6*MM,yy+h-10*MM,w-12*MM,size=11.2,bold=True,max_lines=2)
        draw_text(c,card.get('text',''),x+6*MM,yy+h-23*MM,w-12*MM,size=9,max_lines=5,colorv='#536174')


def chart_text(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Data'),th)
    chart=p.get('chart',{}); data=[float(v) for v in chart.get('data',[])]; labels=chart.get('labels',[])
    box_x=SAFE_X; box_y=74*MM; box_w=W-2*SAFE_X; box_h=105*MM
    shadow_card(c,box_x,box_y,box_w,box_h,14)
    c.setFillColor(color('#536174')); c.setFont('LatinB',8); c.drawString(box_x+7*MM,box_y+box_h-11*MM,chart.get('title','TREND').upper())
    if not data: raise ValueError(f'DATA_FAIL: chart page {p["id"]} has no data')

    maxv=max(data); minv=min(data)
    if maxv==minv: maxv=minv+1
    pad=(maxv-minv)*.16
    lo=max(0,minv-pad); hi=maxv+pad
    left=box_x+15*MM; bottom=box_y+20*MM; gw=box_w-28*MM; gh=box_h-41*MM

    # Quiet grid with numeric scale: unmistakably a chart, never decorative bars.
    c.setFont('Latin',6.6); c.setFillColor(color('#7A8798'))
    for i in range(4):
        ratio=i/3; yy=bottom+ratio*gh; val=lo+ratio*(hi-lo)
        c.setStrokeColor(color('#D9E2EE')); c.setLineWidth(.35); c.line(left,yy,left+gw,yy)
        c.drawRightString(left-3*MM,yy-2,f'{val:.0f}')

    typ=chart.get('type','line')
    if typ=='bar':
        slot=gw/max(len(data),1)
        bw=min(13*MM,slot*.56)
        for i,v in enumerate(data):
            x=left+i*slot+(slot-bw)/2
            h=max(1.4*MM,gh*(v-lo)/(hi-lo))
            # Clean single-body bar + subtle shadow. No segmented tops / horns.
            c.setFillColor(color('#0A1930',.08)); c.roundRect(x+1.2, bottom-1.2, bw, h, bw*.22, fill=1, stroke=0)
            c.setFillColor(color(th['accent'])); c.roundRect(x,bottom,bw,h,bw*.22,fill=1,stroke=0)
            c.setFont('LatinB',7.3); c.setFillColor(color(th['deep'])); c.drawCentredString(x+bw/2,bottom+h+3.5,f'{v:g}')
            lab=labels[i] if i<len(labels) else str(i+1)
            c.setFont('Latin',7); c.setFillColor(color('#69778A')); c.drawCentredString(x+bw/2,bottom-10,lab[:12])
    elif typ=='line':
        pts=[]
        for i,v in enumerate(data):
            x=left+i*gw/max(len(data)-1,1)
            yy=bottom+gh*(v-lo)/(hi-lo)
            pts.append((x,yy,v))
        c.setStrokeColor(color(th['accent'])); c.setLineWidth(2.4)
        for a,b in zip(pts,pts[1:]): c.line(a[0],a[1],b[0],b[1])
        for i,(x,yy,v) in enumerate(pts):
            c.setFillColor(color(th['accent2'],.20)); c.circle(x,yy,4.0,fill=1,stroke=0)
            c.setFillColor(color(th['accent'])); c.circle(x,yy,2.2,fill=1,stroke=0)
            c.setFont('LatinB',7.1); c.setFillColor(color(th['deep'])); c.drawCentredString(x,yy+7,f'{v:g}')
            lab=labels[i] if i<len(labels) else str(i+1)
            c.setFont('Latin',7); c.setFillColor(color('#69778A')); c.drawCentredString(x,bottom-10,lab[:12])
    else:
        raise ValueError(f'DATA_FAIL: unsupported chart type {typ!r}')

    ay=31*MM; ah=34*MM
    round_rect(c,SAFE_X,ay,W-2*SAFE_X,ah,12,fill=th['soft'],stroke=th['accent'],sw=.5)
    draw_text(c,p.get('analysis',''),SAFE_X+6*MM,ay+ah-9*MM,W-2*SAFE_X-12*MM,size=9.4,max_lines=6)
    source=p.get('source')
    if source:
        c.setFont('Latin',7); c.setFillColor(color('#7A8798')); c.drawString(SAFE_X,24*MM,'Source: '+source[:120])


def comparison(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Comparison'),th)
    items=p.get('items',[])[:3]; gap=5*MM; w=(W-2*SAFE_X-gap*(len(items)-1))/max(len(items),1); h=120*MM
    for i,it in enumerate(items):
        x=SAFE_X+i*(w+gap); yy=y-h
        shadow_card(c,x,yy,w,h,14,accent=it.get('accent',th['accent']))
        c.setFillColor(color(it.get('accent',th['accent']))); c.circle(x+w-8*MM,yy+h-10*MM,4*MM,fill=1,stroke=0)
        draw_text(c,it.get('title',''),x+6*MM,yy+h-12*MM,w-18*MM,size=11.2,bold=True,max_lines=2)
        if it.get('value'):
            c.setFont('LatinB',20); c.setFillColor(color(th['deep'])); c.drawString(x+6*MM,yy+h-30*MM,str(it['value']))
        by=yy+h-44*MM
        for bullet in it.get('bullets',[]):
            by=draw_text(c,'• '+bullet,x+6*MM,by,w-12*MM,size=8.6,max_lines=3); by-=3*MM


def table_page(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Table'),th)
    cols=p.get('columns',[]); rows=p.get('rows',[])
    if not cols or not rows: return
    x=SAFE_X; total=W-2*SAFE_X; widths=p.get('widths') or [1/len(cols)]*len(cols)
    s=sum(widths); widths=[total*v/s for v in widths]
    rh=13*MM; hh=14*MM
    # elevated container
    h=hh+rh*len(rows)
    if h > y-28*MM: raise ValueError('FIT_FAIL: table too tall')
    yy=y-h
    shadow_card(c,x,yy,total,h,13)
    c.setFillColor(color(th['deep'])); c.roundRect(x,yy+h-hh,total,hh,11,fill=1,stroke=0)
    c.setFillColor(color(th['accent'])); c.roundRect(x,yy+h-2.6,total,2.6,1.3,fill=1,stroke=0)
    xx=x
    for j,col in enumerate(cols):
        c.setFont('FaUI' if is_fa(col) else 'LatinB',8.2); c.setFillColor(white)
        if is_fa(col): c.drawRightString(xx+widths[j]-4*MM,yy+h-hh/2-2.5,visual_rtl(col))
        else: c.drawString(xx+4*MM,yy+h-hh/2-2.5,col[:24])
        xx+=widths[j]
    for i,row in enumerate(rows):
        ry=yy+h-hh-(i+1)*rh
        if i%2==0:
            c.setFillColor(color(th['soft'],.55)); c.rect(x,ry,total,rh,fill=1,stroke=0)
        xx=x
        for j,val in enumerate(row):
            val=str(val); font='Fa' if is_fa(val) else 'Latin'; c.setFont(font,8.2); c.setFillColor(color('#263449'))
            if is_fa(val): c.drawRightString(xx+widths[j]-4*MM,ry+rh/2-2.5,visual_rtl(val[:80]))
            else: c.drawString(xx+4*MM,ry+rh/2-2.5,val[:38])
            xx+=widths[j]
        c.setStrokeColor(color('#D9E2EE')); c.setLineWidth(.25); c.line(x,ry,x+total,ry)


def image_text(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Evidence'),th)
    x=SAFE_X; iw=W-2*SAFE_X; ih=132*MM; iy=y-ih
    shadow_card(c,x,iy,iw,ih,14)
    img=p.get('image')
    if not img or not Path(img).exists():
        raise ValueError(f'ASSET_FAIL: image page {p["id"]} requires a valid image path')
    c.drawImage(img,x+4*MM,iy+4*MM,iw-8*MM,ih-8*MM,preserveAspectRatio=True,anchor='c',mask='auto')
    draw_text(c,p.get('text',''),SAFE_X,iy-10*MM,W-2*SAFE_X,size=10.2,max_lines=6)


def timeline(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Timeline'),th)
    items=p.get('items',[])[:6]; xline=SAFE_X+14*MM; c.setStrokeColor(color(th['accent'],.35)); c.setLineWidth(2); c.line(xline,36*MM,xline,y-5*MM)
    gap=(y-48*MM)/max(len(items),1)
    yy=y-12*MM
    for i,it in enumerate(items):
        c.setFillColor(color(th['accent2'])); c.circle(xline,yy,4.2*MM,fill=1,stroke=0); c.setFillColor(color(th['accent'])); c.circle(xline,yy,2.1*MM,fill=1,stroke=0)
        shadow_card(c,xline+10*MM,yy-17*MM,W-xline-10*MM-SAFE_X,32*MM,10,accent=th['accent'] if i==0 else None)
        draw_text(c,it.get('title',''),xline+16*MM,yy+7*MM,W-xline-28*MM-SAFE_X,size=10.5,bold=True,max_lines=2)
        draw_text(c,it.get('text',''),xline+16*MM,yy-3*MM,W-xline-28*MM-SAFE_X,size=8.5,colorv='#59677A',max_lines=3)
        yy-=gap


def sources(c,meta,p,th,page):
    header_footer(c,meta,page,p['title'],th,p.get('footer')); tech_grid(c,th)
    y=page_title(c,p['title'],p.get('eyebrow','Sources'),th)
    items=p.get('items',[])
    if not items: return
    cols=2 if len(items)<=6 else 1; gap=5*MM
    if cols==2:
        w=(W-2*SAFE_X-gap)/2; rows=math.ceil(len(items)/2); avail=y-31*MM-gap*(rows-1); h=avail/rows
        if h<37*MM: raise ValueError('FIT_FAIL: source cards too dense')
        for i,s in enumerate(items):
            col=i%2; row=i//2; x=SAFE_X+col*(w+gap); top=y-row*(h+gap); yy=top-h
            shadow_card(c,x,yy,w,h,12,accent=th['accent'] if i==0 else None)
            pill(c,f'{i+1:02d}',x+5*MM,top-12*MM,14*MM,7.5*MM,th)
            draw_text(c,s,x+5*MM,top-21*MM,w-10*MM,size=9.1,max_lines=6,colorv='#344256')
    else:
        for i,s in enumerate(items,1):
            h=31*MM; yy=y-h
            shadow_card(c,SAFE_X,yy,W-2*SAFE_X,h,11)
            pill(c,f'{i:02d}',SAFE_X+5*MM,y-11*MM,14*MM,7*MM,th)
            draw_text(c,s,SAFE_X+24*MM,y-9*MM,W-2*SAFE_X-30*MM,size=9.1,max_lines=4,colorv='#344256')
            y=yy-gap
            if y<30*MM: raise ValueError('FIT_FAIL: sources overflow')


def closing(c,meta,p,th,page):
    c.linearGradient(0,0,W,H,[color('#F8FAFD'),color(th['soft'])])
    tech_grid(c,th)
    c.setFillColor(color(th['accent'])); c.roundRect(SAFE_X,H-38*MM,34*MM,8*MM,4*MM,fill=1,stroke=0)
    c.setFillColor(white); c.setFont('LatinB',8); c.drawCentredString(SAFE_X+17*MM,H-35.2*MM,'REPORT COMPLETE')
    draw_text(c,p.get('title','Thank you'),SAFE_X,H-64*MM,W-2*SAFE_X,size=28,bold=True,max_lines=2)
    draw_text(c,p.get('text',''),SAFE_X,H-88*MM,W-2*SAFE_X,size=11,max_lines=6,colorv='#4E5C70')
    # prominent identity redesigned per decision
    y=40*MM; h=36*MM
    shadow_card(c,SAFE_X,y,W-2*SAFE_X,h,14,accent=th['accent'])
    c.setFillColor(color(th['deep'])); c.setFont('LatinB',14); c.drawString(SAFE_X+7*MM,y+23*MM,'Nima Moheb')
    c.setFillColor(color('#5B687A')); c.setFont('Latin',9); c.drawString(SAFE_X+7*MM,y+14*MM,'Full Stack Developer')
    draw_resume_link(c,SAFE_X+7*MM,y+6*MM,th,label='VIEW RESUME  ↗',size=9.2)
    c.setFont('Latin',7.5); c.setFillColor(color('#778497')); c.drawRightString(W-SAFE_X-7*MM,y+6*MM,RESUME_URL.replace('https://',''))

RENDERERS={'cover':cover,'summary':summary,'text':text_page,'cards':cards_page,'chart_text':chart_text,'comparison':comparison,'table':table_page,'image_text':image_text,'timeline':timeline,'sources':sources,'closing':closing}


def scrub(data):
    raw=json.dumps(data,ensure_ascii=False)
    upper=raw.upper()
    found=[]
    for x in BANNED:
        if re.search(r'[A-Za-z]', x):
            pat=r'(?<![A-Z])'+re.escape(x.upper())+r'(?![A-Z])'
            if re.search(pat, upper): found.append(x)
        else:
            if x in raw: found.append(x)
    if found: raise ValueError('PUBLIC_SAFETY_FAIL: banned text: '+', '.join(found))


def render_page(meta,p,page_num,out):
    th=THEMES[meta.get('theme','blue')]
    c=canvas.Canvas(str(out),pagesize=A4,pageCompression=1)
    c.setTitle(meta['title']); c.setAuthor(meta.get('author','Nima Moheb'))
    fn=RENDERERS[p['type']]
    if p['type']=='cover': fn(c,meta,p,th)
    elif p['type']=='closing': fn(c,meta,p,th,page_num)
    else: fn(c,meta,p,th,page_num)
    c.showPage(); c.save()


def sha(path):
    h=hashlib.sha256(); h.update(Path(path).read_bytes()); return h.hexdigest()


def build(config_path,out_pdf,only_ids=None):
    register_fonts()
    cfg=json.loads(Path(config_path).read_text())
    validate(cfg,SCHEMA); scrub(cfg)
    cfg['meta']['_page_count']=len(cfg['pages'])
    out_pdf=Path(out_pdf); out_pdf.parent.mkdir(parents=True,exist_ok=True)
    pages_dir=out_pdf.parent/'pages'; pages_dir.mkdir(exist_ok=True)
    manifest={}
    for idx,p in enumerate(cfg['pages'],1):
        pp=pages_dir/f'{idx:03d}-{p["id"]}.pdf'
        if only_ids is None or p['id'] in only_ids or not pp.exists():
            render_page(cfg['meta'],p,idx,pp)
        manifest[p['id']]={'index':idx,'file':pp.name,'sha256':sha(pp)}
    wr=PdfWriter()
    for p in cfg['pages']:
        pp=pages_dir/manifest[p['id']]['file']; rd=PdfReader(str(pp)); wr.add_page(rd.pages[0])
    with out_pdf.open('wb') as f: wr.write(f)
    # A report may visually mention a resume only if it is a real clickable PDF URI.
    if cfg['meta'].get('branding') in ('normal','prominent') and _pdf_uri_count(out_pdf,RESUME_URL)<1:
        raise RuntimeError('LINK_FAIL: resume URL annotation missing from final PDF')
    (out_pdf.parent/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
