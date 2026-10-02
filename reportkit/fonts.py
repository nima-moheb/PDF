"""Portable, pinned typography. No download or system font discovery on the hot path."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fontTools.ttLib import TTFont as FontToolsFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = Path(__file__).parent / "data" / "fonts"
FONT_FILES = {
    "Latin": "IBMPlexSans-Regular.ttf", "LatinB": "IBMPlexSans-Bold.ttf",
    "Fa": "Vazirmatn-Regular.ttf", "FaB": "Vazirmatn-Bold.ttf",
    "FaUI": "Vazirmatn-Medium.ttf",
}
_registered = {}


def register_fonts():
    manifest = json.loads((FONT_DIR / "manifest.json").read_text())
    contract = {}
    for name, filename in FONT_FILES.items():
        override = os.environ.get("REPORTKIT_FONT_DIR")
        path = Path(override).expanduser() / filename if override else FONT_DIR / filename
        if not path.is_file():
            path = FONT_DIR / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.parent == FONT_DIR and digest != manifest[filename]["sha256"]:
            raise RuntimeError(f"FONT_SETUP_FAIL: bundled font checksum mismatch: {filename}")
        with FontToolsFont(path, lazy=True) as face:
            cmap = face.getBestCmap() or {}
            required = "اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی۰۱۲۳۴۵۶۷۸۹" if name.startswith("Fa") else "Aa019€£"
            family = face['name'].getDebugName(1) or ""
            if name.startswith("Fa") and "Vazirmatn" not in family:
                raise RuntimeError(f"FONT_SETUP_FAIL: {filename} must be Vazirmatn, got {family}")
            if not all(ord(ch) in cmap for ch in required):
                raise RuntimeError(f"FONT_SETUP_FAIL: incomplete glyph coverage: {filename}")
        # Re-register when font bytes change in a long-lived process.
        if _registered.get(name) != digest:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            _registered[name] = digest
        contract[name] = {"file": filename, "sha256": digest}
    return contract


def require_glyphs(text, font):
    face = pdfmetrics.getFont(font).face
    missing = sorted({ord(ch) for ch in text if ord(ch) not in face.charToGlyph})
    if missing:
        codes = ", ".join(f"U+{code:04X}" for code in missing[:8])
        raise ValueError(f"GLYPH_FAIL: {font} cannot render {codes}; use supported text")
