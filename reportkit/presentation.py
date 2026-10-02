"""Current presentation boundary: language-aware chrome and clean reusable components."""
from __future__ import annotations
from contextvars import ContextVar
from . import engine as e
from .fonts import require_glyphs
from .pricing import pricing_page
from .visual_v05 import clean_text

LANGUAGE = ContextVar('report_language', default='en')
LABELS = {
 'fa': {'Overview':'خلاصه','Report':'گزارش','Highlights':'نکات اصلی','Data':'داده‌ها','Comparison':'مقایسه','Table':'جدول','Evidence':'شواهد','Timeline':'مسیر اجرا','Sources':'منابع','TREND':'روند','Source: ':'منبع: ','DATA TABLE':'جدول داده‌ها','NIMA REPORT ENGINE':'گزارش نیما','STRUCTURED / FINAL':'ساختاریافته / نهایی','REPORT':'گزارش','DATA / INSIGHT / IMPACT':'داده / تحلیل / نتیجه','REPORT COMPLETE':'پایان گزارش','PORTFOLIO / RESUME':'رزومه / نمونه‌کار'},
 'es': {'Overview':'Resumen','Report':'Informe','Highlights':'Puntos clave','Data':'Datos','Comparison':'Comparación','Table':'Tabla','Evidence':'Evidencia','Timeline':'Plan de trabajo','Sources':'Fuentes','TREND':'TENDENCIA','Source: ':'Fuente: ','DATA TABLE':'TABLA DE DATOS','NIMA REPORT ENGINE':'INFORME DE NIMA','STRUCTURED / FINAL':'ESTRUCTURADO / FINAL','REPORT':'INFORME','DATA / INSIGHT / IMPACT':'DATOS / ANÁLISIS / IMPACTO','REPORT COMPLETE':'FIN DEL INFORME','PORTFOLIO / RESUME':'PORTAFOLIO / CV'}
}


def chrome(text):
    return LABELS.get(LANGUAGE.get(), {}).get(text, text)


def draw_chrome(c, text, *args, **kwargs):
    text = chrome(text)
    if e.is_fa(text): kwargs.update(font='FaUI', rtl=True)
    return e.draw_single_line(c, text, *args, **kwargs)


def counter_layout(lang):
    """Coordinates shared by the renderer and exact output-boundary verifier."""
    width = 37*e.MM; x = e.SAFE_X if lang=='fa' else e.W-e.SAFE_X-width
    y = 9.4*e.MM; height = 7.6*e.MM
    if lang=='fa': slots = {'label':(.64, .34), 'page':(.43,.19), 'separator':(.25,.16), 'total':(.03,.19)}
    else: slots = {'label':(.04,.39), 'page':(.44,.19), 'separator':(.64,.10), 'total':(.77,.19)}
    return x,y,width,height,{key:(x+width*start,width*span) for key,(start,span) in slots.items()}


def header_footer(c, meta, number, title, th):
    lang=meta.get('language','en'); rtl=lang=='fa'
    hy=e.H-15.2*e.MM; hh=8.6*e.MM
    e.round_rect(c,e.SAFE_X,hy,e.W-2*e.SAFE_X,hh,hh/2,fill='#FFFFFF',stroke='#DCE6F3',sw=.45)
    dot=e.W-e.SAFE_X-5*e.MM if rtl else e.SAFE_X+5*e.MM
    c.setFillColor(e.color(th['accent'],.2)); c.circle(dot,hy+hh/2,2.4*e.MM,fill=1,stroke=0)
    c.setFillColor(e.color(th['accent'])); c.circle(dot,hy+hh/2,e.MM,fill=1,stroke=0)
    from .visual_v062 import _chrome_line
    left=e.SAFE_X+6*e.MM; right=e.W-e.SAFE_X-80*e.MM
    for text,x,align in ((meta['title'],right if rtl else left+4*e.MM,'right' if rtl else 'left'),(title,left if rtl else right,'left' if rtl else 'right')):
        _chrome_line(c,clean_text(text),x,hy+3*e.MM,70*e.MM,size=7.2,min_size=6,font='FaUI' if e.is_fa(text) else 'LatinB',rtl=e.is_fa(text),colorv='#586A80',align=align)
    fy=9.6*e.MM
    c.setStrokeColor(e.color('#DCE6F3')); c.setLineWidth(.45)
    c.line(e.SAFE_X,fy+5.6*e.MM,e.W-e.SAFE_X,fy+5.6*e.MM)
    author=meta.get('author','نیما محب' if rtl else 'Nima Moheb')
    role={'en':'Full Stack Developer','fa':'توسعه‌دهنده فول‌استک','es':'Desarrollador full stack'}[lang]
    identity=f'{author}  //  {role}' if author in ('Nima Moheb','نیما محب') else author
    _chrome_line(c,identity,e.W-e.SAFE_X-100*e.MM if rtl else e.SAFE_X,fy+1.5*e.MM,100*e.MM,size=6.8,min_size=6,font='FaUI' if rtl else 'LatinB',rtl=rtl,colorv='#59687C',align='right' if rtl else 'left')
    x,y,w,h,slots=counter_layout(lang)
    e.round_rect(c,x,y,w,h,h/2,fill=th['deep'])
    values={'label':{'en':'PAGE','fa':'صفحه','es':'PÁG.'}[lang], 'page':str(number), 'separator':'از' if rtl else '/', 'total':str(meta['_page_count'])}
    for key,text in values.items():
        if rtl: text=text.translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
        sx,sw=slots[key]
        e.draw_single_line(c,text,sx,y+2.3*e.MM,sw,size=7,min_size=6.5,font='FaUI' if rtl else 'LatinB',rtl=e.is_fa(text),colorv='#FFFFFF',align='center')


def closing(c,meta,p,th,number):
    lang=meta.get('language','en'); rtl=lang=='fa'
    c.linearGradient(0,0,e.W,e.H,[e.color('#F8FAFD'),e.color(th['soft'])])
    e.tech_grid(c,th); header_footer(c,meta,number,p['title'],th)
    y=e.page_title(c,p['title'],chrome('REPORT COMPLETE'),th)
    e.draw_text(c,p['text'],e.SAFE_X,y,e.W-2*e.SAFE_X,size=12,max_lines=10,colorv='#405066')
    y=45*e.MM; h=42*e.MM; width=e.W-2*e.SAFE_X
    e.shadow_card(c,e.SAFE_X,y,width,h,14,accent=th['accent'])
    align='right' if rtl else 'left'; x=e.SAFE_X+7*e.MM
    e.draw_single_line(c,meta['author'],x,y+28*e.MM,width-14*e.MM,size=16,bold=True,colorv=th['deep'],align=align)
    draw_chrome(c,'PORTFOLIO / RESUME',x,y+18*e.MM,width-14*e.MM,size=8,bold=True,colorv='#59687C',align=align)
    e.draw_url_link(c,e.RESUME_URL,x,y+7*e.MM,width-14*e.MM,th,size=10,align=align)


def install():
    original_render=e.render_page
    def render(meta,p,number,out):
        token=LANGUAGE.set(meta.get('language','en'))
        try: return original_render(meta,p,number,out)
        finally: LANGUAGE.reset(token)
    original_draw=e.draw_visual_line
    def draw(c,text,x,y,width,font,size,rtl,align='left'):
        from .visual_v06 import _visible_run, _run_font
        if rtl:
            for kind,run in e.visual_runs(clean_text(text)):
                run=_visible_run(run); require_glyphs(run,_run_font(kind,run,font))
        else: require_glyphs(clean_text(text),font)
        return original_draw(c,text,x,y,width,font,size,rtl,align)
    e.render_page=render; e.draw_visual_line=draw
    e.chrome=chrome; e.draw_chrome=draw_chrome
    e.header_footer=header_footer; e.RENDERERS['closing']=closing
    e.RENDERERS['pricing']=pricing_page
