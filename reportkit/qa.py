from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

A4_W = 595.2756
A4_H = 841.8898
BODY_TOP = 112.0
BODY_BOTTOM = 738.0
SPARSE_THRESHOLDS = {
    "summary": 0.66,
    "text": 0.64,
    "cards": 0.66,
    "chart_text": 0.66,
    "comparison": 0.64,
    "table": 0.52,
    "image_text": 0.60,
    "timeline": 0.72,
    "sources": 0.40,
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


def _ink_fraction(pix: fitz.Pixmap) -> float:
    samples = memoryview(pix.samples); n = pix.n; pixels = pix.width * pix.height; nonwhite = 0
    step_px = 2
    for p in range(0, pixels, step_px):
        i = p * n
        if samples[i] < 245 or samples[i + 1] < 245 or samples[i + 2] < 245:
            nonwhite += 1
    checked = (pixels + step_px - 1) // step_px
    return nonwhite / max(checked, 1)


def _body_reach(blocks):
    body = [b for b in blocks if float(b[3]) >= BODY_TOP and float(b[1]) <= BODY_BOTTOM and str(b[4]).strip()]
    if not body:
        return 0.0, 0.0
    min_y = max(BODY_TOP, min(float(b[1]) for b in body))
    max_y = min(BODY_BOTTOM, max(float(b[3]) for b in body))
    reach = max(0.0, (max_y - BODY_TOP) / (BODY_BOTTOM - BODY_TOP))
    span = max(0.0, (max_y - min_y) / (BODY_BOTTOM - BODY_TOP))
    return reach, span


def preflight_and_render(pdf_path, qa_dir, expected_pages=None, page_types=None):
    """Render every final page and enforce visual/output-boundary invariants.

    v0.5 adds a body-density gate. Decorative grids no longer let a report pass while
    two thirds of the actual information area is empty. A sparse page must be
    recomposed, enriched, or consolidated before delivery.
    """
    pdf_path = Path(pdf_path); qa_dir = Path(qa_dir); qa_dir.mkdir(parents=True, exist_ok=True)
    for old in qa_dir.glob("page-*.png"): old.unlink()
    doc = fitz.open(pdf_path)
    if expected_pages is not None and doc.page_count != expected_pages:
        raise RuntimeError(f"QA_FAIL: expected {expected_pages} pages, got {doc.page_count}")
    if doc.page_count < 1: raise RuntimeError("QA_FAIL: final PDF has no pages")
    if page_types is not None and len(page_types) != doc.page_count:
        raise RuntimeError("QA_FAIL: page type metadata does not match final page count")

    report = {"pdf_sha256": _sha256(pdf_path), "renderer": "PyMuPDF", "pages": []}
    for idx, page in enumerate(doc, 1):
        rect = page.rect
        if abs(rect.width - A4_W) > 1.0 or abs(rect.height - A4_H) > 1.0:
            raise RuntimeError(f"QA_FAIL: page {idx} is not A4 ({rect.width:.2f}x{rect.height:.2f})")
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        png = qa_dir / f"page-{idx:03d}.png"; pix.save(png)
        ink = _ink_fraction(pix)
        if ink < 0.006: raise RuntimeError(f"QA_FAIL: page {idx} renders effectively blank (ink={ink:.4f})")

        blocks = [b for b in page.get_text("blocks") if len(b) >= 5 and str(b[4]).strip()]
        text_chars = sum(len(str(b[4]).strip()) for b in blocks)
        if text_chars < 5: raise RuntimeError(f"QA_FAIL: page {idx} has insufficient extractable text")
        for b in blocks:
            x0, y0, x1, y1 = map(float, b[:4])
            if x0 < -1 or y0 < -1 or x1 > rect.width + 1 or y1 > rect.height + 1:
                raise RuntimeError(f"QA_FAIL: page {idx} contains text outside the media box")

        page_type = page_types[idx - 1] if page_types else None
        reach, span = _body_reach(blocks)
        threshold = SPARSE_THRESHOLDS.get(page_type)
        if threshold is not None and reach < threshold:
            raise RuntimeError(
                f"SPARSE_PAGE_FAIL: page {idx} ({page_type}) reaches only {reach:.1%} of the usable body; "
                f"minimum is {threshold:.0%}. Recompose, merge, or add substantive content."
            )
        report["pages"].append({
            "index": idx, "type": page_type, "png": png.name, "png_sha256": _sha256(png),
            "ink_fraction": round(ink, 6), "text_chars": text_chars,
            "body_reach": round(reach, 4), "body_span": round(span, 4),
            "width": round(rect.width, 4), "height": round(rect.height, 4),
        })
    (qa_dir / "qa_manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
