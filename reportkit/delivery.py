from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import fitz

_PERSIAN_RE = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_PERSIAN_DIGIT_RE = re.compile(r"[۰-۹]")
_ASCII_DIGIT_RE = re.compile(r"[0-9]")


def _contains_persian(value) -> bool:
    if isinstance(value, str):
        return bool(_PERSIAN_RE.search(value))
    if isinstance(value, dict):
        return any(_contains_persian(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_persian(v) for v in value)
    return False


def _footer_text(page: fitz.Page) -> str:
    cutoff = page.rect.height - 90
    parts = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if float(span["bbox"][1]) >= cutoff:
                    parts.append(str(span.get("text", "")))
    return " ".join(parts)


def _font_names(doc: fitz.Document):
    out = set()
    for page in doc:
        for font in page.get_fonts(full=True):
            if len(font) > 3 and font[3]:
                out.add(str(font[3]))
    return sorted(out)


def verify_delivery(
    pdf_path,
    config=None,
    *,
    expected_engine_version: str | None = None,
    allow_test_font_fallback: bool = False,
):
    """Hard delivery gate for finished PDFs.

    This intentionally validates the emitted PDF, not only source/config state.
    A file that bypasses Nima Report Engine, leaks control glyphs, uses an
    unapproved Persian fallback font, or loses page-counter digits must fail.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise RuntimeError(f"DELIVERY_FAIL: PDF does not exist: {pdf_path}")

    cfg = config
    if isinstance(config, (str, Path)):
        cfg = json.loads(Path(config).read_text(encoding="utf-8"))

    doc = fitz.open(pdf_path)
    meta = doc.metadata or {}
    producer = str(meta.get("producer") or "")
    errors = []

    if not producer.startswith("Nima Report Engine "):
        errors.append("missing Nima Report Engine producer metadata")
    if expected_engine_version and producer != f"Nima Report Engine {expected_engine_version}":
        errors.append(
            f"engine provenance mismatch: expected {expected_engine_version}, got {producer or '<blank>'}"
        )

    extracted_pages = [page.get_text() or "" for page in doc]
    extracted = "\n".join(extracted_pages)
    for ch in extracted:
        if ch == "\x00":
            errors.append("final PDF contains NUL/missing-glyph characters")
            break
        if ch == "\ufffd":
            errors.append("final PDF contains Unicode replacement glyphs")
            break
        if unicodedata.category(ch) == "Cf":
            errors.append(
                f"final PDF leaks Unicode format-control glyph U+{ord(ch):04X}"
            )
            break

    persian = _contains_persian(cfg) if cfg is not None else bool(_PERSIAN_RE.search(extracted))
    fonts = _font_names(doc)
    if persian and not allow_test_font_fallback:
        if not any("Vazirmatn" in name for name in fonts):
            errors.append("Persian production PDF does not embed Vazirmatn")
        bad_arabic = [
            name for name in fonts
            if "NotoSansArabic" in name or "NotoNaskhArabic" in name
        ]
        if bad_arabic:
            errors.append(
                "unapproved Persian fallback font embedded: " + ", ".join(sorted(bad_arabic))
            )

    # Cover page intentionally has no page number. Pages 2+ must have an actual
    # counter in the footer; the broken JaneDel PDF rendered only 'صفحه از'.
    for idx, page in enumerate(doc):
        if idx == 0:
            continue
        footer = _footer_text(page)
        digits = _PERSIAN_DIGIT_RE.findall(footer) if persian else _ASCII_DIGIT_RE.findall(footer)
        if len(digits) < 2:
            errors.append(
                f"page {idx+1} footer/page counter is missing rendered digits"
            )
            break

    if errors:
        raise RuntimeError("DELIVERY_FAIL:\n- " + "\n- ".join(errors))

    return {
        "pdf": str(pdf_path),
        "producer": producer,
        "pages": doc.page_count,
        "persian": persian,
        "fonts": fonts,
        "status": "PASS",
    }
