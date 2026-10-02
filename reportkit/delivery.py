"""Check the emitted file, source identity, embedded fonts and exact page counters."""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
import fitz
from pypdf import PdfReader
from .contract import language, load_config, source_identity, validate_config


def verify_delivery(pdf_path, config=None, *, expected_engine_version=None, allow_test_font_fallback=False):
    # Kept as a compatibility argument; it no longer bypasses production gates.
    pdf_path=Path(pdf_path)
    if not pdf_path.is_file(): raise RuntimeError(f'DELIVERY_FAIL: missing {pdf_path}')
    cfg=load_config(config) if isinstance(config,(str,Path)) else config
    errors=[]
    raw=PdfReader(pdf_path).metadata or {}
    producer=str(raw.get('/Producer',''))
    if not producer.startswith('Nima Report Engine '): errors.append('missing Nima Report Engine producer metadata')
    if expected_engine_version and producer!=f'Nima Report Engine {expected_engine_version}': errors.append('engine version mismatch')
    if raw.get('/ReportKitStatus')!='production': errors.append('preview or legacy output is not a verified production deliverable')
    lang=raw.get('/ReportKitLanguage','en'); mode=raw.get('/ReportKitMode','report')
    if cfg is not None:
        validate_config(cfg)
        base=Path(config).resolve().parent if isinstance(config,(str,Path)) else pdf_path.parent
        if raw.get('/ReportKitSourceSHA256')!=source_identity(cfg,base): errors.append('source/config identity mismatch')
        if language(cfg)!=lang: errors.append('language mismatch')
        if cfg['meta'].get('mode','report')!=mode: errors.append('report mode mismatch')
    from .presentation import counter_layout
    from .engine import H
    with fitz.open(pdf_path) as doc:
        if not len(doc): errors.append('PDF has no pages')
        if cfg and len(doc)!=len(cfg['pages']): errors.append('page count differs from source')
        text='\n'.join(page.get_text() for page in doc)
        for ch in text:
            if ch in ('\x00','\ufffd') or unicodedata.category(ch)=='Cf':
                errors.append(f'missing or control glyph U+{ord(ch):04X}'); break
        fonts={font[3]:font[0] for page in doc for font in page.get_fonts(full=True)}
        persian=bool(re.search(r'[\u0600-\u06ff\ufb50-\ufdff\ufe70-\ufeff]',text))
        if persian:
            if not any('Vazirmatn' in name for name in fonts): errors.append('Persian output must embed bundled Vazirmatn')
            if any('NotoNaskh' in n or 'NotoSansArabic' in n or 'DejaVuSans' in n for n in fonts): errors.append('unapproved Persian fallback font')
        for name,xref in fonts.items():
            if 'Vazirmatn' in name or 'IBMPlex' in name:
                if not doc.extract_font(xref)[3]: errors.append(f'font is not embedded: {name}')
        if mode!='cover_showcase':
            _,y,_,h,slots=counter_layout(lang)
            for index,page in enumerate(doc,1):
                if index==1: continue
                for key,expected in (('page',index),('total',len(doc))):
                    x,w=slots[key]
                    value=page.get_text('text',clip=fitz.Rect(x,H-y-h,x+w,H-y)).strip()
                    value=value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))
                    if value!=str(expected): errors.append(f'page {index}: wrong {key} counter ({value!r}, expected {expected})')
        if errors: raise RuntimeError('DELIVERY_FAIL:\n- '+'\n- '.join(errors))
        return {'pdf':str(pdf_path),'producer':producer,'pages':len(doc),'persian':persian,
                'fonts':sorted(fonts),'status':'PASS','source_sha256':raw.get('/ReportKitSourceSHA256')}
