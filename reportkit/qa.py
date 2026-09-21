from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

A4_W = 595.2756
A4_H = 841.8898


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _ink_fraction(pix: fitz.Pixmap) -> float:
    samples = memoryview(pix.samples)
    n = pix.n
    pixels = pix.width * pix.height
    nonwhite = 0
    # RGB(A) channels; alpha is ignored. Sampling every second pixel keeps QA cheap.
    step_px = 2
    for p in range(0, pixels, step_px):
        i = p * n
        if samples[i] < 245 or samples[i + 1] < 245 or samples[i + 2] < 245:
            nonwhite += 1
    checked = (pixels + step_px - 1) // step_px
    return nonwhite / max(checked, 1)


def preflight_and_render(pdf_path, qa_dir, expected_pages=None):
    """Render every final page and perform objective PDF-boundary checks.

    This is intentionally renderer-based: a successful source-level build is not
    considered sufficient. The PNGs and manifest are retained for visual review or
    automated regression diffing.
    """
    pdf_path = Path(pdf_path)
    qa_dir = Path(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)
    for old in qa_dir.glob("page-*.png"):
        old.unlink()

    doc = fitz.open(pdf_path)
    if expected_pages is not None and doc.page_count != expected_pages:
        raise RuntimeError(f"QA_FAIL: expected {expected_pages} pages, got {doc.page_count}")
    if doc.page_count < 1:
        raise RuntimeError("QA_FAIL: final PDF has no pages")

    report = {"pdf_sha256": _sha256(pdf_path), "renderer": "PyMuPDF", "pages": []}
    for idx, page in enumerate(doc, 1):
        rect = page.rect
        if abs(rect.width - A4_W) > 1.0 or abs(rect.height - A4_H) > 1.0:
            raise RuntimeError(f"QA_FAIL: page {idx} is not A4 ({rect.width:.2f}x{rect.height:.2f})")

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        png = qa_dir / f"page-{idx:03d}.png"
        pix.save(png)
        ink = _ink_fraction(pix)
        if ink < 0.006:
            raise RuntimeError(f"QA_FAIL: page {idx} renders effectively blank (ink={ink:.4f})")

        blocks = [b for b in page.get_text("blocks") if len(b) >= 5 and str(b[4]).strip()]
        text_chars = sum(len(str(b[4]).strip()) for b in blocks)
        if text_chars < 5:
            raise RuntimeError(f"QA_FAIL: page {idx} has insufficient extractable text")
        for b in blocks:
            x0, y0, x1, y1 = map(float, b[:4])
            if x0 < -1 or y0 < -1 or x1 > rect.width + 1 or y1 > rect.height + 1:
                raise RuntimeError(f"QA_FAIL: page {idx} contains text outside the media box")

        report["pages"].append({
            "index": idx,
            "png": png.name,
            "png_sha256": _sha256(png),
            "ink_fraction": round(ink, 6),
            "text_chars": text_chars,
            "width": round(rect.width, 4),
            "height": round(rect.height, 4),
        })

    (qa_dir / "qa_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report
