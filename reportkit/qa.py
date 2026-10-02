from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path
import fitz
from PIL import Image, ImageChops

A4_W, A4_H = 595.2756, 841.8898
QA_VERSION = 2


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ink_fraction(pix):
    # Pillow's C implementation replaces a Python loop over a million pixels.
    image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    red, green, blue = image.split()
    hist = ImageChops.darker(ImageChops.darker(red, green), blue).histogram()
    return sum(hist[:245]) / (pix.width * pix.height)


def preflight_and_render(pdf_path, qa_dir, expected_pages=None, *, previous_dir=None,
                         page_entries=None, reusable_ids=None, ordered_ids=None):
    pdf_path, qa_dir = Path(pdf_path), Path(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)
    previous = {}
    if previous_dir:
        try:
            old = json.loads((Path(previous_dir)/'qa_manifest.json').read_text())
            if old.get('qa_version') == QA_VERSION and old.get('renderer_version') == fitz.VersionBind:
                previous = {p['index']: p for p in old['pages']}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    report = {'pdf_sha256': _sha256(pdf_path), 'renderer': 'PyMuPDF',
              'renderer_version': fitz.VersionBind, 'qa_version': QA_VERSION, 'pages': [], 'rendered_pages': 0}
    with fitz.open(pdf_path) as doc:
        if expected_pages is not None and len(doc) != expected_pages:
            raise RuntimeError(f'QA_FAIL: expected {expected_pages} pages, got {len(doc)}')
        if not len(doc): raise RuntimeError('QA_FAIL: empty PDF')
        for idx, page in enumerate(doc, 1):
            rect=page.rect
            if abs(rect.width-A4_W)>1 or abs(rect.height-A4_H)>1:
                raise RuntimeError(f'QA_FAIL: page {idx} is not A4')
            blocks=[b for b in page.get_text('blocks') if len(b)>=5 and str(b[4]).strip()]
            text_chars=sum(len(str(b[4]).strip()) for b in blocks)
            if text_chars<5: raise RuntimeError(f'QA_FAIL: page {idx} has insufficient text')
            for block in blocks:
                x0,y0,x1,y1=block[:4]
                if x0< -1 or y0< -1 or x1>rect.width+1 or y1>rect.height+1:
                    raise RuntimeError(f'QA_FAIL: page {idx} has text outside the media box')
            # Hash a serialization of the actual final merged page and resources.
            with fitz.open() as single:
                single.insert_pdf(doc, from_page=idx-1, to_page=idx-1)
                final_hash=hashlib.sha256(single.tobytes(garbage=4, no_new_id=True)).hexdigest()
            png=qa_dir/f'page-{idx:03d}.png'; cached=previous.get(idx,{})
            artifact_hash=page_entries[idx-1]['sha256'] if page_entries else None
            reuse=bool(ordered_ids and ordered_ids[idx-1] in (reusable_ids or set())
                       and cached.get('artifact_sha256')==artifact_hash
                       and cached.get('final_page_sha256')==final_hash)
            old_png=Path(previous_dir)/png.name if previous_dir else None
            if reuse and old_png.is_file() and _sha256(old_png)==cached.get('png_sha256'):
                shutil.copyfile(old_png,png); ink=cached['ink_fraction']
            else:
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                pix.save(png); ink=_ink_fraction(pix); report['rendered_pages']+=1
            if ink<.006: raise RuntimeError(f'QA_FAIL: page {idx} renders blank')
            report['pages'].append({'index':idx,'png':png.name,'png_sha256':_sha256(png),
                                    'final_page_sha256':final_hash,'artifact_sha256':artifact_hash,
                                    'ink_fraction':round(ink,6),'text_chars':text_chars,
                                    'width':round(rect.width,4),'height':round(rect.height,4)})
    (qa_dir/'qa_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
